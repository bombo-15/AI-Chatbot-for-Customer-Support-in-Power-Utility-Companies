"""
AI chatbot engine for PowerGrid Customer Support (Kanea).

Decision logic:
  Step 1 — Classify intent (keyword NLP pre-filter)
  Step 2 — Route query type: STATIC → RAG knowledge base | DYNAMIC → live outage data
  Step 3 — Build context-aware system prompt and generate response via the Claude API
"""

import os
import anthropic

import knowledge_base
import database as db

# Claude API (Anthropic). Requires billing at console.anthropic.com — no
# perpetual free tier — but Haiku 4.5 is cheap enough that this chatbot's
# volume costs cents, not dollars. Chosen over the prior OpenRouter free
# model for its stronger instruction-following (concise answers, no
# unit/number relabeling) — see Kanea_LLM_Migration_Evaluation_Report.pdf.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = "claude-haiku-4-5"

MAX_HISTORY = 4
MAX_TOKENS  = 600

# Retry budget for transient Claude API failures (429 rate limit / 5xx
# upstream overload / network hiccup). Kept small — this blocks a live chat
# reply. The SDK itself performs the retries (with backoff, honoring any
# Retry-After header) — this just caps how many it's allowed.
MAX_RETRIES = 2   # 1 initial try + 2 SDK-managed retries

# ─── Intent taxonomy ─────────────────────────────────────────────────────────

INTENT_KEYWORDS: dict[str, list[str]] = {
    "outage_status": [
        "power", "outage", "blackout", "electricity", "no light", "light off",
        "supply", "when will", "restore", "restoration", "interruption", "off",
        "no electricity", "cut", "load shedding", "dumsor", "current status",
        "is there power", "power back", "power cut", "voltage",
    ],
    "fault_report": [
        "report", "fault", "broken", "fallen", "pole", "wire", "spark", "danger",
        "damage", "leak", "equipment", "transformer", "cable", "streetlight",
        "burning", "fire", "snapped", "electric shock", "low voltage",
    ],
    "billing": [
        "bill", "payment", "pay", "invoice", "charge", "meter", "tariff",
        "overcharge", "estimate", "credit", "debit", "prepaid", "token",
        "balance", "recharge", "vend", "account", "apply", "connection",
    ],
    "safety": [
        "safe", "safety", "surge", "danger", "hazard", "shock", "protect",
        "avoid", "precaution", "what should i do", "is it safe",
    ],
    "escalation": [
        "human", "agent", "representative", "person", "speak to", "call me",
        "manager", "supervisor", "urgent", "emergency", "help me",
        "want to talk", "real person", "connect me",
    ],
    "complaint": [
        "complain", "complaint", "angry", "frustrated", "terrible", "bad",
        "unacceptable", "always", "never", "poor", "worst", "useless",
        "disappointed", "disgusted", "awful",
    ],
    "general": [],
}

# Intents that require LIVE data from the outage database
_DYNAMIC_INTENTS = {"outage_status"}

# Phrases that force dynamic routing even if intent is ambiguous
_DYNAMIC_PHRASES = {
    "outage", "blackout", "no power", "no light", "no electricity",
    "restoration", "restore", "when will power", "load shedding", "dumsor",
    "planned maintenance", "maintenance schedule", "live update",
    "current status", "is there power", "power cut", "power back",
    "any outage", "scheduled outage", "power interruption",
}

# Concrete hazard phrases: always treat as danger, regardless of phrasing.
CONCRETE_DANGER_PHRASES = [
    "electric shock", "fallen wire", "fallen pole", "live wire", "sparking",
    "snapped wire", "smoking", "fire", "smoke", "on fire", "caught fire",
    "smells of burning", "burning smell", "immediate danger", "urgent help",
    "injury", "life-threatening", "electrocution",
]

# Word pairs that describe a concrete hazard even with other words in between
# (e.g. "a fallen electric pole" doesn't contain the literal phrase "fallen pole").
_CONCRETE_DANGER_WORD_PAIRS = [
    ("fallen", "pole"), ("fallen", "wire"), ("snapped", "wire"), ("broken", "pole"),
]

# Generic/abstract hazard words: only count as danger when NOT part of a
# hypothetical or FAQ-style question (e.g. "is it safe to..." "what hazards should I avoid").
SOFT_DANGER_WORDS = ["unsafe", "danger", "hazard"]

_HYPOTHETICAL_PATTERNS = [
    "is it safe", "is it dangerous", "what should i do", "what hazards",
    "what precautions", "how can i", "how do i avoid", "how do i protect",
    "what if",
]

