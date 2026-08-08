# Kanea v2.0 - What Changed

## Major Updates

### 1. Separate Admin Application 🎯
**Before:** Admin panel embedded in customer app  
**After:** Standalone admin app on port 5174

New Files:
- `frontend-admin/` - Complete separate React application
- Admin runs independently with no customer code

### 2. JWT Security 🔐
**Before:** Admin endpoints public (only password gate)  
**After:** All admin endpoints require JWT Bearer tokens

New Files:
- `backend/security.py` - JWT token generation and validation

Changes:
- `backend/main.py` - Added `/admin/login` endpoint and token validation
- `backend/requirements.txt` - Added pyjwt, passlib, python-multipart

### 3. Hidden RAG Sources 👁️
**Before:** Slide references visible in customer chat  
**After:** RAG sources only in admin dashboard (JWT protected)

Changes:
- `frontend/src/components/ChatWindow.jsx` - Removed rag_sources display

### 4. Environment Configuration 🔧
**Before:** Secrets hardcoded in code  
**After:** All secrets in `.env` file

New Files:
- `backend/.env.example` - Configuration template

### 5. Documentation 📚
New Files:
- `SETUP.md` - Installation and usage guide
- `SECURITY.md` - Security implementation details
- `CHANGES.md` - This file
- `DEPLOYMENT_CHECKLIST.md` - Production deployment

## Architecture Changes

### Before
```
Customer App + Admin (port 5173)
         ↓
    Backend (8000)
    ✗ No authentication
    ✗ RAG visible to customers
```

### After
```
Customer App (5173) ─────┐
                         ├─→ Backend (8000)
Admin App (5174) ────────┤   ✅ JWT auth on admin routes
                         │   ✅ RAG hidden from customers
                         └─  SQLite
```

## Security Improvements

| Feature | Before | After |
|---------|--------|-------|
| Admin Authentication | Frontend password gate | JWT tokens (backend) |
| RAG Privacy | Visible to customers | Hidden from customers |
| App Separation | Embedded | Standalone |
| CORS | Permissive | Configurable |
| Passwords | Plaintext | Bcrypt hashed |

## New Endpoints

```
POST /admin/login            - Admin login (get JWT)
GET /admin/rag-sources       - View RAG logs (JWT required)
```

## Breaking Changes ⚠️

1. **Admin URL changed**
   - Old: http://localhost:5173/admin
   - New: http://localhost:5174

2. **Admin endpoints require authentication**
   - Must login first to get JWT token
   - Token required in Authorization header

3. **Environment setup required**
   - Must create `.env` file from `.env.example`
   - Must set GROQ_API_KEY

## Upgrade Steps

1. Install dependencies: `pip install -r requirements.txt`
2. Create `.env` file from `.env.example`
3. Set GROQ_API_KEY in `.env`
4. Install frontend-admin: `cd frontend-admin && npm install`
5. Start services on ports 8000, 5173, 5174

## Files Changed Summary

**New:**
- frontend-admin/ (entire directory)
- backend/security.py
- backend/.env.example
- SETUP.md, SECURITY.md, CHANGES.md, DEPLOYMENT_CHECKLIST.md

**Modified:**
- backend/main.py
- backend/requirements.txt
- frontend/src/App.jsx
- frontend/src/components/ChatWindow.jsx

**No changes:**
- backend/chatbot.py
- backend/database.py
- backend/knowledge_base.py
- frontend/src/components/OutageBoard.jsx
- frontend/src/components/FaultForm.jsx
