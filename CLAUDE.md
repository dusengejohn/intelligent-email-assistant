# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Layout
- `backend/` — FastAPI app, managed with **uv**:
  - `app/main.py` (app, routers under `/api`, error handlers, logging), `config.py`,
    `db.py`, `models.py` (tables), `schemas.py` (API + AI shapes), `priorities.py`
    (brief §7 as code: the single source for priority meanings, colors, default minutes);
  - `app/routers/` — endpoints (`health.py`, `emails.py`);
  - `app/services/` — `ai_client.py` (the only Claude caller), `prompts.py`,
    `generator.py`, `fallback.py` (rule-based classifier, no AI), `errors.py`;
  - `tests/` mirrors `app/`; `tests/fakes.py` holds the shared `FakeAI`;
    `tests/data/labelled_emails.py` is the hand-labelled set for classifier tests.
- `frontend/` — React + Vite + TypeScript + Tailwind, served by nginx in Docker; `/api/` is
  proxied to the backend (by Vite in dev, by nginx in Docker). `src/api.ts` is the typed
  API client (Vitest: `src/api.test.ts`); UI pieces live in `src/components/`.
- `data/` — SQLite database file (git-ignored).
- `docs/` — project documentation; manual end-to-end checklists in `docs/testing/`.

## Commands (run from `backend/`)
- Install / sync deps: `uv sync`
- Dev server: `uv run uvicorn app.main:app --reload`
- Tests: `uv run pytest`
- Lint: `uv run ruff check .` (auto-fix: `--fix`)
- Format: `uv run ruff format .`
- Full stack (from repo root): `docker compose up --build`

## Commands (run from `frontend/`)
- Install deps: `npm install` (CI uses `npm ci`)
- Dev server: `npm run dev` (http://localhost:5173, proxies `/api` → :8000)
- Lint: `npm run lint` · Tests: `npm test` (Vitest) · Build (type-check + bundle): `npm run build`

## Conventions
- Never use pip or edit requirements files — they don't exist. Add deps with
  `uv add <pkg>` (runtime) or `uv add --dev <pkg>` (test/lint tools).
- Always commit `uv.lock` together with `pyproject.toml` changes.
- Pytest and ruff config live in `backend/pyproject.toml`.
- CI fails on lint errors, unformatted code, or a stale `uv.lock` — run
  `ruff check`, `ruff format` and `pytest` before committing.
- Copy `.env.example` to `.env` for local config; never commit `.env`.
- Claude is called **only** through `backend/app/services/ai_client.py` (`AIClient.parse`);
  tests pass a fake SDK client (`sdk_client=`) and never use the network or a real key.

## Automation
- PostToolUse hooks auto-fix every file you edit: `ruff_after_edit.py` (backend
  `.py`) and `eslint_after_edit.py` (frontend `.ts/.tsx`). If they report errors,
  fix them before moving on.
- Pre-commit (`.pre-commit-config.yaml`) runs lint, format, lockfile and test
  checks on `git commit`. Never bypass it with `--no-verify` unless asked.
- Custom commands live in `.claude/commands/`: `/story <issue>`, `/new-endpoint`,
  `/explain`, `/check`, `/pr <issue>`.
- GitHub work goes through the `gh` CLI (issues, PRs, CI status).

## Project brief
Requirements, architecture, working agreement and Definition of Done:
@docs/PROJECT_BRIEF.md