QUICK_REPLIES: dict[str, list[str]] = {
    "outage_status": ["Check my area", "Restoration time?", "Report a fault"],
    "fault_report":  ["Submit fault form", "Speak to agent", "Track my report"],
    "billing":       ["View my bill", "Pay online", "Dispute a charge"],
    "safety":        ["Report hazard", "Emergency line", "Speak to agent"],
    "escalation":    ["Call +233(0302) 611 611", "Leave a message", "Track my case"],
    "complaint":     ["Speak to agent", "Submit feedback", "Check outages"],
    "general":       ["Power outages", "Report a fault", "Billing enquiry"],
}

# ─── In-memory session store ──────────────────────────────────────────────────

_sessions: dict[str, list[dict]] = {}

# ─── Step 1: Intent classification ───────────────────────────────────────────

def classify_intent(text: str) -> str:
    """Keyword-based NLP pre-classifier. Scores each intent by keyword hits."""
    lower = text.lower()
    scores: dict[str, int] = {intent: 0 for intent in INTENT_KEYWORDS}
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                scores[intent] += 1
    scored = {k: v for k, v in scores.items() if k != "general" and v > 0}
    if not scored:
        return "general"
    return max(scored, key=lambda k: scores[k])


def classify_query_type(intent: str, text: str) -> str:
    """
    Step 2 routing decision.
    Returns:
      'dynamic'    — query needs live outage / maintenance data
      'static'     — query answered from RAG knowledge base
      'escalation' — route to human agent
    """
    lower = text.lower()

    # Escalation takes priority
    if intent == "escalation" or any(kw in lower for kw in INTENT_KEYWORDS["escalation"]):
        return "escalation"

    # Dynamic: outage / restoration / maintenance / live updates
    if intent in _DYNAMIC_INTENTS or any(phrase in lower for phrase in _DYNAMIC_PHRASES):
        return "dynamic"

    # Everything else (billing, safety, complaint, fault procedure, general) → RAG
    return "static"


def is_danger_message(text: str) -> bool:
    lower = text.lower()
    if any(phrase in lower for phrase in CONCRETE_DANGER_PHRASES):
        return True
    if any(a in lower and b in lower for a, b in _CONCRETE_DANGER_WORD_PAIRS):
        return True
    if any(pattern in lower for pattern in _HYPOTHETICAL_PATTERNS):
        return False
    return any(word in lower for word in SOFT_DANGER_WORDS)

# ─── Context builders ─────────────────────────────────────────────────────────

def _build_rag_context(user_message: str, query_type: str) -> tuple[str, list[dict]]:
    """
    For static queries fetch more docs (top_n=5).
    For dynamic queries fetch fewer docs (top_n=2) as supplemental background only.
    """
    top_n = 5 if query_type == "static" else 2
    docs = knowledge_base.retrieve_relevant_docs(user_message, top_n=top_n)
    if not docs:
        return "", []

    source_label = "KNOWLEDGE BASE (ECG + PURC)" if query_type == "static" else "SUPPLEMENTAL BACKGROUND"
    parts = [f"{source_label}:"]
    for i, doc in enumerate(docs, 1):
        src_tag = f"[{doc.get('source', 'knowledge')}:{doc['id']}]"
        parts.append(f"Source {i} {src_tag}: {doc['text']}")
    return "\n\n".join(parts), docs


def _format_outage_list(outages: list[dict]) -> str:
    lines = []
    for o in outages:
        if o.get("status") == "resolved":
            continue
        restoration = o.get("estimated_restoration") or "TBD"
        affected = o.get("affected_customers") or "unknown number of"
        source = o.get("source_title", "")
        line = (
            f"  • {o['area']} — {o['type'].upper()} | "
            f"Status: {o['status']} | "
            f"Restoration: {restoration} | "
            f"Cause: {o.get('cause', 'Unknown')} | "
            f"Affected customers: {affected}"
        )
        if source:
            line += f"\n    Details: {source[:150]}"
        lines.append(line)
    return "\n".join(lines) if lines else "  No active outages recorded at this time."


