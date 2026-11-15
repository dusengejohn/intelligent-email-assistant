---
description: Scaffold a new FastAPI endpoint (router + models + tests), test-first
argument-hint: <what the endpoint should do, e.g. "GET /emails returns a list of emails">
---

Add a new backend endpoint for: $ARGUMENTS

Follow these steps in order and pause where indicated:

1. **Plan** — Briefly state the HTTP method, path, request/response shapes, and
   which files you will create or change. Keep the design minimal.
2. **Test first** — Write tests in `backend/tests/` describing the behaviour
   (happy path + at least one error case). Run `cd backend && uv run pytest`
   and show that the new tests FAIL. Pause and let me review the tests.
3. **Implement** — After I approve the tests:
   - Put the endpoint in a router module under `backend/app/routers/`
     (create the package if missing) and register it in `app/main.py`.
   - Define request/response models with Pydantic in `backend/app/schemas/`.
   - Use type hints everywhere.
4. **Verify** — Run `uv run pytest` and `uv run ruff check .` from `backend/`.
   All must pass.
5. **Explain** — Finish with a short beginner-friendly explanation of each new
   piece of code and why it is structured that way.
