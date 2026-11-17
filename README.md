# intelligent-email-assistant

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
uv run pytest                             # tests
uv run ruff check . && uv run ruff format .   # lint + format

# Frontend (second terminal)
cd frontend
npm install
npm run dev                               # http://localhost:5173 (proxies /api to :8000)

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

## Docker and the `data/` folder

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
backend/                   FastAPI app + tests (pyproject.toml, uv.lock)
frontend/                  Vite app (served by nginx)
docs/                      Documentation
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
How the frontend reaches the backend, and how the healthcheck works:
[docs/REQUEST_FLOW.md](docs/REQUEST_FLOW.md).
