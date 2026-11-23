# Epic 2 end-to-end test log

> **What this is:** the manual end-to-end check for Epic 2 (priority classification),
> run in Docker the way a user uses the app, **with and without** the API key. Unit and
> API tests run automatically in CI; this log covers what only the real stack and a real
> browser can prove. Every ✅ below points to evidence in the server logs or the database,
> not only to what the screen showed.

| | |
|---|---|
| Date | 2026-11-23 |
| Branch / base | `chore/2.7-epic2-e2e-docs` on `main` @ `5e4031d` (PR #60) |
| Stack | `docker compose up -d --build` (Docker Desktop, WSL integration) |
| Model | `claude-haiku-5-5`, effort low; classify batches of 20, max 50 emails per request |
| "No key" mode | backend restarted with a compose override (`ANTHROPIC_API_KEY: ""`); `.env` untouched |
| Tested by | John (browser, http://localhost:8080) and Claude Code (setup, logs, database) |
| Claude cost of this log | about **$0.002** (step B); the backlog run from story 2.5 about $0.008 |

---

## A. No API key: graceful degradation

| # | Step (browser) | Expected | Evidence | Result |
|---|---|---|---|---|
| A.1 | Backend restarted without a key | not configured | `key configured: False` inside the container | ✅ |
| A.2 | Click **Generate emails** | red banner *"AI is not configured…"*, list unchanged | `POST /api/emails/generate -> 503` (browser via nginx); count stayed 115 | ✅ |
| A.3 | Click **Classify** (10 unclassified) | rules classify them, no error | `POST /api/emails/classify -> 200`; `Classified 10 emails: ai=0 fallback=10` | ✅ |

## B. Real API key

| # | Step (browser) | Expected | Evidence | Result |
|---|---|---|---|---|
| B.0 | Key restored; container reaches Anthropic | reachable | `key configured: True`; `HTTP 401` from `api.anthropic.com` without auth (= reachable) | ✅ |
| B.1 | Generate **10** | 10 new emails | `POST /generate -> 201`, 1 Claude call, 12.3 s, `10 valid (0 skipped)`; 115 → **125** | ✅ |
| B.2 | Click **Classify** | 10 by AI | `POST /classify -> 200`, 1 Claude call, 7.4 s, `ai=10 fallback=0`, 0 items rejected | ✅ |
| B.3 | Cost of B.1 + B.2 | – | 4,002 input + 3,440 output tokens ≈ **$0.0021** | ✅ |

**Full backlog through nginx** (story 2.5, browser, real data, confirmed in the logs):
105 emails classified by Claude in **3 requests** (50 + 50 + 5) in about 26 s, 7 Claude
calls, 0 items rejected, 29,136 input + 10,781 output tokens ≈ **$0.008**. Every request
stayed far below nginx's 180 s timeout.

## C. Manual override (dropdown)

| # | Step (browser) | Expected | Evidence | Result |
|---|---|---|---|---|
| C.1 | Change a priority with the dropdown (story 2.5 follow-up) | `manual`, "Set manually." | 2026-11-23 03:26:30 `PATCH /api/emails/86 -> 200`: *"Production checkout errors spiking since 9:40"* → high, manual | ✅ |
| C.2 | Change another one | same | 04:15:29 `PATCH /api/emails/49 -> 200`: *"Unusual sign-in detected for service account svc-reporting"* → high, manual, 15 min | ✅ |

## D. Persistence across `docker compose down` / `up`

| # | Step | Expected | Evidence | Result |
|---|---|---|---|---|
| D.1 | `docker compose down` | containers gone, DB kept | 0 containers; `data/app.db` (owner `john`) still on disk | ✅ |
| D.2 | `docker compose up -d`, then `GET /api/emails` | same data | 125 emails; manual #49 and #86 still high/manual | ✅ |
| D.3 | **Browser:** F5 after the restart | both cards show High · manual | 04:17:18 page reload (`GET /`, `GET /api/emails -> 200`) from the browser | ✅ |

## E. CI without a key

| # | Check | Evidence | Result |
|---|---|---|---|
| E.1 | No API key in GitHub | `gh secret list` returns nothing | ✅ |
| E.2 | CI green for every Epic 2 PR | #53, #54, #55, #56, #59, #60: backend, frontend, docker all pass | ✅ |

---

## Incident: real-world fallback (story 2.5, 2026-11-23 ~03:05 UTC)

During a browser check, **every Claude call from the Docker container failed** with
`CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`: something on
the machine/network briefly intercepted HTTPS from Docker (WSL was not affected). The app
behaved as designed: 7 failed calls, **all 105 emails classified by the rules**, every
request 200, no crash, $0. The connection recovered on its own minutes later; the
fallback rows were reset (backup kept) and the AI run repeated successfully.

What it shows: graceful degradation works outside of tests, and the UI's result line
("0 by AI, 105 by rules") is how a user notices it. If you see "by rules" while a key is
set, check `docker compose logs backend | grep "Claude call failed"`.

## Epic 1 browser follow-up (closed here)

The three Epic 1 rows marked "not run" in `docs/testing/epic-1.md` are now done in the
browser, with log evidence:

| Epic 1 row | Evidence (2026-11-23) |
|---|---|
| 4.5 Generate without a key → banner, list unchanged | step A.2: `POST /generate -> 503`, count stayed 115 |
| 6.1 Generate 10 in the UI | 03:27:28 `POST /generate -> 201` (10 emails) and step B.1 (115 → 125) |
| 6.2 Refresh: generated emails still listed | 04:10:41 page reload listed the 10 emails generated at 03:27 |

## Known limits (not bugs)

- **AI and rules often disagree** (55 of 105 on the generated emails): the rules over-raise
  to "high" on words like "customer" and "tomorrow". Measured quality: see
  `docs/testing/epic-2-eval.md` (Claude 83-91 %, no critical missed).
- **Classify is sequential:** 50 emails = 3 Claude calls one after another (~20 s per request).
- **Generated emails repeat** (e.g. "Production checkout errors spiking" appears 10+ times):
  low variety from the generator prompt; a candidate for a later story.
- **Docker HTTPS interception** can make every call fall back to the rules (see incident).
