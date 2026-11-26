# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Layout
- `backend/` — FastAPI app, managed with **uv**:
  - `app/main.py` (app, routers under `/api`, error handlers, logging), `config.py`,
    `db.py`, `models.py` (tables), `schemas.py` (API + AI shapes), `priorities.py`
    (brief §7 as code: the single source for priority meanings, colors, default minutes);
  - `app/routers/` — endpoints (`health.py`, `emails.py`);
  - `app/services/` — `ai_client.py` (the only Claude caller), `prompts.py`,
    `classifier.py` (AI in batches + per-email fallback),
    `fallback.py` (rule-based classifier, no AI), `errors.py`;
  - `migrations/` + `alembic.ini` — Alembic database migrations, applied at startup by
    `app/db.py` `migrate_database()` (existing pre-Alembic databases are stamped at `0001`);
  - `scripts/` — developer tools run by hand, never in CI (`uv run python -m scripts.<name>`),
    e.g. `eval_classifier.py` (AI vs rules accuracy; calls the real API);
  - `tests/` mirrors `app/`; `tests/fakes.py` holds the shared `FakeAI`;
    `tests/data/labelled_emails.py` is the hand-labelled set for classifier tests.
- `generator/` — the **Email Generator** service (Epic 3b), a separate uv project with its own
  `pyproject.toml`/`uv.lock`: `app/routers/generate.py` (`POST /api/generate`),
  `app/services/` — `ai_client.py` + `errors.py` (**copies** of the inbox's; fix bugs in both),
  `generator.py`, `prompts.py`, `inbox.py` (`InboxClient`: delivers to the inbox's
  `/api/emails/ingest` with `X-Ingest-Token`; the only caller of the inbox). No database.
  Emails may be at most 47 h old (inbox: 48 h) so they're still valid on delivery.
  Tests: `tests/fakes.py` has `FakeAI` and `FakeInbox` (`httpx.MockTransport`), no network.
  `generator/web/` is its page (React + Vite + TS + Tailwind, Vitest; same setup as `frontend/`);
  `app/main.py` `create_app()` serves the built page from `static/` at `/` when it exists (Docker),
  after `/api` (unknown `/api/...` = JSON 404). `generator/Dockerfile` is multi-stage (Node builds
  the page, Python serves page + API), non-root. `VITE_INBOX_URL` (build time) = the inbox link.
- `frontend/` — React + Vite + TypeScript + Tailwind, served by nginx in Docker; `/api/` is
  proxied to the backend (by Vite in dev, by nginx in Docker). `src/api.ts` is the typed
  API client (Vitest: `src/api.test.ts`); UI pieces live in `src/components/`. Component tests
  use React Testing Library in a simulated browser: a file opts in with
  `// @vitest-environment jsdom` (others run in Node); shared setup in `src/test-setup.ts`.
  The list header and rows share one grid template (`src/components/columns.ts`).
  `src/views.ts` is the single table of sidebar views (label, API filter, summary count);
  the selected view lives in the URL (`?view=critical`, History API for Back/Forward).
  `ReadingPane` holds the per-email actions; `Toast` (reusable, auto-hides, optional action
  such as Undo) and `ConfirmDialog` (only for irreversible actions) are shared components;
  `src/selection.ts` picks the next email when the open one leaves the view.
  Alerts for new critical/high emails follow Classify and are counted from the classify
  response (`src/alerts.ts`); desktop notifications go only through `src/notifications.ts`
  (opt-in by click, shown only when the tab is hidden; the toast always appears).
  `HealthPill` re-checks `/api/health` every 15 s (new-mail polling stays quiet on errors).
  `src/priorities.ts` mirrors `app/priorities.py` (labels, colors); the backend test
  `tests/test_frontend_priorities_sync.py` fails if they drift apart.
- `data/` — SQLite database file (git-ignored).
- `docs/` — project documentation; manual end-to-end checklists in `docs/testing/`; decision
  records (ADRs) in `docs/decisions/` (numbered, never rewritten; a new decision supersedes).

## Commands (run from `backend/`)
- Install / sync deps: `uv sync`
- Dev server: `uv run uvicorn app.main:app --reload`
- Tests: `uv run pytest`
- Lint: `uv run ruff check .` (auto-fix: `--fix`)
- Format: `uv run ruff format .`
- Full stack (from repo root): `docker compose up --build` → inbox :8080, inbox API :8000,
  generator :8081 (delivers to `http://backend:8000` on the compose network);
  wiring check: `bash .github/scripts/compose_smoke.sh` (CI runs it in the `docker` job)

## Commands (run from `generator/`)
- Same as `backend/`: `uv sync`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`
- Dev server: `uv run uvicorn app.main:app --reload --port 8001` (delivers to `INBOX_URL`,
  default `http://localhost:8000`; needs `INGEST_TOKEN` and `ANTHROPIC_API_KEY`)
- Page (from `generator/web/`): `npm install`, `npm run dev` (:5174, proxies `/api` → :8001),
  `npm run lint`, `npm test`, `npm run build`

## Commands (run from `frontend/`)
- Install deps: `npm install` (CI uses `npm ci`)
- Dev server: `npm run dev` (http://localhost:5173, proxies `/api` → :8000)
- Lint: `npm run lint` · Tests: `npm test` (Vitest) · Build (type-check + bundle): `npm run build`

## Conventions
- Never use pip or edit requirements files — they don't exist. Add deps with
  `uv add <pkg>` (runtime) or `uv add --dev <pkg>` (test/lint tools).
- Always commit `uv.lock` together with `pyproject.toml` changes.
- **Model changes need a migration:** `uv run alembic revision --autogenerate -m "…"` from
  `backend/`, read the generated file, commit it with the model change. Migrations must not
  import `app` code (plain `sa.*` types only); `tests/test_migrations.py` catches drift.
- Pytest and ruff config live in `backend/pyproject.toml`.
- CI fails on lint errors, unformatted code, or a stale `uv.lock` — run
  `ruff check`, `ruff format` and `pytest` before committing.
- Copy `.env.example` to `.env` for local config; never commit `.env`.
- Claude is called **only** through `backend/app/services/ai_client.py` (`AIClient.parse`);
  tests pass a fake SDK client (`sdk_client=`) and never use the network or a real key.
- **Soft delete:** trashed emails (`deleted_at` set) must stay invisible. New queries in
  `routers/emails.py` filter with `_active()`; single-email actions use `_get_or_404()`.
- **Manual browser checks:** use a normal browser (Firefox/Edge/Chrome, not VS Code's built-in
  one, which drops POST/PATCH/DELETE) and confirm each step in the nginx log
  (`docker compose logs frontend`, user agent shows the browser); prefer `--tail` over `--since`.
- AI features **with** a fallback depend on `get_optional_ai_client` (no key → `None` → fallback,
  HTTP 200). The inbox has no AI feature **without** a fallback since Generate moved to
  `generator/` (3b.5); a new one (e.g. Epic 5) needs a strict dependency again (no key → 503).
- **The inbox never generates:** emails arrive via `POST /api/emails/ingest` (validated with
  `IncomingEmail`). The page notices them by polling `/summary` (`src/arrivals.ts`: new mail =
  `all + trash` went up; deletes/restores don't count).

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
