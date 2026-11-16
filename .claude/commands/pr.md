---
description: Run all checks, commit, push and open a pull request for the current story
argument-hint: <issue number this PR closes>
---

Open a pull request for the current branch that closes issue #$ARGUMENTS.

1. **Guard** — refuse if the current branch is `main`. Show `git status` and the diff
   summary; flag anything that looks unrelated to the story or like a secret.
2. **Checks** — from `backend/`: `uv lock --check`, `uv run ruff check .`,
   `uv run ruff format --check .`, `uv run pytest`. From `frontend/`: `npm run lint`,
   `npm run build`. If anything fails, explain why in plain words and stop.
3. **Definition of Done** — walk through §11 of `docs/PROJECT_BRIEF.md` and say which
   items are met. Remind me of docs (README / CLAUDE.md / brief / `.env.example`) that
   need updating.
4. **Commit & push** — show me the proposed commit message and wait for my OK, then
   commit (never `--no-verify`) and `git push -u origin HEAD`.
5. **Open PR** — `gh pr create --base main` with a description containing: What,
   Why, How verified, and `Closes #$ARGUMENTS`. Give me the PR URL.
