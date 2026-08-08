"""
Kanea AI Customer Support — FastAPI Backend

Public endpoints:
  GET  /              health check
  GET  /outages       active/scheduled outages
  POST /fault-report  submit fault report (rate-limited: 5/min per IP)
  WS   /ws/{id}       real-time WebSocket chat

Auth endpoints:
  POST /admin/login   returns a session token

Admin-only endpoints (Bearer token required):
  GET  /admin/fault-reports
  GET  /admin/escalations
  GET  /admin/analytics
  GET  /admin/rag-sources
  POST /admin/scrape
  GET  /admin/scrape-log
  GET  /admin/ecg-outages
  POST /admin/seed-demo-outages

  POST /chat-rating         submit star rating for a session
  POST /message-feedback    submit helpful/unhelpful on a message
"""

import os
import secrets
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import database as db
import chatbot
import ecg_scraper
import seed_demo_outages

# ─── Rate limiter ─────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address)

# ─── Admin token store ────────────────────────────────────────────────────────

_admin_tokens: set[str] = set()
_bearer_scheme = HTTPBearer(auto_error=False)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "kanea2026")


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)):
    if credentials is None or credentials.credentials not in _admin_tokens:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


# ─── Scraping helpers ─────────────────────────────────────────────────────────

async def _background_scrape() -> None:
    try:
        outages, errors = await asyncio.to_thread(ecg_scraper.scrape_outages)
        if errors and len(errors) == ecg_scraper.TOTAL_PAGES:
            # Every page fetch failed (e.g. ECG's WAF returned 403 site-wide) —
            # log it as a real failure and leave the last known-good data alone.
            db.log_scrape_failure(errors)
            print(f"[ECG scraper] Blocked on all {len(errors)} pages ({errors[0]['reason']}) — keeping last known outage data")
        else:
            note = f", {len(errors)}/{ecg_scraper.TOTAL_PAGES} pages unreachable" if errors else ""
            db.sync_ecg_outages(outages, error_detail=note or None)
            print(f"[ECG scraper] Synced {len(outages)} live outages from ecg.com.gh{note}")
    except Exception as exc:
        db.log_scrape_failure([{"url": "n/a", "reason": str(exc)}])
        print(f"[ECG scraper] Failed: {exc}")


async def _scrape_loop() -> None:
    """Refresh ECG outage data every hour."""
    while True:
        await asyncio.sleep(3600)
        await _background_scrape()


# ─── App lifecycle ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    # Keep strong references to these background tasks — asyncio only holds a
    # weak reference internally, so an unreferenced task is eligible for GC
    # mid-run. Stashing them on app.state keeps them alive for the process lifetime.
    app.state.bg_tasks = [
        asyncio.create_task(_background_scrape()),   # immediate first scrape
        asyncio.create_task(_scrape_loop()),          # hourly refresh
    ]
    yield


