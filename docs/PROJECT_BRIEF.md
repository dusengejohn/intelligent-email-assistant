# Project Brief — Intelligent Email Assistant

> **Purpose of this file:** the single source of truth for *what* this project must do,
> *why*, and *how* it is built. Claude Code: read this before planning any work.
> Owner: John Dusenge · Repo: `dusengejohn/intelligent-email-assistant` · Last updated: 2026-11-15

---

## 1. Why this project exists

- **Learning goal (primary):** I am a developer/IT-infrastructure person taking my first
  practical steps into AI. This project teaches me how to (a) call an LLM from code,
  (b) get reliable **structured output** from it, (c) combine AI with normal deterministic
  code, and (d) ship it with a modern SDLC: Git branching, PRs, tests, Docker, CI/CD.
- **Product goal:** a small full-stack web app that helps a busy person triage email:
  it generates sample emails, classifies them by priority with AI, highlights what needs
  attention, and suggests when to answer them based on calendar availability.
- **Final goal:** a working, containerized app deployed to the cloud, built through
  GitHub Issues → branches → PRs → green CI → automated image build and deploy.

## 2. How Claude should work with me (working agreement)

1. **I am learning.** Explain *why*, not just *what*. Name the concept (e.g. "dependency
   injection", "multi-stage build") and explain it briefly in plain words.
2. **Plan first.** For any story, show a short plan (files to change, approach, tests)
   and wait for my OK before writing code.
3. **Small steps.** One user story per branch/PR. Keep diffs small and reviewable.
4. **Test first where practical.** Every endpoint and every piece of logic gets a pytest test.
5. **Never call the real Anthropic API (or any network) in tests or CI** — mock it.
6. **Follow repo rules in `CLAUDE.md`** (uv only, ruff, pre-commit, never `--no-verify`).
7. **Never commit secrets.** Config comes from environment variables / `.env`.
8. **Ask when a requirement is ambiguous** instead of guessing; suggest a sensible default.
9. Update `README.md` / `CLAUDE.md` / this file when setup, commands or decisions change.

## 3. Architecture

```
Browser (React SPA)
   │  fetch("/api/...")
   ▼
nginx (frontend container :80, host :8080)  ── serves static build, proxies /api/* ──┐
                                                                                    ▼
                                                     FastAPI backend (container :8000)
                                                       ├── SQLite  (./data/app.db, volume)
                                                       ├── Anthropic Claude API (generate, classify, advise)
                                                       ├── Calendar source (mock JSON/.ics → Google/Outlook later)
                                                       ├── Open-Meteo (weather, no key)
                                                       └── RSS feeds (news)
```

- **Dev mode:** `uv run uvicorn app.main:app --reload` (:8000) + `npm run dev` (:5173,
  Vite proxies `/api` → :8000).
- **Docker mode:** `docker compose up --build` → frontend :8080, backend :8000.
- **Rule:** every backend route lives under the **`/api`** prefix (FastAPI `APIRouter(prefix="/api")`);
  nginx passes the path through unchanged (`proxy_pass http://backend:8000;` — no trailing slash).

## 4. Tech stack & conventions

| Area | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, `pydantic-settings` for config |
| Python tooling | **uv** (`pyproject.toml` + `uv.lock`), ruff (lint + format), pytest, pre-commit |
| Persistence | SQLite via **SQLModel** (or SQLAlchemy 2.x); file at `data/app.db` |
| AI | Official `anthropic` Python SDK; model name from env `ANTHROPIC_MODEL` |
| HTTP clients | `httpx` (weather), `feedparser` (RSS) |
| Frontend | React + Vite + TypeScript, Tailwind CSS; plain `fetch` (no heavy state libs) |
| Containers | Backend: python:3.12-slim + uv; Frontend: node:22-alpine build → nginx:alpine |
| CI/CD | GitHub Actions; images to GitHub Container Registry (GHCR) |
| Dev environment | WSL (Ubuntu) + VS Code (WSL extension) + Claude Code extension; Docker Desktop |

Backend layout target:

```
backend/app/
  main.py            # FastAPI app, includes routers
  config.py          # Settings (pydantic-settings, reads env)
  db.py              # engine/session, create tables
  models.py          # SQLModel tables
  schemas.py         # request/response models
  routers/           # emails.py, calendar.py, planning.py, widgets.py, health.py
  services/          # ai_client.py, generator.py, classifier.py, fallback.py, planner.py, weather.py, news.py
backend/tests/       # mirrors services/ and routers/
```

## 5. Configuration (environment variables)

| Variable | Example | Notes |
|---|---|---|
| `APP_ENV` | `development` | |
| `DATABASE_URL` | `sqlite:///./data/app.db` | |
| `ANTHROPIC_API_KEY` | *(secret)* | Optional at startup; AI features return a clear error / fallback if missing |
| `ANTHROPIC_MODEL` | a current Haiku-class model | Cheap + fast is enough; verify current model names in Anthropic docs |
| `APP_TIMEZONE` | `America/Toronto` | Used by calendar planning |
| `WORK_HOURS` | `09:00-17:00` | Working window for suggestions |
| `WEATHER_CITY` | `Toronto` | |
| `NEWS_FEEDS` | comma-separated RSS URLs | |

All listed in `.env.example` with placeholder values. Real values only in `.env` (git-ignored)
and GitHub/hosting secrets.

## 6. Domain model

**Email**
| Field | Type | Notes |
|---|---|---|
| id | int PK | |
| sender_name, sender_email | str | |
| subject, body | str | |
| received_at | datetime (tz-aware) | |
| priority | enum `critical/high/moderate/low` \| null | null = not yet classified |
| priority_reason | str \| null | one sentence |
| classification_source | enum `ai/fallback/manual` \| null | |
| suggested_response_minutes | int \| null | estimated effort to reply |
| status | enum `new/handled` | default `new` |
| created_at | datetime | |

**CalendarEvent** (read-only input): `id, title, start, end` (tz-aware). Mock source:
`backend/app/data/calendar_mock.json` first.

## 7. Priority definitions (shared by AI prompt, fallback rules and UI)

| Priority | Meaning / typical signals | Respond within | UI color |
|---|---|---|---|
| **Critical** | Outage, security incident, legal/compliance, exec escalation, deadline today | ~2 h | Red `#DC2626` |
| **High** | Customer issue, manager request, deadline ≤ 48 h, blocked colleague | Same day | Orange `#EA580C` |
| **Moderate** | Normal work requests, meeting coordination, reviews | 2–3 days | Yellow `#CA8A04` |
| **Low** | FYI, newsletters, automated notifications, social | Whenever | Green `#16A34A` |

Sort order everywhere: Critical → High → Moderate → Low, then newest first.

## 8. Functional requirements by epic

### Epic 0 — Project setup & DevOps foundation (in progress)
- Monorepo: `backend/`, `frontend/`, `docs/`, `data/`, `.github/workflows/`.
- `GET /api/health` → `{"status":"ok"}` with a test.
- React page shows backend health; `docker compose up --build` runs both services.
- CI jobs: `backend` (uv sync --locked, ruff check, ruff format --check, pytest),
  `frontend` (npm ci, lint, build), `docker` (compose build; needs the other two).
- `main` protected: PR required + all three checks green.

### Epic 1 — Email generation (AI)
- `POST /api/emails/generate` body `{ "count": 1..50, "scenario"?: str }`.
- Backend asks Claude for a **JSON array** of realistic workplace emails covering a mix
  of priorities (sender_name, sender_email, subject, body, received_at within last 48 h).
- Output **validated with Pydantic**; invalid items rejected, never saved half-broken.
- Saved to SQLite; returns created emails. Missing API key → HTTP 503 with clear message.
- `GET /api/emails?priority=&status=` and `GET /api/emails/{id}`.

### Epic 2 — Priority classification (AI + fallback)
- `POST /api/emails/classify` classifies all unclassified emails (also `/api/emails/{id}/classify`).
- AI returns per email: `{ "priority", "reason", "suggested_response_minutes" }` — validated.
- **Fallback classifier** (pure Python keyword/rule based) used when the API is missing,
  fails, times out, or returns invalid output → `classification_source = "fallback"`.
- `PATCH /api/emails/{id}` with `{priority?, status?}`; changing priority sets source `manual`.
- Tests: fallback classifier on fixed sample emails gives expected priorities; AI client mocked.

### Epic 3 — Dashboard & notifications (frontend)
- Email list sorted by priority, color-coded (left border/badge), with reason shown.
- Summary panel: count per priority (from `GET /api/emails/summary` → `{critical, high, moderate, low, unclassified}`).
- Filters by priority/status; "Mark handled" button.
- Toast + optional browser Notification (Notification API, permission requested) when new
  Critical/High emails appear after generate/classify.
- Buttons: "Generate emails", "Classify".

### Epic 4 — Calendar-based response planning (advice only)
- `GET /api/calendar/events?date=YYYY-MM-DD` (mock source first; Google Calendar / Microsoft Graph later).
- `GET /api/planning/suggestions?date=` returns suggested slots:
  1. Deterministic code: within `WORK_HOURS` in `APP_TIMEZONE`, merge busy events,
     compute free gaps ≥ 15 min.
  2. Allocate unhandled emails in priority order using `suggested_response_minutes`
     (defaults: critical 15, high 15, moderate 10, low 5); Critical gets the earliest slot;
     Low emails batched together; flag emails that do not fit today.
  3. Optional: Claude turns the slot plan into a short human-readable recommendation.
- **Never creates or modifies calendar events.**
- Free-slot algorithm fully unit tested with fixed events.

### Epic 5 — Extra widgets
- `GET /api/widgets/weather` — Open-Meteo (geocode `WEATHER_CITY`, current + today forecast), cached ~15 min.
- `GET /api/widgets/news` — top 5 items from `NEWS_FEEDS` (title, link, source, date).
- `GET /api/brief` — Claude summary (≤150 words) of: email counts + top urgent subjects,
  today's free time, weather.
- Any external failure → widget shows "unavailable"; page never crashes.

### Epic 6 — CI/CD & deployment
- `release.yml`: on push to `main`, build backend + frontend images, push to
  `ghcr.io/dusengejohn/intelligent-email-assistant-{backend,frontend}` tagged `sha` and `latest`.
- On tag `v*.*.*`: deploy to a container host (candidates: Render, Fly.io, Azure Container
  Apps — decision pending); secrets only in GitHub Secrets / host settings.
- Post-deploy smoke test: `GET /api/health` returns ok.
- Dependabot for pip/uv, npm, GitHub Actions and Docker base images.

## 9. AI design rules

- One small wrapper (`services/ai_client.py`) owns the Anthropic client, model, timeout
  (~30 s), retries (1), and JSON parsing — routers never call the SDK directly.
- Prompts live in code as constants (or `services/prompts.py`), are short, and specify the
  **exact JSON schema** expected. Parse → validate with Pydantic → on failure use fallback.
- Keep cost low: cheap model, `count ≤ 50`, classify in batches, no AI calls on page load
  except `/api/brief` (cache it).
- Data is synthetic (generated emails); connecting a real mailbox is **out of scope** for now.

## 10. Non-functional requirements

- Type hints everywhere; ruff clean; formatted; tests pass locally and in CI.
- Graceful degradation: every external dependency (Claude, weather, news, calendar) can
  fail without breaking the app.
- Logging with Python `logging` (no secrets in logs).
- Reproducible builds: `uv.lock` + `package-lock.json` committed; CI uses `--locked` / `npm ci`.
- Containers: small images, dependency layers cached, no dev tools in production images.

## 11. Definition of Done (every story)

1. All acceptance criteria met and demonstrated locally.
2. Work on a feature branch, merged to `main` via PR (description contains `Closes #<issue>`).
3. CI green (backend, frontend, docker).
4. New logic has tests; no real network calls in tests.
5. No secrets committed; `.env.example` updated if new config was added.
6. README / CLAUDE.md / this brief updated if behaviour, commands or decisions changed.
7. I (John) have read and understood the code.

## 12. Current status (2026-11-15)

- ✅ Repo structure, README, CLAUDE.md, `.gitignore`, `.env.example`, `.gitattributes`
- ✅ Backend: `GET /api/health` (under `APIRouter(prefix="/api")`) + test; uv/pyproject/uv.lock; ruff config
- ✅ Automation: Claude Code PostToolUse ruff hook, slash commands (`/new-endpoint`,
  `/explain`, `/check`), pre-commit (lint, format, lock check, pytest, secret detection)
- ✅ Backend Dockerfile (uv), docker-compose, backend CI job
- ✅ Frontend: React/Vite/TS scaffold; page shows backend health; Vite dev proxy `/api` → :8000
- ✅ Frontend Dockerfile on `node:22-alpine` + `.dockerignore`; nginx keeps `/api` prefix + SPA fallback
- ✅ Dev environment: WSL-native clone, uv and gh installed in WSL; brief imported into `CLAUDE.md`
- ⏳ Tooling PR: VS Code recommended extensions, frontend lint in hooks, `.env.example`, `/story` + `/pr` commands
- ⏳ CI: add `frontend` and `docker` jobs, PR/issue templates, Dependabot; then protect `main`
- ⏳ Docker Desktop WSL integration (daemon not reachable from WSL) → verify `docker compose up --build`

## 13. Roadmap

| Iteration | Scope |
|---|---|
| 1 | Finish Epic 0 |
| 2 | Epic 1 — generation + DB |
| 3 | Epic 2 — classification + fallback; Epic 3 basic dashboard |
| 4 | Epic 3 notifications/filters; Epic 4 with mock calendar |
| 5 | Epic 5 widgets + daily brief; optional real calendar integration |
| 6 | Epic 6 release pipeline + cloud deployment; polish docs |

## 14. Out of scope (for now)

Reading/sending real email, writing to a real calendar, user accounts/auth, multi-user
support, mobile app. Revisit after Epic 6.
