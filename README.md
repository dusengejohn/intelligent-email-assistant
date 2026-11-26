# intelligent-email-assistant

A small full-stack app for learning AI + modern SDLC: it generates realistic (fictional)
workplace emails with Claude and classifies them by priority (Claude, with keyword rules
as a fallback). A dashboard and calendar planning follow in later epics ([project brief](docs/PROJECT_BRIEF.md)).

## Prerequisites
Developed in WSL (Ubuntu) + VS Code. Install these **inside WSL**, not on Windows:
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh` (installs Python 3.12 for you)
- Node.js 22+ and npm
- [GitHub CLI](https://cli.github.com/) — `sudo apt install gh && gh auth login`
- Docker Desktop with **WSL integration** enabled for your distro (optional, for the full stack)

Clone into the Linux filesystem (e.g. `~/projects/`), not `/mnt/c/...`. Open the folder
in VS Code and accept "Install recommended extensions".

## Quick start

```bash
cp .env.example .env

# Backend
cd backend
uv sync                                   # create .venv + install deps from uv.lock
uv run uvicorn app.main:app --reload      # http://localhost:8000/api/health  (API docs: /docs)
                                          # (Docker stack running? `docker compose stop backend` first: same port)
uv run pytest                             # tests
uv run ruff check . && uv run ruff format .   # lint + format

# Frontend (second terminal)
cd frontend
npm install
npm run dev                               # http://localhost:5173 (proxies /api to :8000)
npm test                                  # frontend unit + component tests (Vitest, React Testing Library)

# Or the full stack (from repo root)
docker compose up --build                 # frontend :8080, backend :8000
```

## Using Claude (API key and cost)

Generating and classifying emails call the **Claude API**, which is **pay-as-you-go** and
billed separately from any claude.ai subscription. Everything else (the list, manual
priorities, tests, CI) works without a key, and classification falls back to keyword rules.

1. In the [Anthropic Console](https://console.anthropic.com): add a few dollars of credit
   (Billing) and **set a monthly spend limit** (Settings → Limits) first.
2. Create an API key just for this project (API Keys → Create Key; it's shown only once).
3. Put it in `.env` at the repo root, which git ignores. **Never commit it.**
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
4. Restart what's running: `docker compose up -d backend`, or restart uvicorn.

| | Cost with `claude-haiku-5-5` |
|---|---|
| Generate 10 emails (1 Claude call, ~15 s) | about **$0.0015** |
| Generate 50 emails (5 calls, ~60–80 s) | about **$0.007** |
| Classify 20 emails (1 call, ~5–10 s) | about **$0.0008** |
| Classify 105 emails (one click = 3 requests, ~26 s) | about **$0.008** |

- Every call logs its tokens: `docker compose logs backend | grep "Claude call"`.
- No key → the app still works; **Generate** shows *"AI is not configured: set
  ANTHROPIC_API_KEY in .env"* (HTTP 503), and **Classify** uses the keyword rules (HTTP 200).
- **Tests and CI never call Claude** and need no key: the AI client is replaced by a fake
  (`backend/tests/fakes.py`), and GitHub has no API key secret on purpose.

**Classify emails:** click **Classify**. One click classifies every unclassified email
(the UI repeats the request, 50 emails at a time). Each card shows a colored priority
badge, its source (`AI`, `rules` or `manual`) and a one-sentence reason. The result line
says how many came from the AI and how many from the rules: **"by rules" while a key is
set means Claude was unreachable** (see the troubleshooting table in
[docs/REQUEST_FLOW.md](docs/REQUEST_FLOW.md)). Change a priority with the dropdown on a
card: it becomes `manual` and is never overwritten by later classifications.

**Measure classifier quality** (manual, never in CI, ~$0.001 per run with a key):
`cd backend && uv run python -m scripts.eval_classifier --runs 3`. Results and caveats:
[docs/testing/epic-2-eval.md](docs/testing/epic-2-eval.md).

**Generate emails:** open http://localhost:8080 (Docker) or http://localhost:5173 (dev),
choose 1–50 and click **Generate emails**; or use the API docs at
http://localhost:8000/docs (`POST /api/emails/generate` → *Try it out*).

**Deliver emails from another service** (`POST /api/emails/ingest`, used by the separate
generator service of Epic 3b): set `INGEST_TOKEN` in `.env` (see `.env.example` for how
to generate one) and send `{"emails": [...]}` (1–50 emails) with the header
`X-Ingest-Token`. Wrong or missing token → 401; `INGEST_TOKEN` not set → 503; any invalid
email → 422 and nothing is saved. Emails arrive unclassified and `new`.

**Run the generator service locally** (Epic 3b, `generator/`; Docker follows in 3b.4):
set `INGEST_TOKEN` in `.env` (one value, read by both services), start the inbox
(`cd backend && uv run uvicorn app.main:app --reload`), then in a second terminal:

```bash
cd generator
uv sync
uv run uvicorn app.main:app --reload --port 8001
curl -X POST localhost:8001/api/generate -H 'Content-Type: application/json' -d '{"count": 10}'
# -> {"generated":10,"delivered":10}; the emails are now in the inbox
```

**The generator's page** (`generator/web/`, React + Vite + Tailwind): in dev run
`npm install && npm run dev` in `generator/web` → http://localhost:5174 (proxies `/api` to
the generator on :8001). Type a count (1–50) and an optional scenario, click **Generate** →
"10 new emails generated and delivered to the inbox" + **Open the inbox**. In the Docker
image FastAPI serves the built page itself at `/` (one container, same origin):

```bash
docker build -t email-generator generator/
docker run --rm -p 8081:8000 --env-file .env \
  -e INBOX_URL=http://host.docker.internal:8000 --add-host host.docker.internal:host-gateway \
  email-generator
