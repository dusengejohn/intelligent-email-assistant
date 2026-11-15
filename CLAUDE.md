# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Layout
- `backend/` — FastAPI app (`app/main.py`), tests in `backend/tests/`.
- `frontend/` — Vite app served by nginx in Docker; `/api/` is proxied to the backend.
- `data/` — SQLite database file (git-ignored).
- `docs/` — project documentation.

## Commands
- Backend dev: `cd backend && pip install -r requirements-dev.txt && uvicorn app.main:app --reload`
- Tests: `cd backend && pytest`
- Lint: `cd backend && ruff check .`
- Full stack: `docker compose up --build`

## Conventions
- Runtime deps go in `requirements.txt`; test/lint tools in `requirements-dev.txt`.
- Copy `.env.example` to `.env` for local config; never commit `.env`.
