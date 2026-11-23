# Classifier eval: AI vs rules (story 2.6)

> **What this is:** the first measured comparison of the two classifiers against the
> hand-labelled emails (`backend/tests/data/labelled_emails.py`, 23 emails written from
> the brief §7 meanings only). Re-run it after any change to the prompt, the rules, the
> model or `app/priorities.py`, and compare with the numbers below.
>
> ```bash
> cd backend
> uv run python -m scripts.eval_classifier            # 1 run, ~$0.001 with a key
> uv run python -m scripts.eval_classifier --runs 3   # + run-to-run consistency
> ```
>
> Never run in CI (it calls the real API). Without a key, only the rules are measured.

| | |
|---|---|
| Date | 2026-11-23 (a Monday) |
| Model | `claude-haiku-5-5`, effort low, batches of 20 |
| Data | 23 labelled emails: 6 critical, 6 high, 6 moderate, 5 low |
| Runs | rules once (deterministic), Claude 3 times |
| Cost | 6 Claude calls, 13,254 input + 4,394 output tokens, about **$0.0035** |
| Validity check | Claude answered **23/23** in every run (no silent fallback) |

## Results

| | Accuracy | Critical classified moderate/low |
|---|---|---|
| Rules (fallback) | **96 %** (22/23), *optimistic, see caveat* | 0 |
| Claude, run 1 | 83 % (19/23) | 0 |
| Claude, run 2 | 91 % (21/23) | 0 |
| Claude, run 3 | 87 % (20/23) | 0 |

Claude never missed a critical email (6/6 in every run). Its errors are all one step
apart (high to moderate, moderate to low), never a critical email marked as routine.

Claude, run 2 (rows = expected, columns = predicted; the diagonal is correct):

```
expected\got  critical      high  moderate       low
critical           6         0         0         0
high               0         5         1         0
moderate           0         0         5         1
low                0         0         0         5
```

## The misses, and what they really mean

| Email | Expected | Claude | Runs | Assessment |
|---|---|---|---|---|
| Vendor contract review by Friday | high | moderate | 3/3 | **Label is debatable.** I labelled it "deadline within 48 h", but the eval ran on a Monday, so Friday was ~4 days away: by brief §7 that is moderate. |
| Room change for the sprint retro | moderate | low | 3/3 | **Debatable.** Meeting coordination (moderate) vs informational notice (low). |
| Downloaded the logs you asked for | moderate | low | 2/3 | **Debatable.** A reply to the user's own request vs an FYI. |
| Budget numbers needed by tomorrow noon | high | moderate | 1/3 | **Real miss**, but inconsistent: runs 2 and 3 got it right. |
| Pizza Friday in the kitchen (rules) | low | moderate | – | Real miss for the rules: keyword rules can't see "social". |

**Consistency:** 2 of 23 emails changed priority between runs ("Budget numbers…",
"Downloaded the logs…"). The same prompt doesn't always give the same answer.

## Caveats (read before trusting the numbers)

1. **The rules' 96 % is optimistic.** The rules were written while looking at these 23
   emails (story 2.1). On 105 unseen generated emails the first rule version put security
   alerts in *low*. Claude never saw this set, so its 83-91 % is the fairer number.
2. **23 emails is a small set.** One email is about 4 percentage points, so 83 % vs 91 %
   is a difference of two emails, not a real trend.
3. **The eval isn't reproducible over time.** Relative deadlines ("tomorrow", "by Friday")
   are judged against the real current time, which `classify_emails()` reads itself. The
   same eval run on another weekday can score differently.
4. **The labels are one person's judgment** (mine, from brief §7). Three of the four
   Claude "misses" are cases a reasonable person could label either way.

## Improvement ideas

1. **Make the eval reproducible:** let `classify_emails()` accept a fixed "now" (e.g. the
   labelled emails' received time), so relative deadlines are judged the same way every run.
2. **Fix and sharpen the labels:** relabel "Vendor contract review by Friday" (or give it
   an absolute date), and add a short note per ambiguous email explaining the rule used.
   Better still: use your own manual overrides (`PATCH`, story 2.4) on real emails as a
   second, independent labelled set.
3. **Sharpen the prompt where the misses cluster:** state that "meeting logistics changes"
   are moderate and "replies to the recipient's own request" are moderate, not low.
   Re-run the eval afterwards: a prompt change is only an improvement if the numbers say so.