# -> http://localhost:8081 (compose wiring follows in story 3b.4)
```

The generator calls Claude (same key, same cost as Generate), then delivers the emails
to `INBOX_URL` (default `http://localhost:8000`). Inbox down or wrong token → HTTP 502
"Generated N emails but … Nothing was delivered." No key or no `INGEST_TOKEN` → 503
before any Claude call.

## Using the inbox

Open http://localhost:8080 (Docker) or http://localhost:5173 (dev). Use a normal browser
(Firefox, Edge, Chrome): VS Code's built-in browser doesn't send the requests that change
data (see `docs/testing/epic-3.md`).

- **Layout:** toolbar on top (Generate, Classify, desktop alerts, health), views on the
  left, the email list in the middle (it scrolls; the column header stays put) and the
  **reading pane** when an email is open (side by side on wide screens; on narrower ones
  it replaces the list, with "Back to list").
- **Order:** new emails before handled ones (handled are greyed out at the bottom);
  within each, unclassified first, then Critical → High → Moderate → Low, newest first.
- **Views** with counts: All, Unclassified, Classified, each priority and the Trash. The
  view is part of the address (`/?view=critical`), so refresh, bookmarks and Back keep it.
  On a narrow window the views are a dropdown above the list.
- **Reading pane:** the full email, its priority, source and reason, and the actions:
  change the priority (becomes `manual`, never overwritten by Classify), Mark handled /
  Mark as new, Re-classify (one Claude call), Delete.
- **Trash:** Delete moves an email to the Trash at once, with an **Undo** toast. In the
  Trash view, open an email to **Restore** it; **Empty trash** deletes everything in it
  permanently and asks first.
- **Alerts:** after Classify, a toast like "1 new critical, 3 new high" with **Show
  critical** appears when new urgent emails were classified. **Enable desktop alerts**
  (top right) adds a system notification when the tab is in the background; the browser
  asks for permission only when you click it.
- **Keyboard:** Tab to a view or a row and press Enter to open it; Esc closes the
  confirmation dialog.

## Database migrations (Alembic)