def _build_system_prompt(
    outages: list[dict],
    rag_context: str,
    query_type: str,
) -> str:
    outage_text = _format_outage_list(outages)

    # Routing instruction differs by query type
    if query_type == "dynamic":
        routing_instruction = (
            "The customer is asking about a DYNAMIC topic (outage, restoration, maintenance, live status).\n"
            "→ Answer ONLY from the LIVE OUTAGE DATA below. Do not invent or assume outage information.\n"
            "→ If the customer's area is not listed, tell them no active outage is recorded for that area.\n"
            "→ Reference specific areas, causes, and restoration times where available."
        )
    elif query_type == "static":
        routing_instruction = (
            "The customer is asking a STATIC topic (billing, tariff, meter, safety, procedure, FAQ).\n"
            "→ Answer from the KNOWLEDGE BASE provided below (ECG procedures and PURC-approved tariffs).\n"
            "→ Cite specific procedures, fees, tariff rates, or contact numbers where relevant, including the tariff's effective date if quoting a rate.\n"
            "→ Do not speculate; if information is not in the knowledge base, say so and direct them to 0302 611 611."
        )
    else:  # escalation
        routing_instruction = (
            "The customer requires HUMAN AGENT assistance.\n"
            "→ Acknowledge their request, provide the emergency/support line, and end with [ESCALATE_TO_AGENT]."
        )

    return f"""You are Kanea, the AI customer support assistant for ECG (Electricity Company of Ghana).

ROUTING DECISION: {routing_instruction}

─── LIVE OUTAGE DATA (scraped from ecg.com.gh) ───
{outage_text}

─── {("KNOWLEDGE BASE (ECG + PURC)" if query_type == "static" else "SUPPLEMENTAL BACKGROUND")} ───
{rag_context if rag_context else "  (No relevant knowledge base entries for this query.)"}

─── RESPONSE RULES ───
1. Be concise, empathetic, and professional (under 120 words unless detail is essential).
2. Never invent outage data, prices, or procedures not provided above.
3. For safety hazards (fallen wire, electric shock, fire): immediately advise the customer to stay away and call 0302 611 611, then add [ESCALATE_TO_AGENT].
4. Add [ESCALATE_TO_AGENT] ONLY when:
   - Customer is in physical danger
   - Customer explicitly asks for a human agent / manager
   - The same issue has been unresolved across 3+ messages
5. Do NOT add [ESCALATE_TO_AGENT] for routine queries.

Emergency / general support line: 0302 611 611
"""

# ─── Step 3: Generate response ────────────────────────────────────────────────

async def get_bot_response(
    session_id: str,
    user_message: str,
    outages: list[dict],
) -> dict:
    """
    Returns:
      reply         : str   — clean response text
      intent        : str   — classified intent label
      query_type    : str   — 'static' | 'dynamic' | 'escalation'
      quick_replies : list  — suggested follow-up buttons
      escalate      : bool  — whether to route to human agent
      rag_sources   : list  — knowledge base docs used
    """
    # Step 1: classify intent
    intent = classify_intent(user_message)

    # Step 2: route query type
    query_type = classify_query_type(intent, user_message)

    quick_replies = QUICK_REPLIES.get(intent, QUICK_REPLIES["general"])
    force_escalate = is_danger_message(user_message) or query_type == "escalation"

    # Build context based on route
    rag_context, rag_sources = _build_rag_context(user_message, query_type)

    # Restore history from DB if this session is new to this process (e.g. after restart)
    if session_id not in _sessions:
        _sessions[session_id] = db.get_session_history_for_chat(session_id, max_turns=MAX_HISTORY)

    history = _sessions[session_id]
    history.append({"role": "user", "content": user_message})
    if len(history) > MAX_HISTORY * 2:
        history[:] = history[-(MAX_HISTORY * 2):]

    # ── No API key fallback ───────────────────────────────────────────────────
    if not ANTHROPIC_API_KEY:
        reply = (
            "The AI service is not configured yet. "
            "Please set ANTHROPIC_API_KEY in your .env file. "
            "Get a key at https://console.anthropic.com/settings/keys"
        )
        history.append({"role": "assistant", "content": reply})
        return {
            "reply": reply, "intent": intent, "query_type": query_type,
            "quick_replies": quick_replies, "escalate": False, "rag_sources": [],
        }

    # ── Call the Claude API ────────────────────────────────────────────────────
    system_prompt = _build_system_prompt(outages, rag_context, query_type)

    technical_issue = False
    raw_reply = ""

    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY, max_retries=MAX_RETRIES)
        response = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=history,
        )
        raw_reply = next((b.text for b in response.content if b.type == "text"), "")
    except anthropic.APIError as e:
        # Covers everything the SDK raises here: RateLimitError / APIStatusError
        # (bad request, auth, invalid model, upstream 5xx, ...) and
        # APIConnectionError — the SDK already retried transient failures
        # (MAX_RETRIES) before raising, so any of these is a genuine failure.
        # All of them get the same friendly fallback below rather than a
        # stack trace, since none are something the customer caused — but log
        # the real cause so it's diagnosable instead of silently swallowed.
        print(f"[chatbot] Claude API call failed ({type(e).__name__}): {e}")

    if not raw_reply:
        # Technical/rate-limit failure — NOT the same as the customer needing a
        # human agent, so this must not silently set [ESCALATE_TO_AGENT].
        technical_issue = True
        raw_reply = (
            "I'm having a technical issue right now. "
            "Please call 0800-POWER (0800-76937) for immediate assistance."
        )

    escalate = force_escalate or (not technical_issue and "[ESCALATE_TO_AGENT]" in raw_reply)
    clean_reply = raw_reply.replace("[ESCALATE_TO_AGENT]", "").strip()
    history.append({"role": "assistant", "content": clean_reply})

    return {
        "reply": clean_reply,
        "intent": intent,
        "query_type": query_type,
        "quick_replies": quick_replies,
        "escalate": escalate,
        "rag_sources": rag_sources,
    }


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
