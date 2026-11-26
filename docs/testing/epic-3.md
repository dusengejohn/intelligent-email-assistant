# Epic 3 end-to-end test log

> **What this is:** the manual end-to-end check for Epic 3 (the inbox: priority order,
> views with counts, reading pane, Trash, alerts), run in Docker in a real browser.
> Unit and component tests run in CI; this log covers what only the real stack and a
> real browser can prove. Every ✅ points to evidence in the **nginx log** (what the
> browser sent), the **backend log** or the **database**, not only to what the screen
> showed. The checks were done in 5 short rounds, each verified before the next.

| | |
|---|---|
| Dates | 2026-11-24 (round 1 part 1), 2026-11-25/26 UTC (rest) |
| Branch / base | `chore/3.8-epic3-e2e-docs` on `main` @ `14517c5` (PR #76) |
| Stack | `docker compose up -d` (Docker Desktop, WSL integration); DB at migration `0002` |
| Browser | **Firefox 160** (see "Incident: VS Code's built-in browser" below) |
| Tested by | John (browser, DevTools Network open) and Claude Code (setup, logs, database) |
| Claude cost of this log | about **$0.0012** (1 throwaway email + classifying 10) |

---

## Round 1: views, URL, refresh, Back

| # | Step | Evidence (nginx) | Result |
|---|---|---|---|
| 1.1 | Trash view | 2026-11-24 15:29:49 `GET /api/emails?trash=true` 200 | ✅ |
| 1.2 | Classified / Unclassified views | 15:29:54 `?classified=true`, `?classified=false` 200 | ✅ |
| 1.3 | Browser Back | 15:29:57 `?classified=true` again (Back from Unclassified) | ✅ |
| 1.4 | Open `/?view=critical` (= refresh in that view) | 2026-11-25 23:48:11 `GET /?view=critical` 200 + `GET /api/emails?priority=critical` 200 | ✅ |
| 1.5 | Back to All | 23:48:23 `GET /api/emails` 200 | ✅ |

## Round 2: reading pane (email #116 "Production database CPU at 98%…")

| # | Step | Evidence | Result |
|---|---|---|---|
| 2.1 | Open an email | the pane opens (client-side, no request) | ✅ (John) |
| 2.2 | Mark handled / Mark as new | 2026-11-26 00:09:33 and 00:09:49 `PATCH /api/emails/116` 200; #116 ends `new` | ✅ |
| 2.3 | Delete → next email opens → **Undo** | 00:09:53 `DELETE /api/emails/116` 204 ("Moved email 116 to the Trash"), 00:09:59 `POST /api/emails/116/restore` 200 ("Restored email 116") | ✅ |
| 2.4 | Change priority in the pane | **not run / not confirmed**: tried twice, no `PATCH` reached the server, #116 stayed `ai` / critical. Covered by `App.test.tsx` ("changes the priority and reloads the list and counts") and `ReadingPane.test.tsx`. Follow-up: #77. | ⬜ |

Earlier the same session, three deletes from Firefox (2026-11-25 23:52 UTC: #133, #126, #17) moved
three real emails to the Trash; they were restored in round 3.

## Round 3: Trash (throwaway email for the permanent step)

| # | Step | Evidence | Result |
|---|---|---|---|
| 3.1 | Restore the 3 trashed emails | 00:13:51–54 `POST /api/emails/{17,126,133}/restore` 200 ("Restored email …") | ✅ |
| 3.2 | Generate 1 throwaway | 00:14:49 `POST /api/emails/generate` 201 (1 Claude call, "Generated 1 valid emails") | ✅ |
| 3.3 | Delete it (no Undo) | 00:15:20 `DELETE /api/emails/153` 204 ("Moved email 153 to the Trash") | ✅ |
| 3.4 | Empty trash: Esc, then Cancel | no request between 00:15:20 and 00:16:20 | ✅ |
| 3.5 | Empty trash → Delete forever | 00:16:20 `DELETE /api/emails/trash` 200 ("Emptied the Trash: 1 emails permanently deleted"); #153 no longer exists; Trash 0 | ✅ |

## Round 4: alerts

| # | Step | Evidence | Result |
|---|---|---|---|
| 4.1 | Classify the 10 unclassified emails | 00:19:37 `POST /api/emails/classify` 200; backend "Classified 10 emails: ai=10 fallback=0", 3,310 in / 1,410 out tokens (~$0.001) | ✅ |
| 4.2 | Alert toast | counts critical 37 → 38, high 28 → 31, so the toast is "1 new critical, 3 new high" (toast itself is browser-only; reported by John) | ✅ |
| 4.3 | "Show critical" opens the view | **not confirmable**: Classify was clicked while already in Critical, so opening it again sends no request. Covered by `App.test.tsx`. | ⬜ |
| 4.4 | Desktop notification (tab hidden) | **not run** (skipped). Covered by `notifications.test.ts` with a fake Notification API. | ⬜ |

(Story 3.7's own check already showed 2 × generate 201 + 2 × classify 200 producing new
urgent emails: critical +6, high +5.)

## Round 5: persistence across `docker compose down` / `up`

| # | Step | Evidence | Result |
|---|---|---|---|
| 5.1 | `down` | 0 containers; `data/app.db` kept on disk | ✅ |
| 5.2 | `up` | backend "Database schema is up to date" (already at `0002`, no migration needed) | ✅ |
| 5.3 | Same data | `/api/emails/summary` identical before/after: 152 emails (critical 38, high 31, moderate 58, low 25), Trash 0; manual #49/#86 kept; emptied #153 stays gone | ✅ |
| 5.4 | Browser F5 after the restart | reported by John; no page load reached the new frontend container's log | ⬜ |

## CI and secrets

| # | Check | Evidence | Result |
|---|---|---|---|
| 6.1 | No API key in GitHub | `gh secret list`: empty | ✅ |
| 6.2 | CI green for every Epic 3 PR | #70, #71, #72, #73, #74, #75, #76: backend, frontend, docker all pass | ✅ |

## Not observable in logs (John's report)

Narrow window (sidebar → View dropdown, pane replaces the list with "Back to list") and
keyboard use (Tab/Enter on views and rows, Esc in the dialog) leave no server trace. They
are covered by component tests (`Sidebar.test.tsx`, `EmailRow.test.tsx`,
`ConfirmDialog.test.tsx`).

---

## Incident: VS Code's built-in browser drops data-changing requests

For stories 3.4–3.7 most browser checks never appeared in the server log. This round found
why: the nginx log records the browser's user agent, and **every** `POST`/`PATCH`/`DELETE`
came from **Firefox**, while VS Code's built-in browser (`Code/1.147 … Electron`) only ever
produced page loads and view `GET`s. Clicking Delete or changing a priority in VS Code's
browser did nothing and showed no error. **Use a normal browser (Firefox, Edge, Chrome)
for checks**, with DevTools → Network open. Why VS Code's browser drops them wasn't
investigated further.

## Incident: Docker Desktop engine stopped after a reboot (twice)

After a restart of the machine, Docker Desktop's window and processes were running but its
engine was not: the `docker-desktop` WSL distro was **Stopped**, `/var/run/docker.sock`
missing, even Windows' `docker.exe` hung, and the app didn't answer. Docker Desktop →
Troubleshoot → **Restart** fixed it both times (otherwise `wsl --shutdown`, then start
Docker Desktop). Check with `wsl -l -v` from Windows.

## Known limits (not bugs)

- **Pane priority change not confirmed in a real browser** (2.4); follow-up #77 to
  investigate.
- **Clicking a view you're already in sends nothing** (by design; `selectView` returns early).
- `docker logs --since` returned nothing after the Docker restart although `--tail` showed
  fresh lines; evidence here was read with `--tail`.
