# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Layout
- `backend/` — FastAPI app (`app/main.py`), tests in `backend/tests/`. Managed with **uv**.
- `frontend/` — Vite app served by nginx in Docker; `/api/` is proxied to the backend.
- `data/` — SQLite database file (git-ignored).
- `docs/` — project documentation.

## Commands (run from `backend/`)
- Install / sync deps: `uv sync`
- Dev server: `uv run uvicorn app.main:app --reload`
- Tests: `uv run pytest`
- Lint: `uv run ruff check .` (auto-fix: `--fix`)
- Format: `uv run ruff format .`
- Full stack (from repo root): `docker compose up --build`

## Conventions
- Never use pip or edit requirements files — they don't exist. Add deps with
  `uv add <pkg>` (runtime) or `uv add --dev <pkg>` (test/lint tools).
- Always commit `uv.lock` together with `pyproject.toml` changes.
- Pytest and ruff config live in `backend/pyproject.toml`.
- CI fails on lint errors, unformatted code, or a stale `uv.lock` — run
  `ruff check`, `ruff format` and `pytest` before committing.
- Copy `.env.example` to `.env` for local config; never commit `.env`.
