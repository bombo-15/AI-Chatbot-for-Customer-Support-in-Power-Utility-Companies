import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "chatbot.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            intent TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS message_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            rating TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            stars INTEGER NOT NULL,
            comment TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fault_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            location TEXT NOT NULL,
            fault_type TEXT NOT NULL,
            urgency TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'open',
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS outages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            type TEXT NOT NULL,
            start_time TEXT NOT NULL,
            estimated_restoration TEXT,
            affected_customers INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            cause TEXT
        );

        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            customer_name TEXT,
            intent TEXT,
            last_message TEXT,
            status TEXT DEFAULT 'pending',
            timestamp TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rag_references (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            sources TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ecg_outages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT NOT NULL,
            type TEXT NOT NULL,
            start_time TEXT NOT NULL,
            estimated_restoration TEXT,
            affected_customers INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            cause TEXT,
            source_title TEXT,
            scraped_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ecg_scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scraped_at TEXT NOT NULL,
            total_outages INTEGER NOT NULL,
            regions TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 1,
            error_detail TEXT
        );
        """)

        # Migrate older databases created before error_detail existed.
        try:
            conn.execute("ALTER TABLE ecg_scrape_log ADD COLUMN error_detail TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

        # Seed sample outages if table is empty
        row = conn.execute("SELECT COUNT(*) FROM outages").fetchone()
        if row[0] == 0:
            now = datetime.now().isoformat()
            conn.executemany(
                "INSERT INTO outages (area, type, start_time, estimated_restoration, affected_customers, status, cause) VALUES (?,?,?,?,?,?,?)",
                [
                    ("Accra Central", "unplanned", "2026-03-16T08:00:00", "2026-03-16T16:00:00", 3200, "active", "High-voltage line fault"),
                    ("Tema Industrial", "scheduled", "2026-03-17T06:00:00", "2026-03-17T14:00:00", 870, "scheduled", "Routine maintenance"),
                    ("Kumasi North", "unplanned", "2026-03-15T22:00:00", "2026-03-16T12:00:00", 1500, "active", "Transformer overload"),
                    ("East Legon", "scheduled", "2026-03-18T09:00:00", "2026-03-18T17:00:00", 420, "scheduled", "Network upgrade"),
                    ("Takoradi Port", "unplanned", "2026-03-14T10:00:00", "2026-03-14T18:00:00", 950, "resolved", "Cable fault repaired"),
                ]
            )


# ──────────────── Messages ────────────────

def save_message(session_id: str, sender: str, content: str, intent: str | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO messages (session_id, sender, content, intent, timestamp) VALUES (?,?,?,?,?)",
            (session_id, sender, content, intent, datetime.now().isoformat())
        )
        return cur.lastrowid


def get_session_messages(session_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_session_history_for_chat(session_id: str, max_turns: int = 4) -> list[dict]:
    """
    Reconstruct LLM-compatible conversation history from the messages table.
    Used to restore context after a server restart.
    """
    messages = get_session_messages(session_id)
    history = []
    for msg in messages:
        if msg["sender"] == "user":
            history.append({"role": "user", "content": msg["content"]})
        elif msg["sender"] == "bot":
            history.append({"role": "assistant", "content": msg["content"]})
    # Return the last max_turns * 2 messages (user + bot pairs)
    return history[-(max_turns * 2):]


# ──────────────── Feedback ────────────────

def save_message_feedback(message_id: int, session_id: str, rating: str) -> None:
    """rating: 'helpful' | 'unhelpful'"""
    with get_conn() as conn:
        # Upsert: one feedback per message
        existing = conn.execute(
            "SELECT id FROM message_feedback WHERE message_id=? AND session_id=?",
            (message_id, session_id)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE message_feedback SET rating=?, timestamp=? WHERE id=?",
                (rating, datetime.now().isoformat(), existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO message_feedback (message_id, session_id, rating, timestamp) VALUES (?,?,?,?)",
                (message_id, session_id, rating, datetime.now().isoformat())
            )


def save_chat_rating(session_id: str, stars: int, comment: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_ratings (session_id, stars, comment, timestamp) VALUES (?,?,?,?)",
            (session_id, stars, comment, datetime.now().isoformat())
        )


# ──────────────── Analytics ────────────────

def get_analytics() -> dict:
    with get_conn() as conn:
        total_sessions = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM messages WHERE sender='user'"
        ).fetchone()[0]

        total_messages = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE sender='user'"
        ).fetchone()[0]

        # Satisfaction
        rating_rows = conn.execute(
            "SELECT stars FROM chat_ratings"
        ).fetchall()
        ratings = [r["stars"] for r in rating_rows]
        avg_satisfaction = round(sum(ratings) / len(ratings), 2) if ratings else 0

        # Feedback accuracy (helpful messages / total feedback)
        fb_rows = conn.execute(
            "SELECT rating, COUNT(*) as cnt FROM message_feedback GROUP BY rating"
        ).fetchall()
        fb_map = {r["rating"]: r["cnt"] for r in fb_rows}
        helpful = fb_map.get("helpful", 0)
        unhelpful = fb_map.get("unhelpful", 0)
        total_fb = helpful + unhelpful
        accuracy = round(helpful / total_fb * 100, 1) if total_fb > 0 else None

        # Escalation rate
        escalations = conn.execute("SELECT COUNT(*) FROM escalations").fetchone()[0]
        escalation_rate = round(escalations / total_sessions * 100, 1) if total_sessions > 0 else 0

        # Intent distribution
        intent_rows = conn.execute(
            "SELECT intent, COUNT(*) as cnt FROM messages WHERE sender='bot' AND intent IS NOT NULL GROUP BY intent ORDER BY cnt DESC"
        ).fetchall()
        intent_dist = [{"intent": r["intent"], "count": r["cnt"]} for r in intent_rows]

        # Satisfaction distribution
        sat_dist = {}
        for r in rating_rows:
            sat_dist[str(r["stars"])] = sat_dist.get(str(r["stars"]), 0) + 1

        # Recent ratings
        recent_ratings = conn.execute(
            "SELECT stars, comment, timestamp FROM chat_ratings ORDER BY id DESC LIMIT 10"
        ).fetchall()

        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "avg_satisfaction": avg_satisfaction,
            "total_ratings": len(ratings),
            "accuracy_percent": accuracy,
            "helpful_count": helpful,
            "unhelpful_count": unhelpful,
            "escalation_rate": escalation_rate,
            "total_escalations": escalations,
            "intent_distribution": intent_dist,
            "satisfaction_distribution": sat_dist,
            "recent_ratings": [dict(r) for r in recent_ratings],
        }


# ──────────────── Fault Reports ────────────────

def save_fault_report(reference: str, customer_name: str, phone: str, location: str,
                      fault_type: str, urgency: str, description: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO fault_reports (reference, customer_name, phone, location, fault_type, urgency, description, timestamp) VALUES (?,?,?,?,?,?,?,?)",
            (reference, customer_name, phone, location, fault_type, urgency, description, datetime.now().isoformat())
        )


def get_fault_reports(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM fault_reports ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ──────────────── Outages ────────────────

def get_outages() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM outages ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def add_outage(area: str, type_: str, start_time: str, est_restoration: str,
               affected: int, status: str, cause: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO outages (area, type, start_time, estimated_restoration, affected_customers, status, cause) VALUES (?,?,?,?,?,?,?)",
            (area, type_, start_time, est_restoration, affected, status, cause)
        )
        return cur.lastrowid


# ──────────────── Escalations ────────────────

def save_escalation(session_id: str, customer_name: str, intent: str, last_message: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO escalations (session_id, customer_name, intent, last_message, timestamp) VALUES (?,?,?,?,?)",
            (session_id, customer_name, intent, last_message, datetime.now().isoformat())
        )


def get_escalations(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM escalations ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def save_rag_reference(message_id: int, session_id: str, sources: list[dict]) -> None:
    if not sources:
        return
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO rag_references (session_id, message_id, sources, timestamp) VALUES (?,?,?,?)",
            (session_id, message_id, json.dumps(sources, ensure_ascii=False), datetime.now().isoformat())
        )


def get_rag_references(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM rag_references ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        results = []
        for r in rows:
            item = dict(r)
            item['sources'] = json.loads(item['sources']) if item['sources'] else []
            results.append(item)
        return results


# ──────────────── ECG Live Outages ────────────────

def sync_ecg_outages(outages: list[dict], error_detail: str | None = None) -> int:
    """
    Replace all scraped ECG outages with a fresh batch and log the run as a
    success. Only call this when the scrape reached ECG's site at all — a
    fully-blocked scrape (e.g. every page returned HTTP 403) should call
    log_scrape_failure() instead, so we don't wipe out the last known-good
    outage data just because the site's WAF had a bad hour.
    Returns the number of outages inserted.
    """
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM ecg_outages")
        conn.executemany(
            """INSERT INTO ecg_outages
               (area, type, start_time, estimated_restoration,
                affected_customers, status, cause, source_title, scraped_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [
                (
                    o["area"],
                    o["type"],
                    o["start_time"],
                    o.get("estimated_restoration"),
                    o.get("affected_customers", 0),
                    o["status"],
                    o.get("cause"),
                    o.get("source_title", ""),
                    now,
                )
                for o in outages
            ],
        )
        regions = json.dumps(list({o["area"] for o in outages}))
        conn.execute(
            "INSERT INTO ecg_scrape_log (scraped_at, total_outages, regions, success, error_detail) VALUES (?,?,?,1,?)",
            (now, len(outages), regions, error_detail),
        )
    return len(outages)


def log_scrape_failure(fetch_errors: list[dict]) -> None:
    """
    Record a scrape run that could not reach ECG's site at all (every page
    fetch failed — WAF block, DNS/timeout, outage, etc). Deliberately does
    NOT touch the ecg_outages table, so the board keeps showing the last
    known-good data instead of going blank because of a transient block.
    """
    now = datetime.now().isoformat()
    detail = "; ".join(f"{e['url']}: {e['reason']}" for e in fetch_errors[:3])
    if len(fetch_errors) > 3:
        detail += f" (+{len(fetch_errors) - 3} more)"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ecg_scrape_log (scraped_at, total_outages, regions, success, error_detail) VALUES (?,0,'[]',0,?)",
            (now, detail),
        )


def get_ecg_outages() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ecg_outages ORDER BY scraped_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_outages() -> list[dict]:
    """Return seeded outages plus live ECG scraped outages."""
    seeded = get_outages()
    live = get_ecg_outages()
    return seeded + live


def get_scrape_log(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ecg_scrape_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        results = []
        for r in rows:
            item = dict(r)
            try:
                item["regions"] = json.loads(item["regions"])
            except Exception:
                pass
            results.append(item)
        return results
