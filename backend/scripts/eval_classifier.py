"""Measure how well the classifiers agree with hand-labelled priorities (story 2.6).

Run from backend/ (never in CI: with a key it calls the real Claude API):

    uv run python -m scripts.eval_classifier            # 1 run, ~$0.001 with a key
    uv run python -m scripts.eval_classifier --runs 3   # also shows run-to-run variation

It classifies the labelled set (tests/data/labelled_emails.py) with the rules and,
if ANTHROPIC_API_KEY is set, with Claude, and prints accuracy, a confusion matrix,
the misses, and critical emails classified moderate/low (the costly mistake).

Caveat: the rules were written while looking at this set (story 2.1), so their score
here is optimistic. Claude never saw it, so its score is a fair one.
"""

import argparse
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.config import get_settings
from app.models import ClassificationSource, Priority
from app.priorities import SORT_ORDER
from app.schemas import Classification
from app.services.ai_client import AIClient
from app.services.classifier import classify_emails
from app.services.fallback import classify_fallback
from tests.data.labelled_emails import LABELLED, LabelledEmail

Matrix = dict[Priority, dict[Priority, int]]


@dataclass(frozen=True)
class Prediction:
    sample: LabelledEmail
    result: Classification

    @property
    def expected(self) -> Priority:
        return self.sample.expected

    @property
    def predicted(self) -> Priority:
        return self.result.priority

    @property
    def correct(self) -> bool:
        return self.expected == self.predicted


@dataclass
class EvalResult:
    predictions: list[Prediction]
    by_source: dict[str, int] = field(default_factory=dict)

    @property
    def ai_predictions(self) -> list[Prediction]:
        """Only the answers that really came from Claude (not silent fallbacks)."""
        return [p for p in self.predictions if p.result.source == ClassificationSource.AI]

    @property
    def ai_answered_all(self) -> bool:
        return len(self.ai_predictions) == len(self.predictions)


# --- pure helpers (unit tested) ------------------------------------------------------


def accuracy(predictions: Sequence[Prediction]) -> float:
    """Share of exact matches (0.0 for an empty list)."""
    if not predictions:
        return 0.0
    return sum(p.correct for p in predictions) / len(predictions)


def confusion_matrix(predictions: Sequence[Prediction]) -> Matrix:
    """matrix[expected][predicted] = count, every cell present, brief §7 order."""
    matrix: Matrix = {e: {p: 0 for p in SORT_ORDER} for e in SORT_ORDER}
    for prediction in predictions:
        matrix[prediction.expected][prediction.predicted] += 1
    return matrix


def critical_misses(predictions: Sequence[Prediction]) -> list[Prediction]:
    """Critical emails classified moderate or low (high is still urgent: acceptable)."""
    return [
        p
        for p in predictions
        if p.expected == Priority.CRITICAL and p.predicted in (Priority.MODERATE, Priority.LOW)
    ]


def format_matrix(matrix: Matrix) -> str:
    """Rows = expected, columns = predicted; the diagonal is correct."""
    width = 10
    header = "expected\\got".ljust(width) + "".join(p.value.rjust(width) for p in SORT_ORDER)
    rows = [
        e.value.ljust(width) + "".join(str(matrix[e][p]).rjust(width) for p in SORT_ORDER)
        for e in SORT_ORDER
    ]
    return "\n".join([header, *rows])


# --- running the classifiers -----------------------------------------------------------


def evaluate(samples: Sequence[LabelledEmail], ai: AIClient | None) -> EvalResult:
    """Classify every sample (AI with per-email fallback, or rules only if ai is None)."""
    emails = []
    for number, sample in enumerate(samples, start=1):
        email = sample.to_email()
        email.id = number  # in-memory ids so results can be matched to samples
        emails.append(email)

    if ai is None:
        results = {e.id: classify_fallback(e) for e in emails}
    else:
        results = classify_emails(emails, ai)

    predictions = [Prediction(s, results[e.id]) for s, e in zip(samples, emails, strict=True)]  # type: ignore[index]
    sources = [p.result.source for p in predictions]
    return EvalResult(
        predictions=predictions,
        by_source={
            "ai": sources.count(ClassificationSource.AI),
            "fallback": sources.count(ClassificationSource.FALLBACK),
        },
    )


def report(title: str, predictions: Sequence[Prediction]) -> str:
    lines = [
        f"=== {title} ===",
        f"accuracy: {accuracy(predictions):.0%} "
        f"({sum(p.correct for p in predictions)}/{len(predictions)} exact)",
        "",
        format_matrix(confusion_matrix(predictions)),
        "",
    ]
    misses = [p for p in predictions if not p.correct]
    lines.append(f"misses ({len(misses)}):")
    for p in misses:
        lines.append(
            f"  - {p.sample.subject[:50]!r}: expected {p.expected.value}, got "
            f"{p.predicted.value} ({p.result.reason[:70]})"
        )
    critical = critical_misses(predictions)
    lines.append(
        f"critical emails classified moderate/low: {len(critical)}"
        + ("" if not critical else " <-- costly mistake")
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=int, default=1, help="AI runs (to see variation)")
    args = parser.parse_args(argv)

    print(
        report(
            "Rules (fallback) - optimistic: written while looking at this set",
            evaluate(LABELLED, None).predictions,
        )
    )
    print()

    settings = get_settings()
    if settings.anthropic_api_key is None:
        print("AI part skipped: no ANTHROPIC_API_KEY configured.")
        return 0

    # Show the AI client's per-call token log (the cost of this eval)
    logging.basicConfig(level=logging.INFO, format="  %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)

    runs: list[EvalResult] = []
    for run in range(1, args.runs + 1):
        result = evaluate(LABELLED, AIClient(settings))
        runs.append(result)
        answered = len(result.ai_predictions)
        print(f"AI answered {answered}/{len(result.predictions)} emails")
        if not result.ai_answered_all:
            print(
                "  WARNING: some answers came from the rules (AI unreachable or invalid);"
                " only the AI's own answers are scored below."
            )
        print(report(f"Claude, run {run}", result.ai_predictions))
        print()

    if len(runs) > 1:
        # Same email, different priority across runs = the AI is not fully consistent
        changed = [
            sample.subject
            for i, sample in enumerate(LABELLED)
            if len({r.predictions[i].predicted for r in runs}) > 1
        ]
        accuracies = ", ".join(f"{accuracy(r.ai_predictions):.0%}" for r in runs)
        print(f"=== Consistency over {len(runs)} runs ===")
        print(f"accuracy per run: {accuracies}")
        print(f"emails whose priority changed between runs: {len(changed)}")
        for subject in changed:
            print(f"  - {subject[:60]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
