# ADR 0001: A separate generator service that delivers to the inbox

| | |
|---|---|
| Status | **Accepted**, implemented in Epic 3b (#79, stories #80–#85) |
| Date | 2026-11-26 |
| Decided by | John Dusenge, on the advice of his coach; analysis by Claude Code |

> **What an ADR is:** a short, numbered record of one important decision: the context,
> the options, what was chosen and what it costs. It is not rewritten later; a new
> decision that changes it gets a new ADR that "supersedes" this one.

## Context

After Epic 3 the inbox did two jobs: it **generated** sample emails with Claude (a
"Generate" button) and it **triaged** them (views, classify, reading pane, alerts).
John's coach advised separating the two, like a real mail system: a mail client does
not write its own mail, mail arrives from outside. Concretely: a separate Email
Generator with a simple, search-engine-like page that says "10 new emails generated",
and the existing app on `:8080` only receives, displays and triages.

Constraints: learning project (show real patterns, explain them), small steps, tests
without network, no secrets in the repo, everything must keep running in Docker and CI.

## Options

| Option | How it works | Verdict |
|---|---|---|
| **A. Shared backend, separate page** | A new page calls the existing `POST /api/emails/generate` | Cheapest (~2 stories), but **not decoupled**: generation still lives in the inbox's backend. |
| **B. Separate service + delivery API** | The generator has its own backend and Claude client; it **delivers** emails to the inbox through `POST /api/emails/ingest`, protected by a shared token | **Chosen.** A real service boundary; the inbox doesn't know or care who sends mail; both sides testable alone. |
| C. Shared database | Both services write to `data/app.db` | Rejected: an anti-pattern. SQLite with two writers, and the services stay coupled through the table schema. |
| D. Message queue (Redis, RabbitMQ) | The generator publishes, the inbox consumes | Rejected for now: a lot of infrastructure for this size. B can grow into it later. |
| E. Real mail protocol (SMTP + IMAP) | The generator sends to a local mail server, the inbox reads it | Rejected: much more work, and reading real mailboxes is out of scope (brief §14). |

## Decision

**Option B.** Also decided (John, 2026-11-26): **remove Generate from the inbox
completely**, and do it as a **new epic before Epic 4**, so planning and the dashboard
build on the final shape.

The contract between the two services:

- `POST /api/emails/ingest` on the inbox, body `{"emails": [...]}` (1–50), header
  `X-Ingest-Token` = the shared `INGEST_TOKEN` (one value in `.env`, read by both).
- Wrong or missing token → 401; inbox without a token → 503 (a forgotten setting never
  means "accept anything"); any invalid email → 422 and nothing is saved.
- The inbox **validates every email again** ("never trust the sender"); unknown fields
  such as `priority` are rejected, those belong to the inbox.
- The inbox notices new mail by **polling** `/api/emails/summary` every 15 s.

## Consequences

**Good**

- Clear responsibilities: the generator only writes and delivers; the inbox only
  receives and triages. Each can change inside without breaking the other.
- The contract is small and tested on both sides (fake inbox in the generator's tests,
  ingest tests in the inbox), plus a CI smoke test of the real wiring.
- The inbox now behaves like a mail client: mail arrives from outside, the page
  notices it ("10 new emails arrived").
- Claude is called by one service per job; generation costs are visible in the
  generator's log.

**Costs and risks (accepted)**

- **More to run and maintain:** three containers instead of two, a second Python project
  and a second web project, one more CI job, more Dependabot PRs; in Epic 6 one more
  image to build and deploy.
- **Duplicated code:** the generator has its own copy of the small Claude client
  (`ai_client.py`, `errors.py`) and of the email rules. Chosen over a shared library so
  each service can upgrade on its own; a bug fixed in one copy must be checked in the
  other (noted in both files).
- **A failed delivery loses the generated emails** (no retry, no storage in the
  generator): ~$0.0015 per 10 emails, acceptable for test data.
- **Polling, not push:** up to 15 s late (up to about a minute in a background tab,
  because browsers slow down timers there) and a small request every 15 s per open tab.
- **Counting arrivals from `/summary`** (`all + trash` went up): emptying the Trash and
  receiving mail within one interval partly cancel out in the *message* (the list stays
  right).
- **Timing between services:** an email valid when generated can be too old when it
  arrives; the generator therefore accepts at most 47 h, one hour stricter than the
  inbox's 48 h.

## Deviation from the plan

The analysis planned **four** containers (`generator-api` and `generator-web` with its own
nginx). Story 3b.3 chose **one** generator container instead: a multi-stage build where
FastAPI serves the built page and the API on one origin (no CORS, no second nginx). Fine
for a small internal tool; a busy public site would put the page behind nginx or a CDN.

## Follow-ups

- **Push instead of polling** (Server-Sent Events) if 15 s or the extra requests matter.
- **Idempotency:** a delivery id the inbox remembers, so a retried delivery can't save
  the same emails twice (needed before adding automatic retries).
- **Epic 6:** decide whether the inbox's port 8000 stays published (today a convenience,
  protected by the token) and how `INGEST_TOKEN` reaches the cloud host (a secret).
- nginx should send `Cache-Control: no-cache` for the inbox's `index.html` (Firefox reused
  an old copy after a rebuild).

## Evidence

- Stories and PRs: #80/#86, #81/#87, #82/#88, #83/#89, #84/#91, #85.
- End-to-end test log: [docs/testing/epic-3b.md](../testing/epic-3b.md).
- How a request flows now: [docs/REQUEST_FLOW.md §6](../REQUEST_FLOW.md#6-generate--deliver--arrive-the-two-apps-together).
