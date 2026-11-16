---
description: Run all quality checks (lint, format, tests, lockfile) and explain any failures
---

Run each of these and report the result of each:

From `backend/`:
1. `uv lock --check` — is `uv.lock` in sync with `pyproject.toml`?
2. `uv run ruff check .` — lint
3. `uv run ruff format --check .` — formatting
4. `uv run pytest` — tests

From `frontend/`:
5. `npm run lint` — ESLint
6. `npm run build` — TypeScript type-check + production bundle

For any failure: explain in plain language what went wrong and why, then ask me
whether you should fix it. Do not fix anything without asking.
