# intelligent-email-assistant

A small full-stack app for learning AI + modern SDLC: it generates realistic (fictional)
workplace emails with Claude and lists them. Classification, a dashboard and calendar
planning follow in later epics ([project brief](docs/PROJECT_BRIEF.md)).

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
npm test                                  # frontend unit tests (Vitest)

# Or the full stack (from repo root)
docker compose up --build                 # frontend :8080, backend :8000
```

## Using Claude (API key and cost)

Generating emails calls the **Claude API**, which is **pay-as-you-go** and billed separately
from any claude.ai subscription. Everything else (the list, tests, CI) works without a key.

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

- Every call logs its tokens: `docker compose logs backend | grep "Claude call"`.
- No key → the app still works; **Generate** shows *"AI is not configured: set
  ANTHROPIC_API_KEY in .env"* (HTTP 503).
- **Tests and CI never call Claude** and need no key: the AI client is replaced by a fake
  (`backend/tests/fakes.py`), and GitHub has no API key secret on purpose.

**Measure classifier quality** (manual, never in CI, ~$0.001 per run with a key):
`cd backend && uv run python -m scripts.eval_classifier --runs 3`. Results and caveats:
[docs/testing/epic-2-eval.md](docs/testing/epic-2-eval.md).

**Generate emails:** open http://localhost:8080 (Docker) or http://localhost:5173 (dev),
choose 1–50 and click **Generate emails**; or use the API docs at
http://localhost:8000/docs (`POST /api/emails/generate` → *Try it out*).

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
.github/                   CI (backend, frontend, docker jobs), Dependabot, PR/issue templates
backend/app/               FastAPI app: main.py, config, db, models, schemas
  routers/                 API endpoints (health, emails)
  services/                Claude client, prompts, email generator
backend/tests/             pytest (fakes.py = fake Claude client)
frontend/src/              React app: App.tsx, api.ts (typed API client), components/
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
timeouts): [docs/REQUEST_FLOW.md](docs/REQUEST_FLOW.md). Epic 1 end-to-end test log:
[docs/testing/epic-1.md](docs/testing/epic-1.md).
