# Epic 3b end-to-end test log

> **What this is:** the manual end-to-end check for Epic 3b (the separate Email
> Generator delivering to the inbox), run in Docker in a real browser. Unit, component
> and smoke tests run in CI; this log covers what only the real stack and a real
> browser can prove. Every ✅ points to evidence in a server log (generator, backend or
> nginx, which records the browser) or the database, not only to what the screen showed.

| | |
|---|---|
| Date | 2026-11-26 (UTC) |
| Branch / base | `chore/3b.6-split-e2e-docs` on `main` @ `8e839a9` (PR #91); stack rebuilt from it at 03:12 |
| Stack | `docker compose up -d --build`: frontend :8080, backend :8000, generator :8081 |
| Browser | **Firefox 160**, DevTools → Network open |
| Tested by | John (browser) and Claude Code (setup, logs, database) |
| Starting point | 186 emails, 34 unclassified; smoke test passed |
| Claude cost of this log | about **$0.003** (generate 10, then 3 × generate 1) |

Three small fixes came out of this review and are part of the same PR: **"Open the inbox"
and the inbox's "Email Generator" link open a new tab** (John's requests) and **the
inbox's health pill re-checks every 15 s** (found in round 3).

---

## Round 1: generate on :8081 → arrives on :8080

| # | Step | Evidence | Result |
|---|---|---|---|
| 1.1 | Fresh generator page | generator 03:17:56–03:18:52 `GET /` 200 | ✅ |
| 1.2 | Generate 10 | 03:19:24 `POST /api/generate` 201; Claude 19.4 s, 925 in / 3,631 out tokens; "Generated 10 valid emails (0 skipped)", "Delivered 10 emails to the inbox" | ✅ |
| 1.3 | The inbox receives them | backend 03:19:24 "Ingested 10 emails (ids 187..196)", from the generator's container IP; unclassified 34 → 44 | ✅ |
| 1.4 | **Open the inbox ↗** opens a new tab | nginx 03:19:27 Firefox `GET /` with **`Referer: http://localhost:8081/`**; John: "inbox opened in a new tab" | ✅ |
| 1.5 | Classify after the arrival | **not run**: John decided to replace AI classification by keyword rules (#92) | ⬜ |
| 1.6 | "1 new email arrived" | covered by round 4 (same arrival check) | ✅ (4.3) |

A first attempt showed a green result line although nothing reached the servers: the
generator tab still displayed the result of an earlier run (03:04, story 3b.5), from
before the rebuild. The page keeps its last result until reloaded; reload it after a
rebuild.

## Round 2: wrong token → clear error, nothing delivered

Setup: the compose generator stopped; the same image run on :8081 in the compose network
with `INGEST_TOKEN=this-token-is-wrong-on-purpose` (everything else from `.env`).

| # | Step | Evidence | Result |
|---|---|---|---|
| 2.1 | Generate 1 | generator 03:40:09: Claude call 2.5 s, "Generated 1 valid emails" | ✅ |
| 2.2 | The inbox rejects the token | backend 03:40:09 `POST /api/emails/ingest` **401 Unauthorized** | ✅ |
| 2.3 | Clear error, nothing delivered | generator WARNING "the inbox rejected the token (INGEST_TOKEN must be the same in both services)", `POST /api/generate` **502**; red box (John); counts unchanged (196) | ✅ |

As designed, Claude is paid before the delivery fails: the generator only learns at
delivery time that the token is wrong (~$0.0003 here). The real generator was restored
afterwards (`docker compose start generator`, healthy).

## Round 3: inbox stopped

| # | Step | Evidence | Result |
|---|---|---|---|
| 3.1 | `docker compose stop backend` | nginx `/api/...` → 502 | ✅ |
| 3.2 | Generate 1 | generator 03:42:19 Claude 2.0 s; 03:42:23 WARNING "the inbox could not be reached at http://backend:8000. (ConnectError)", **502**; red box (John) | ✅ |
| 3.3 | Inbox polling stays quiet | nginx 03:41:40–03:42:26: every `/api/emails/summary` poll 502, no error banner (John) | ✅ |
| 3.4 | Pill turns red **without a reload** | **failed at first**: the pill only turned red after a page reload (03:42:33 `GET /`, then `/api/health` 502). `HealthPill` checked the backend once, on page load. **Fixed** in this PR: it re-checks every 15 s (`HealthPill.test.tsx`) | ✅ after the fix |
| 3.5 | Re-test with the fix, no reload | 03:50:51 backend stopped → 03:51:38 `/api/health` 502, pill red, no banner (John) | ✅ |
| 3.6 | Recovery, no reload | 03:51:54 backend started → **03:52:09** `/api/health` + `/summary` 200, pill green (John) | ✅ |

The first red check came 47 s after the stop, not 15 s: Firefox ran no timers at all from
03:50:38 to 03:51:38 because the window was in the background (see "Known limits").

## Round 4: desktop notification (inbox tab hidden)

| # | Step | Evidence | Result |
|---|---|---|---|
| 4.1 | Enable desktop alerts, switch to the generator tab | browser-only (permission prompt, John) | ✅ (John) |
| 4.2 | Generate 1 | generator 03:56:45 Claude 2.4 s, "Delivered 1 emails"; backend "Ingested 1 emails (ids 197..197)" | ✅ |
| 4.3 | Arrival noticed in the background tab | nginx **03:56:55** poll + `GET /api/emails` reload (10 s after delivery) | ✅ |
| 4.4 | System notification "New email – 1 new email arrived" | browser-only, reported by John | ✅ (John) |

## Round 5: persistence across `docker compose down` / `up`

| # | Step | Evidence | Result |
|---|---|---|---|
| 5.1 | `down` | 0 containers, network removed; `data/app.db` kept (172,032 bytes, owned by john) | ✅ |
| 5.2 | `up --wait` | all healthy; backend "Database schema is up to date" | ✅ |
| 5.3 | Same data | `/api/emails/summary` **identical** before and after: 197 emails, 45 unclassified, critical 38, high 31, moderate 58, low 25, Trash 0 | ✅ |
| 5.4 | Wiring after the restart | `compose_smoke.sh` passed (wrong token 401, right token 201, id 198) | ✅ |

The generator is stateless (no database), so it has nothing to persist.

## Round 6: CI and secrets

| # | Check | Evidence | Result |
|---|---|---|---|
| 6.1 | No API key in GitHub | `gh secret list`: empty | ✅ |
| 6.2 | Required checks on `main` | backend, frontend, docker, **generator** | ✅ |
| 6.3 | CI green for every Epic 3b PR | #86 (backend, frontend, docker), #87, #88, #89, #91 (all four checks) SUCCESS; `main` @ `8e839a9` success | ✅ |
| 6.4 | The smoke test really ran in CI | #89's `docker` job log: both UIDs 1000, healthy services, `http://backend:8000` ok, wrong token 401, right token 201, "Smoke test passed." | ✅ |

---

## Findings and fixes from this review

| Finding | Fix |
|---|---|
| "Open the inbox" replaced the generator page (John) | `target="_blank" rel="noopener"`; component test checks both attributes; round 1.4 |
| The inbox's "Email Generator" link replaced the inbox page (John) | Same fix in the inbox toolbar (`Toolbar.tsx`), tested in `App.test.tsx`; checked after a rebuild: inbox reload 04:02:52, generator page `GET /` 04:02:54, opened in a new tab (John) |
| The health pill checked only on page load, so a backend outage was invisible in an open inbox (polling errors are deliberately quiet) | `HealthPill` re-checks every 15 s with cleanup; 4 component tests with a fake clock; 2 mutations caught |
| John prefers keyword rules over AI for classification | New story **#92** (after Epic 3b, before Epic 4) |

## Known limits (not bugs)

- **Timer throttling:** browsers slow down timers in background tabs and windows, so
  new-mail polling and the pill's re-check can take up to about a minute there instead of
  15 s (seen in round 3: no requests for 60 s).
- **Every open inbox tab polls** (`/summary` and `/api/health` every 15 s each); seen as
  paired requests while two inbox tabs were open.
- **A failed delivery loses the generated emails** (rounds 2 and 3): Claude has already
  been paid; nothing is retried or stored.
- **A tab keeps showing its last result** until reloaded (the first round 1 attempt).
- An old, exited container `interesting_hopper` (an nginx check from 2026-11-21) is still
  listed by `docker ps -a`; harmless, remove with `docker rm interesting_hopper`.