app = FastAPI(
    title="Kanea AI Customer Support",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS_ORIGINS: comma-separated list of allowed origins in production
# (e.g. "https://kanea.vercel.app,https://kanea-admin.vercel.app").
# Defaults to "*" so local dev / first deploys work with zero config —
# lock this down once the frontend's real domain is known.
_cors_origins = os.getenv("CORS_ORIGINS", "*")
_allow_origins = ["*"] if _cors_origins == "*" else [o.strip() for o in _cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic models ──────────────────────────────────────────────────────────

class FaultReportRequest(BaseModel):
    customer_name: str
    phone: str
    location: str
    fault_type: str
    urgency: str
    description: str = ""


class AdminLoginRequest(BaseModel):
    password: str


class ChatRatingRequest(BaseModel):
    session_id: str
    stars: int
    comment: str = ""


class MessageFeedbackRequest(BaseModel):
    message_id: int
    session_id: str
    rating: str   # 'helpful' | 'unhelpful'


# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_customer_name(text: str) -> str | None:
    lower = text.lower()
    for marker in ["my name is ", "i am ", "i'm ", "this is "]:
        if marker in lower:
            start = lower.index(marker) + len(marker)
            raw = text[start:].split('\n')[0].split('.')[0].split(',')[0].strip()
            if raw:
                return ' '.join(raw.split()[:3])
    return None


# ─── Auth endpoint ────────────────────────────────────────────────────────────

@app.post("/admin/login")
def admin_login(req: AdminLoginRequest):
    if req.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect password")
    token = secrets.token_hex(32)
    _admin_tokens.add(token)
    return {"token": token}


@app.post("/admin/logout")
def admin_logout(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)):
    if credentials:
        _admin_tokens.discard(credentials.credentials)
    return {"status": "ok"}


# ─── Public endpoints ─────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok", "service": "Kanea AI Support v2"}


@app.get("/outages")
def get_outages():
    return db.get_all_outages()


@app.get("/session/{session_id}/messages")
def get_session_messages(session_id: str):
    """Lets the frontend re-hydrate chat history after a page refresh (same session_id)."""
    rows = db.get_session_messages(session_id)
    return [
        {
            "type": r["sender"],
            "message_id": r["id"],
            "text": r["content"],
            "intent": r["intent"],
        }
        for r in rows
    ]


@app.post("/fault-report")
@limiter.limit("5/minute")
def submit_fault_report(request: Request, req: FaultReportRequest):
    reference = f"FAULT-{secrets.token_hex(4).upper()}"
    db.save_fault_report(
        reference, req.customer_name, req.phone, req.location,
        req.fault_type, req.urgency, req.description
    )
    return {"reference": reference, "status": "submitted"}


@app.post("/chat-rating")
@limiter.limit("10/minute")
def submit_chat_rating(request: Request, req: ChatRatingRequest):
    if not 1 <= req.stars <= 5:
        raise HTTPException(status_code=422, detail="Stars must be 1–5")
    db.save_chat_rating(req.session_id, req.stars, req.comment)
    return {"status": "ok"}


@app.post("/message-feedback")
@limiter.limit("30/minute")
def submit_message_feedback(request: Request, req: MessageFeedbackRequest):
    if req.rating not in ("helpful", "unhelpful"):
        raise HTTPException(status_code=422, detail="Rating must be 'helpful' or 'unhelpful'")
    db.save_message_feedback(req.message_id, req.session_id, req.rating)
    return {"status": "ok"}


# ─── Admin endpoints (token-protected) ───────────────────────────────────────

@app.get("/admin/fault-reports", dependencies=[Depends(require_admin)])
def get_fault_reports():
    return db.get_fault_reports()


@app.get("/admin/escalations", dependencies=[Depends(require_admin)])
def get_escalations():
    return db.get_escalations()


@app.get("/admin/analytics", dependencies=[Depends(require_admin)])
def get_analytics():
    return db.get_analytics()


@app.get("/admin/rag-sources", dependencies=[Depends(require_admin)])
def get_rag_sources():
    return db.get_rag_references()


@app.post("/admin/scrape", dependencies=[Depends(require_admin)])
async def trigger_scrape():
    outages, errors = await asyncio.to_thread(ecg_scraper.scrape_outages)
    if errors and len(errors) == ecg_scraper.TOTAL_PAGES:
        db.log_scrape_failure(errors)
        return {"status": "blocked", "outages_synced": 0, "regions_found": [], "fetch_errors": errors}
    note = f"{len(errors)}/{ecg_scraper.TOTAL_PAGES} pages unreachable" if errors else None
    count = db.sync_ecg_outages(outages, error_detail=note)
    regions = list({o["area"] for o in outages})
    return {"status": "ok", "outages_synced": count, "regions_found": regions, "fetch_errors": errors}


@app.get("/admin/scrape-log", dependencies=[Depends(require_admin)])
def get_scrape_log():
    return db.get_scrape_log()


@app.get("/admin/ecg-outages", dependencies=[Depends(require_admin)])
def get_ecg_outages():
    return db.get_ecg_outages()


@app.post("/admin/seed-demo-outages", dependencies=[Depends(require_admin)])
def seed_demo_outages_endpoint():
    """
    Populate ecg_outages with a hand-built, current-dated demo dataset —
    for use while ECG's site keeps blocking the real scraper (see
    seed_demo_outages.py for the full rationale). Safe to call repeatedly.
    """
    demo_outages = seed_demo_outages.build_demo_outages()
    count = db.sync_ecg_outages(
        demo_outages,
        error_detail="Demo dataset (ECG site blocked by WAF — seeded via /admin/seed-demo-outages)",
    )
    regions = list({o["area"] for o in demo_outages})
    return {"status": "ok", "outages_synced": count, "regions_found": regions}


# ─── WebSocket ────────────────────────────────────────────────────────────────

WELCOME = (
    "Hello! I'm **Kanea**, your AI customer support assistant.\n\n"
    "I can help you with:\n"
    "• Power outage status\n"
    "• Reporting electrical faults\n"
    "• Billing & payment queries\n"
    "• Connecting you to a human agent\n\n"
    "How can I assist you today?"
)

# Simple per-session message rate limit: max 20 messages per minute
_session_msg_times: dict[str, list[float]] = {}

def _is_rate_limited(session_id: str) -> bool:
    import time
    now = time.monotonic()
    times = _session_msg_times.setdefault(session_id, [])
    # Keep only timestamps within the last 60 seconds
    _session_msg_times[session_id] = [t for t in times if now - t < 60]
    if len(_session_msg_times[session_id]) >= 20:
        return True
    _session_msg_times[session_id].append(now)
    return False


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()

    await ws.send_json({
        "type": "bot",
        "text": WELCOME,
        "intent": "general",
        "query_type": "general",
        "quick_replies": ["Check outages", "Report a fault", "Billing enquiry"],
        "escalate": False,
    })

    try:
        while True:
            data = await ws.receive_json()
            user_text: str = data.get("message", "").strip()
            if not user_text:
                continue

            if _is_rate_limited(session_id):
                await ws.send_json({
                    "type": "bot",
                    "text": "You're sending messages too quickly. Please wait a moment.",
                    "intent": "general",
                    "query_type": "static",
                    "quick_replies": [],
                    "escalate": False,
                })
                continue

            await ws.send_json({"type": "user", "text": user_text})
            db.save_message(session_id, "user", user_text)

            outages = db.get_all_outages()
            result = await chatbot.get_bot_response(session_id, user_text, outages)

            bot_message_id = db.save_message(session_id, "bot", result["reply"], result["intent"])
            if result.get("rag_sources"):
                db.save_rag_reference(bot_message_id, session_id, result["rag_sources"])

            if result["escalate"]:
                db.save_escalation(
                    session_id,
                    extract_customer_name(user_text) or "Unknown",
                    result["intent"],
                    user_text,
                )

            await ws.send_json({
                "type": "bot",
                "message_id": bot_message_id,
                "text": result["reply"],
                "intent": result["intent"],
                "query_type": result.get("query_type", "static"),
                "quick_replies": result["quick_replies"],
                "escalate": result["escalate"],
                "rag_sources": result.get("rag_sources", []),
            })

    except WebSocketDisconnect:
        pass
