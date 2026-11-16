---
description: Start a user story from a GitHub issue — read it, branch, plan, wait for OK
argument-hint: <issue number, e.g. 21>
---

Start work on GitHub issue #$ARGUMENTS, following the working agreement in
`docs/PROJECT_BRIEF.md`.

1. **Read** — `gh issue view $ARGUMENTS` (include comments). Restate the acceptance
   criteria in your own words and point out anything ambiguous; check it against the
   relevant epic in the brief.
2. **Branch** — make sure the working tree is clean, then
   `git switch main && git pull && git switch -c <type>/<short-slug>` where type is
   `feat`, `fix`, `chore`, `docs` or `ci`. Tell me the branch name.
3. **Plan** — list the files you will create or change, the approach, and the tests
   you will write first. Name any new concept involved and explain it in one or two
   plain sentences.
4. **Stop** — wait for my OK before writing any code.
