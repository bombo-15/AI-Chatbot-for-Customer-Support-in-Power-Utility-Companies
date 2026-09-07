# Security — Kanea AI Chatbot

This document describes the security measures **actually implemented** in the
current codebase (verified against `backend/main.py`, `backend/chatbot.py`,
`backend/requirements.txt`, and both frontend apps) — not an aspirational or
planned design. An earlier version of this file described a JWT + bcrypt
admin-auth system that was never built (no `pyjwt` or `passlib` dependency
exists in `requirements.txt`); this version replaces that with what is
genuinely running in production.

## 1. Admin authentication

- `POST /admin/login` accepts a single shared password (no email/username —
  the field is just `password`), compared directly against the `ADMIN_PASSWORD`
  environment variable (`backend/main.py`). This is a **plain string
  comparison, not a hashed password check** — there is no bcrypt/argon2 in
  this codebase.
- On success, a random 32-byte token is generated with Python's `secrets.token_hex(32)`
  (cryptographically secure) and added to an **in-memory set** (`_admin_tokens`).
  This is a bearer token, not a JWT — it carries no claims, has no built-in
  expiry, and is *not* persisted to the database.
  - Practical effect: every admin session is invalidated whenever the backend
    process restarts (every deploy, and every free-tier inactivity spin-down
    on Render) — there is no "stay logged in" beyond that.
- `require_admin()` is a FastAPI dependency that checks the `Authorization:
  Bearer <token>` header against that in-memory set on every admin-only
  route; a missing or unrecognized token returns `401`.
- **No hardcoded fallback password.** If `ADMIN_PASSWORD` is not set in the
  environment, the app generates a random one at startup and logs it — it
  does **not** fall back to a fixed value baked into the source code (an
  earlier version of this codebase did exactly that, which meant the
  "secret" was visible to anyone reading the public GitHub repo; this was
  removed).
- Both the stored value and the incoming login attempt are `.strip()`'d
  before comparison, specifically because a hosting dashboard silently
  appending a trailing newline to a pasted secret is a real, observed
  failure mode, not a hypothetical one.

## 2. Rate limiting

Implemented with `slowapi`, keyed per client IP, on every public write
endpoint:

| Endpoint | Limit |
|---|---|
| `POST /fault-report` | 5/minute |
| `POST /chat-rating` | 10/minute |
| `POST /message-feedback` | 30/minute |

The `/admin/*` routes and the `/ws/{session_id}` chat endpoint are **not**
rate-limited (see Known Limitations).

## 3. CORS

`CORSMiddleware` restricts cross-origin requests to an explicit allow-list
read from the `CORS_ORIGINS` environment variable (comma-separated). Requests
from origins not on that list receive no `Access-Control-Allow-Origin`
header, so browsers block them client-side even though the server itself
still processes the request (standard CORS behavior — this is enforced by
the browser, not the server refusing the connection).

## 4. Secrets management

- All secrets (`ANTHROPIC_API_KEY`, `ADMIN_PASSWORD`, `CORS_ORIGINS`) are read
  from environment variables via `os.getenv()` / `python-dotenv`, never
  hardcoded in source (see §1 for the one historical exception, now fixed).
- `.env` is gitignored; `.env.example` ships with placeholder values only
  (`change-me-before-deploying`, etc.) so a fresh clone can't accidentally
  inherit a real secret.
- In deployment, secrets live in the hosting platform's own environment
  variable store (Render's Environment tab / Environment Groups; Vercel's
  Project Environment Variables) — not in the repository at any point.

## 5. Frontend output sanitization (XSS)

The customer chat renders the model's response as HTML (to support basic
markdown-style formatting), which is a real XSS surface if left unsanitized.
`frontend/src/components/ChatWindow.jsx` passes all bot output through
**DOMPurify** before rendering, restricted to a small allow-list of tags:

```js
DOMPurify.sanitize(html, { ALLOWED_TAGS: ['strong', 'em', 'br', 'ul', 'li', 'p'] })
```

Anything outside that allow-list (`<script>`, event handler attributes,
`<img onerror>`, etc.) is stripped before it ever reaches the DOM.

## 6. RAG source privacy

Which knowledge-base documents were retrieved to ground a given answer is
logged for audit purposes but is **not** shown to customers in the chat UI —
it's only visible in the admin dashboard's RAG Sources tab (itself behind
the admin token from §1). This avoids exposing internal document naming/
structure to the public while keeping the retrieval decision auditable.

## 7. Application separation

The customer-facing app (`frontend/`) and the internal admin dashboard
(`frontend-admin/`) are two entirely separate builds/deployments with no
shared client-side code path — the customer bundle contains no admin
routes, login form, or admin-only fetch calls to leak in its JS.

## 8. Input validation

All request bodies are typed Pydantic models (`FaultReportRequest`,
`ChatRatingRequest`, `MessageFeedbackRequest`, `AdminLoginRequest`) — FastAPI
rejects malformed JSON or wrong types with a `422` before the handler body
ever runs. `chat-rating` and `message-feedback` additionally hand-check their
constrained fields (`1 <= stars <= 5`, `rating in ("helpful", "unhelpful")`).

---

## Known limitations (not yet addressed)

Documented honestly rather than omitted — these are real, current gaps:

- **Single shared admin password, not per-user accounts.** Anyone with the
  one password has full admin access; there's no way to tell which admin did
  what, or to revoke one person's access without changing it for everyone.
- **WebSocket chat endpoint (`/ws/{session_id}`) has no authentication at
  all** and is not rate-limited — anyone can open a connection and send
  messages, which both consumes Claude API quota and is the one path not
  covered by the REST rate limits in §2.
- **Admin tokens are in-memory only.** Besides invalidating on every
  restart (§1), there's also no way to explicitly list or revoke a specific
  active session short of restarting the whole service.
- **No audit log of *admin* actions** (who viewed what, when) — only the
  RAG-retrieval log (§6) and the data admins can *view* (escalations, fault
  reports) are recorded; actions taken *by* an admin are not.
- **SQLite on Render's free tier is ephemeral** — it resets on every deploy
  and on inactivity spin-down. This is a data-durability issue more than a
  security one, but it's worth knowing alongside everything else here.
- **No HTTPS enforcement at the application layer** — TLS is provided by the
  hosting platforms (Render, Vercel) terminating at their edge, not by
  anything in this codebase; there's no HSTS header or scheme-redirect logic
  of our own.

## Recommendations, in priority order

1. Add authentication (even a lightweight session/token check) to the
   WebSocket endpoint, and rate-limit it — it's currently the least
   protected path into the system and the one most directly tied to API
   cost.
2. Move from a single shared `ADMIN_PASSWORD` to per-user accounts if more
   than one person needs admin access, so actions and access can be
   attributed and individually revoked.
3. Add a persistent token store (even just a DB table) if admin sessions
   surviving a restart becomes a real annoyance rather than an accepted
   trade-off.
4. If this moves beyond a demo/coursework deployment, replace the ephemeral
   SQLite setup with a durable hosted database and add real audit logging
   for admin actions.
