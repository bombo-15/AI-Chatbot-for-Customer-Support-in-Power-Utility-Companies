# Deployment Checklist - Kanea v2.0

## Local Development Setup

### Backend
- [ ] Python 3.11+ installed
- [ ] Virtual environment created: `python -m venv venv`
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] `.env` file created from `.env.example`
- [ ] ANTHROPIC_API_KEY added to `.env`
- [ ] Backend starts without errors: `uvicorn main:app --reload`

### Frontend
- [ ] Node.js 16+ installed
- [ ] Customer app: `cd frontend && npm install`
- [ ] Admin app: `cd frontend-admin && npm install`
- [ ] Customer app runs: `npm run dev`
- [ ] Admin app runs: `npm run dev`

### Testing
- [ ] Customer app loads at http://127.0.0.1:5173
- [ ] Admin app loads at http://127.0.0.1:5174
- [ ] Chat WebSocket works (test sending a message)
- [ ] Admin login succeeds (admin@kanea.local / kanea2026)
- [ ] RAG sources NOT visible in customer chat ✅
- [ ] RAG sources visible in admin dashboard ✅
- [ ] Fault report submission works
- [ ] Outage board displays correctly

## Production Deployment

### Before Deployment
- [ ] All tests passing
- [ ] Code reviewed for security
- [ ] Environment file configured
- [ ] Database backup plan in place
- [ ] Monitoring setup ready

### Security Hardening
- [ ] `JWT_SECRET` changed to random 32+ character string
- [ ] `ADMIN_PASSWORD` changed from default
- [ ] `ENVIRONMENT` set to "production"
- [ ] `CORS_ORIGINS` set to production domain only
- [ ] HTTPS/TLS enabled for all endpoints
- [ ] WebSocket TLS (WSS) enabled

### Backend Deployment
- [ ] Code deployed to production server
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] `.env` file created with production values
- [ ] Database initialized
- [ ] Uvicorn configured with production settings
- [ ] Backend service starts and stays running

### Frontend Deployment
- [ ] Customer app built: `npm run build`
- [ ] Admin app built: `npm run build`
- [ ] Built files deployed to static hosting
- [ ] API endpoint URLs updated to production backend
- [ ] HTTPS enabled for both apps
- [ ] CDN configured (if applicable)

### Database
- [ ] SQLite backup configured
- [ ] Database encryption enabled (if applicable)
- [ ] Connection pooling configured
- [ ] Backup tested and verified

### Monitoring & Logging
- [ ] Error logging configured
- [ ] Performance monitoring enabled
- [ ] Uptime monitoring configured
- [ ] Admin login attempts logged
- [ ] Failed authentication attempts logged

### Post-Deployment
- [ ] Health check endpoint responding
- [ ] Admin can login
- [ ] Customer can chat
- [ ] No errors in logs
- [ ] Database queries working
- [ ] Backups running on schedule

## Rollback Plan

If issues occur, rollback steps:
1. Stop all services
2. Restore previous database backup
3. Restore previous code version
4. Restart services
5. Verify functionality

## Troubleshooting

**Backend won't start:**
- Check port 8000 not in use: `netstat -ano | findstr :8000`
- Check `.env` file exists with ANTHROPIC_API_KEY
- Check database permissions
- Review error logs

**Admin login fails:**
- Verify email is `admin@kanea.local`
- Verify password in `.env` matches
- Check backend is running
- Check network connectivity

**Chat WebSocket fails:**
- Verify backend on port 8000
- Check CORS_ORIGINS includes frontend port
- Check firewall allows WebSocket
- Verify WebSocket URL correct in code

**Database locked:**
- Stop all instances
- Restart backend
- Check no other processes using database

## Monitoring

Monitor these metrics:
- API response time (should be < 500ms)
- Database query time (should be < 100ms)
- WebSocket connection stability
- Admin login success rate
- Error rate (should be < 0.1%)
- Storage usage (database size)

## Maintenance Schedule

- **Daily:** Review error logs, verify backups
- **Weekly:** Check performance metrics, update dependencies
- **Monthly:** Security audit, performance analysis
- **Quarterly:** Disaster recovery test, capacity planning
