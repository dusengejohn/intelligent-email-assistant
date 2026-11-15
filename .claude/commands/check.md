---
description: Run all quality checks (lint, format, tests, lockfile) and explain any failures
---

From `backend/`, run each of these and report the result of each:

1. `uv lock --check` — is `uv.lock` in sync with `pyproject.toml`?
2. `uv run ruff check .` — lint
3. `uv run ruff format --check .` — formatting
4. `uv run pytest` — tests

For any failure: explain in plain language what went wrong and why, then ask me
whether you should fix it. Do not fix anything without asking.
