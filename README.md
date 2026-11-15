# intelligent-email-assistant

## Prerequisites
- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you)
- Docker (optional, for the full stack)

## Quick start

```bash
cp .env.example .env

# Backend
cd backend
uv sync                                   # create .venv + install deps from uv.lock
uv run uvicorn app.main:app --reload      # http://localhost:8000/health  (API docs: /docs)
uv run pytest                             # tests
uv run ruff check . && uv run ruff format .   # lint + format

# Or the full stack (from repo root)
docker compose up --build                 # frontend :8080, backend :8000
```

## Managing dependencies

```bash
uv add <package>          # runtime dependency
uv add --dev <package>    # test/lint tool
uv remove <package>
```

Commit both `pyproject.toml` and `uv.lock`.

## Structure

```
.github/workflows/ci.yml   CI: lint, format check, tests
backend/                   FastAPI app + tests (pyproject.toml, uv.lock)
frontend/                  Vite app (served by nginx)
docs/                      Documentation
data/                      SQLite file (git-ignored)
```

## Automation

| What | When it runs | Config |
|---|---|---|
| Ruff format + lint on Claude's edits | Every time Claude Code edits a backend `.py` file | `.claude/settings.json`, `.claude/hooks/` |
| Pre-commit checks (lint, format, lockfile, tests, secrets) | Every `git commit` | `.pre-commit-config.yaml` |
| CI (same checks, on GitHub) | Every push to `main` / pull request | `.github/workflows/ci.yml` |

One-time setup after cloning: `cd backend && uv sync && uv run pre-commit install`

Claude Code slash commands: `/new-endpoint <description>`, `/explain <file or concept>`, `/check`.