The database structure is versioned with [Alembic](https://alembic.sqlalchemy.org/)
migrations in `backend/migrations/versions/`. **The backend applies them automatically
at startup** (locally and in Docker), so normally there's nothing to do.

When you change a model in `backend/app/models.py`:

```bash
cd backend
uv run alembic revision --autogenerate -m "add deleted_at to email"   # writes a new file
# read the generated file, then commit it TOGETHER with the model change
uv run alembic upgrade head        # apply now (or just restart the backend)
uv run alembic current             # which version the database is at
uv run alembic history             # all migrations
```

- A test (`tests/test_migrations.py`) fails in CI if the models and the migrations differ.
- A database created before migrations existed is *stamped* at the baseline (`0001`) on
  first start: nothing is recreated and no data is touched.
- Before risky changes, back up the database: `cp data/app.db data/backups/app-$(date +%F).db`
  (`data/` is git-ignored).

## Managing dependencies

```bash
uv add <package>          # runtime dependency
uv add --dev <package>    # test/lint tool
uv remove <package>
```

Commit both `pyproject.toml` and `uv.lock`.

## Docker and the `data/` folder

**Use Docker Desktop only.** If a second Docker Engine is also installed inside
Ubuntu/WSL (`systemctl is-active docker` says `active`), the two engines fight over
ports 8080/8000 and `localhost:8080` can show an old stack that `docker ps` doesn't
list. Turn the WSL engine off once:
`sudo systemctl disable --now docker.service docker.socket containerd.service`,
then check that `docker info --format '{{.Name}}'` prints `docker-desktop`.
Docker Desktop publishes ports on Windows **and inside WSL**: http://localhost:8080
works in your Windows browser and in a WSL terminal. (If `curl localhost:8080` fails in
WSL on your setup, use the Windows host IP: `ip route | awk '/default/ {print $3}'`.)

**Docker and dev mode share port 8000.** While the Docker stack runs, its backend holds
`:8000`, so `uv run uvicorn` fails with *"address already in use"*, and the Vite dev
server (`:5173`) would silently talk to the **Docker** backend (real `.env` key, real
data). Before dev mode, run `docker compose stop backend`; afterwards
`docker compose up -d backend`.

The SQLite database lives in `data/app.db`, shared by local runs and Docker
(`./data` is bind-mounted into the backend container at `/app/data`).

- The backend container runs as a **non-root user with UID 1000**, the default
  WSL/Linux user, so files it creates in `data/` are owned by you.
- If your user ID isn't 1000 (`id -u`), build with
  `docker compose build --build-arg UID=$(id -u) --build-arg GID=$(id -g)`.
- `data/` must exist before `docker compose up` (it does: `data/.gitkeep` is
  committed). Otherwise Docker creates it as root and the app can't write to it.
- **One-time fix** if `data/app.db` was created by an older, root-run container
  (`ls -l data` shows `root`) and local runs fail with *"attempt to write a
  readonly database"*: `rm data/app.db` (the app recreates it; development data
  is lost) or keep the data with `sudo chown $USER:$USER data/app.db`.

## Structure

```
.github/                   CI (backend, generator, frontend, docker jobs), Dependabot, PR/issue templates
backend/app/               FastAPI app: main.py, config, db, models, schemas
  routers/                 API endpoints (health, emails)
  services/                Claude client, prompts, generator, classifier, fallback rules
backend/scripts/           Manual developer tools (classifier eval; never in CI)
backend/migrations/        Alembic database migrations (applied at startup)
backend/tests/             pytest (fakes.py = fake Claude client)
generator/app/             Email generator service (Epic 3b): Claude client, generate, deliver to the inbox
generator/tests/           its pytest suite (fakes: FakeAI, FakeInbox)
generator/web/             its page (React; served by the generator in Docker)
frontend/src/              React app: App.tsx, api.ts (typed API client), priorities.ts, components/
docs/                      Brief, request flow, test checklists (docs/testing/)
data/                      SQLite file (git-ignored)
```

## Automation

| What | When it runs | Config |
|---|---|---|
| Ruff / ESLint auto-fix on Claude's edits | Every time Claude Code edits a backend `.py` or frontend `.ts/.tsx` file | `.claude/settings.json`, `.claude/hooks/` |
| Format / lint on save in VS Code | Every save | `.vscode/settings.json`, `.editorconfig` |
| Pre-commit checks (ruff, eslint, lockfile, tests, secrets) | Every `git commit` | `.pre-commit-config.yaml` |
| CI (same checks, on GitHub) | Every push to `main` / pull request | `.github/workflows/ci.yml` |

One-time setup after cloning: `cd backend && uv sync && uv run pre-commit install`, then
`cd ../frontend && npm install`.

Claude Code slash commands: `/story <issue>`, `/new-endpoint <description>`,
`/explain <file or concept>`, `/check`, `/pr <issue>`.

Project requirements and working agreement: [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md).
How the frontend reaches the backend, the healthcheck, and the generate flow (with
timeouts): [docs/REQUEST_FLOW.md](docs/REQUEST_FLOW.md). End-to-end test logs:
[docs/testing/epic-1.md](docs/testing/epic-1.md), [docs/testing/epic-2.md](docs/testing/epic-2.md).
