# Security Implementation - Kanea AI Chatbot v2.0

## What's Implemented

### 1. JWT Token Authentication ✅
- Admin endpoints require Bearer tokens
- Tokens expire after 24 hours
- Generated via `/admin/login` endpoint
- Token validation on every admin request

### 2. Password Hashing ✅
- Bcrypt one-way password hashing
- Automatic salt generation
- Secure password comparison

### 3. Application Separation ✅
- Customer app (port 5173) completely separate
- Admin app (port 5174) runs independently
- No admin code in customer application

### 4. RAG Source Privacy ✅
- Slide references NOT shown in customer chat
- RAG sources only in admin dashboard (JWT protected)
- Sources logged internally for audit trail

### 5. CORS Protection ✅
- Whitelist of allowed origins
- Configurable via `.env` file
- Blocks unauthorized cross-origin requests

### 6. Environment Configuration ✅
- All secrets in `.env` (not hardcoded)
- `.env.example` provided as template
- `.env` excluded from version control

## Admin Login Flow

```
User enters credentials → Backend validates → Bcrypt verify
    ↓
Create JWT token (24-hour expiration) → Return to frontend
    ↓
Frontend stores in sessionStorage → Add to Authorization header
    ↓
Admin makes request with JWT → Backend validates token
    ↓
If valid: Execute request, If invalid: Return 401 Unauthorized
```

## Environment Variables

```env
# LLM Configuration
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Security (CHANGE IN PRODUCTION!)
JWT_SECRET=your-very-long-random-secret-key-change-this
ADMIN_PASSWORD=kanea2026

# CORS Configuration
CORS_ORIGINS=http://localhost:5173,http://localhost:5174

# Other
ENVIRONMENT=development
```

## Default Admin Credentials

- **Email:** admin@kanea.local
- **Password:** kanea2026 (change in `.env` file)

⚠️ **Production:** Change these values immediately!

## API Endpoints

### Public Endpoints
```
GET /                    - Health check
GET /outages            - List active outages
POST /fault-report      - Submit fault report
WS /ws/{session_id}     - Chat WebSocket
```

### Admin Endpoints (JWT Required)
```
POST /admin/login                - Get JWT token
GET /admin/fault-reports         - View all faults
GET /admin/escalations           - View escalations
GET /admin/analytics             - View metrics
GET /admin/rag-sources           - View RAG logs
```

## Security Testing

### Test Admin Login
```bash
curl -X POST http://localhost:8000/admin/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@kanea.local","password":"kanea2026"}'
```

### Test Protected Endpoint
```bash
curl -X GET http://localhost:8000/admin/fault-reports \
  -H "Authorization: Bearer <your_token_here>"
```

### Test Without Token (Should fail)
```bash
curl -X GET http://localhost:8000/admin/fault-reports
# Response: 403 Forbidden
```

## Production Recommendations

- [ ] Change `JWT_SECRET` to 32+ character random string
- [ ] Change `ADMIN_PASSWORD` or use secrets manager
- [ ] Enable HTTPS/TLS for all connections
- [ ] Configure `CORS_ORIGINS` for production domain only
- [ ] Add rate limiting on API endpoints
- [ ] Implement input sanitization
- [ ] Set up audit logging for admin actions
- [ ] Use PostgreSQL instead of SQLite
- [ ] Move admin credentials to secure vault
- [ ] Enable WebSocket TLS (WSS)

## Files Modified

- `backend/security.py` - NEW (JWT + password utilities)
- `backend/main.py` - Added JWT auth, login endpoint
- `backend/requirements.txt` - Added pyjwt, passlib
- `frontend-admin/src/components/AdminPanel.jsx` - JWT login
- `frontend/src/components/ChatWindow.jsx` - RAG sources hidden
