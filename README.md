# intelligent-email-assistant

## Quick start

```bash
cp .env.example .env

# Backend
cd backend
pip install -r requirements-dev.txt
uvicorn app.main:app --reload   # http://localhost:8000/health
pytest

# Or the full stack
docker compose up --build       # frontend :8080, backend :8000
```

## Structure

```
.github/workflows/ci.yml   CI pipeline
backend/                   FastAPI app + tests
frontend/                  Vite app (served by nginx)
docs/                      Documentation
data/                      SQLite file (git-ignored)
```
