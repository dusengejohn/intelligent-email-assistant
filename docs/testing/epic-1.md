# Epic 1 end-to-end test log

> **What this is:** the manual end-to-end check for Epic 1 (email generation), run in
> Docker the way a user would use the app. Unit and API tests run automatically in CI;
> this log covers what only the real stack can prove (nginx, Docker volumes, the real
> Claude API). Re-run it after changes to Docker, nginx or the generate flow.

| | |
|---|---|
| Date | 2026-11-21 |
| Branch / base | `chore/1.8-epic1-e2e-docs` on `main` @ `3ae389f` (PR #44) |
| Stack | `docker compose up -d --build` on Docker Desktop (WSL integration) |
| Model | `claude-haiku-5-5`, `AI_TIMEOUT_SECONDS=30`, 1 retry |
| Tested by | Claude Code (commands); browser rows not run (see below) |
| Total Claude cost | about **$0.02** |

From a **WSL terminal**, Docker Desktop's ports are reached via the Windows host IP:
`H=http://$(ip route | awk '/default/ {print $3; exit}'):8080`. In a Windows browser,
`http://localhost:8080` works.

---

## 1. The 504 bug, reproduced first (before the fix)

| Step | Expected | Actual |
|---|---|---|
| nginx with its default `proxy_read_timeout` (60 s); `POST $H/api/emails/generate {"count": 50}` | (the bug) | **504 Gateway Time-out after 56.9 s**; nginx log: `upstream timed out … while reading response header` |
| Backend log during the same request | — | 5 Claude calls of 11.1–13.0 s (~62 s total); `Generated 45 valid emails (3 skipped)` |
| `GET /api/emails` afterwards | — | 10 → **55** emails: the backend **saved 45 emails although the user saw an error** |

Why it matters: the user is told "failed" for work that succeeded, and a retry creates
duplicates. Claude returned 48 of 50 items (two batches had 9) and 3 failed validation,
so 45 were kept: the "skip invalid, no top-up" rule from #30 working as designed.

## 2. After the fix (`proxy_read_timeout 180s`)

| # | Step | Expected | Actual | Result |
|---|---|---|---|---|
| 2.1 | `nginx -t` on the built image (also a new CI step) | config valid | `syntax is ok`, `test is successful`; a missing `;` makes it fail (exit 1) | ✅ |
| 2.2 | `POST $H/api/emails/generate {"count": 50}` | 201, no 504 | **201 after 60.3 s**, 50 emails in the response; 5 calls of 12.0–13.4 s, `50 valid (0 skipped)` | ✅ |
| 2.3 | List after 2.2 | 50 more emails | 55 → **105** | ✅ |
| 2.4 | `POST … {"count": 51}` | 422 | 422 | ✅ |

## 3. Persistence and restart policy

| # | Step | Expected | Actual | Result |
|---|---|---|---|---|
| 3.1 | `docker compose down` | containers removed, DB file kept | 0 containers; `data/app.db` (72 KB, owner `john`) still on disk | ✅ |
| 3.2 | `docker compose up -d`, then `GET /api/emails` | same emails | **105** emails, same newest email (id 64) as before `down` | ✅ |
| 3.3 | `docker inspect … RestartPolicy` | `unless-stopped` on both | backend and frontend: `unless-stopped` | ✅ |
| 3.4 | `DATABASE_URL` in the container | inside the volume | `sqlite:////app/data/app.db` (compose), volume `./data:/app/data` | ✅ |

## 4. Missing API key

The key was blanked for the backend only, with a temporary compose override
(`environment: ANTHROPIC_API_KEY: ""`, which beats `env_file`), so `.env` wasn't edited.

| # | Step | Expected | Actual | Result |
|---|---|---|---|---|
| 4.1 | Settings inside the container | key not configured | `key configured: False` | ✅ |
| 4.2 | `POST … {"count": 10}` | 503 with a clear message | **503** `AI is not configured: set ANTHROPIC_API_KEY in .env` | ✅ |
| 4.3 | Rest of the app | still works | `/api/health` 200, page 200, all 105 emails listed | ✅ |
| 4.4 | Restore (`docker compose up -d backend`) | key configured again | `key configured: True` | ✅ |
| 4.5 | **Browser:** click Generate with the key removed | red banner with the 503 message; list unchanged | **not run** (see note below) | ⬜ |

## 5. Build and CI

| # | Step | Expected | Actual | Result |
|---|---|---|---|---|
| 5.1 | Image packages vs `backend/uv.lock` | identical | fastapi 0.163.0, sqlmodel 0.0.50, sqlalchemy 2.1.9, anthropic 2.8.0, pydantic 2.14.3, pydantic-settings 2.16.3, email-validator 2.4.0, uvicorn 0.54.0: **all match** (`uv sync --frozen --no-dev`) | ✅ |
| 5.2 | No dev tools in the image | pytest/ruff absent | none found | ✅ |
| 5.3 | `gh secret list` | no `ANTHROPIC_API_KEY` in GitHub | **no secrets at all** | ✅ |
| 5.4 | CI on the PR (backend, frontend incl. Vitest, docker incl. non-root + `nginx -t`) | green without a key | see the checks on this story's PR (#34) | ⏳ |

## 6. Browser (John)

| # | Step | Expected | Actual | Result |
|---|---|---|---|---|
| 6.1 | http://localhost:8080, enter 10, **Generate emails** | button "Generating…", then 10 new emails with sender, subject, preview, local time | **not run** (see note below) | ⬜ |
| 6.2 | Refresh the page (F5) | emails still listed | **not run** (see note below) | ⬜ |

---

## Not run: browser rows 4.5, 6.1, 6.2

These three steps were **not run** in this session. The server logs showed the page being
loaded and reloaded in the browser (04:51 and 04:52 UTC) but no `POST /api/emails/generate`
from the browser, and the backend was not restarted without a key, so there was no result
to record.

The same flows **were** verified through nginx with `curl` (the exact requests the page
sends): 201 for 50 emails (2.2), 503 with the clear message without a key (4.2), and the
list after a restart (3.2). The UI itself was checked in the browser in story 1.7 (#33).
**Follow-up:** run 4.5, 6.1 and 6.2 in the browser and record the results here.

## Known limits (not bugs)

- **50 emails take ~60–80 s** because the 5 Claude calls run one after another. If a run
  ever exceeds 180 s, the browser shows the 504 "took too long" message, but the emails
  are usually saved anyway (refresh the list). Parallel batches would fix this.
- **A request can return fewer emails than asked** (here 45 of 50): invalid AI output is
  skipped, never topped up.
- **Similar senders across runs** (e.g. `priya.raman@example.com` again): the same prompt
  with low effort gives similar answers. A random theme per batch could add variety.
