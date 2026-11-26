# ADR 0002: Classify with keyword rules only (no AI in the inbox)

| | |
|---|---|
| Status | **Accepted**, implemented in #92 |
| Date | 2026-11-26 |
| Decided by | John Dusenge, during the Epic 3b review (#85); plan by Claude Code |
| Changes | Epic 2's design (Claude first, keyword rules as a fallback) |

## Context

Since Epic 2 the inbox classified emails with Claude (`claude-haiku-5-5`, batches of 20)
and fell back to keyword rules when Claude was missing, failed or answered badly. The
eval (story 2.6, `docs/testing/epic-2-eval.md`) measured Claude at 83–91 % on the
hand-labelled set and the rules at 96 % (on a set the rules were written against).

During the Epic 3b review John decided he wants to **select any received email and get it
classified by the keywords of its priority**, not have AI do everything: a result he can
predict and check, at no cost. Claude still writes the sample emails (in the separate
generator, ADR 0001), so the project keeps its AI part.

## Options

| Option | Verdict |
|---|---|
| **A. Remove the AI from the inbox completely** | **Chosen.** One method, simplest code, no key and no cost to classify. |
| B. Rules by default, AI behind a setting (`CLASSIFIER=rules`) | Rejected: keeps a second code path, its tests and its dependency for a feature nobody uses. |
| C. Keep AI first, show the rules' keywords next to it | Rejected: doesn't meet the wish (AI would still decide). |

Also decided: the reason **names the matched keywords**; emails already classified by
Claude **keep their label** (source `ai`); manual priorities always win.

## Decision

- The keyword rules (`backend/app/services/rules.py`, formerly the fallback) are the
  inbox's only classifier: **Classify** (all unclassified) and **Classify by keywords**
  (one email, even one with an `ai` or `manual` label) both use them.
- The reason lists every keyword of the deciding priority (in the order found, at most 4)
  and what they signal, e.g. *Critical: matched "outage", "database is down" (an outage,
  a service that is down).* Always ≤ 200 characters.
- The source `fallback` is renamed `rules`; migration `0003` (the project's first **data**
  migration) changes the stored rows, and downgrade restores them exactly.
- Removed from the inbox: the AI classifier, its prompt, `ai_client.py`, `errors.py`,
  the AI error handlers, `scripts/eval_classifier.py`, the `ANTHROPIC_*` settings and the
  `anthropic` dependency. A test fails if any inbox code mentions `anthropic` again.

## Consequences

**Good**

- **Deterministic and explainable:** the same text always gets the same priority, and the
  reason says why. Mistakes are easy to see and to fix (add or move a keyword).
- **Free and fast:** no API key, no cost, no network; 46 emails classified in one request
  in milliseconds (before: ~20 s per 50).
- **Less code and fewer failure modes:** no timeouts, rate limits, prompt injection or
  invalid AI output to handle in the inbox.

**Costs (accepted)**

- **Less judgement:** rules only see words, not meaning. Context ("not an outage, just a
  test"), sarcasm or unusual wording can be misclassified; the eval showed the rules were
  optimistic on the set they were written for.
- **Mixed history:** 140 emails keep Claude's labels and reasons; new ones get keyword
  reasons. "Classify by keywords" on one email switches it.
- **Learning scope:** the inbox no longer shows structured AI output; the generator still
  does (generation with structured outputs, validation, error mapping).

## Follow-ups

- If the rules misclassify often: extend the keyword table (and the labelled set first,
  test-driven), or reconsider option B with an eval.
- Epic 5's daily brief (`/api/brief`) is planned as a Claude feature; it would bring an AI
  client back into the inbox, with its own decision.

## Evidence

- Story #92 (this change), test log in its PR; migration test
  `tests/test_migrations.py::test_0003_renames_fallback_to_rules_and_can_be_undone`.
- Before/after on the real database: `FALLBACK` 10 → `RULES` 10, `AI` 140 and `MANUAL` 2
  unchanged; then Classify → "Classified 46 emails by keyword rules", no Claude call.
