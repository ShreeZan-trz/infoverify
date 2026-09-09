# InfoVerify: Misinformation Detection Platform

An AI-powered platform for detecting and scoring misinformation during crises. Built with FastAPI, PostgreSQL, and SQLAlchemy.

## Features

- **Claim Submission**: Submit disaster/crisis claims for verification
- **Credibility Scoring**: AI-powered multi-dimensional credibility analysis
- **Verification System**: Human verification and audit trails
- **Source Tracking**: Track and score information sources
- **Immutable Audit Logs**: Compliance-ready audit logging
- **Role-Based Access Control**: Admin, Verifier, Analyst, Viewer roles

## Tech Stack

- **Backend**: FastAPI (Python 3.14)
- **Database**: PostgreSQL 18 with SQLAlchemy ORM
- **Authentication**: JWT (coming soon)
- **API Docs**: Swagger UI & ReDoc
- **Deployment**: Railway/Docker ready

## Quick Start

```bash
git clone https://github.com/ShreeZan-trz/infoverify.git
cd infoverify
python3.14 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb disaster_info_db
psql disaster_info_db < infoverify_schema.sql
uvicorn main:app --reload
```

Visit: `http://localhost:8000/docs`

## API Endpoints

- `GET /` - Welcome message
- `GET /health` - Health check
- `GET /api/claims` - List claims
- `POST /api/claims` - Submit claim
- `GET /api/claims/{id}` - Claim details
- `PATCH /api/claims/{id}/verify` - Verify claim
- `GET /api/sources` - List sources

## Case Study: Nepal 2026 Floods

Built in response to the August 2026 Nepal glacier disaster. During the crisis, misinformation spread rapidly while 1000+ died and 4000+ went missing. This platform helps relief organizations verify information during disasters.

## Security Features

✅ Role-based access control (RBAC)
✅ Immutable audit logging
✅ Input validation & sanitization
✅ PostgreSQL constraints
✅ Production-ready architecture

## Future Features

- [ ] JWT authentication
- [ ] React frontend dashboard
- [ ] ML credibility scoring
- [ ] WebSocket real-time updates
- [ ] Docker deployment

## Author

**Shrijan** - Computer Science Student (Cybersecurity)
Texas A&M University–Texarkana

## License

MIT License
