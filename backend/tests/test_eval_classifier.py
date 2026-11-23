"""Tests for the classifier eval script's helpers (story 2.6, issue #51).

Only the pure helpers and the offline paths are tested here: the real eval calls
Claude and is run by hand, never in tests or CI.
"""

from typing import Any

import pytest

from app.models import ClassificationSource, Priority
from app.schemas import Classification
from app.services.errors import AIServiceError
from scripts.eval_classifier import (
    Prediction,
    accuracy,
    confusion_matrix,
    critical_misses,
    evaluate,
    format_matrix,
    main,
)
from tests.data.labelled_emails import LABELLED
from tests.fakes import EchoClassifierAI

C, H, M, L = Priority.CRITICAL, Priority.HIGH, Priority.MODERATE, Priority.LOW


def prediction(expected: Priority, predicted: Priority, **kwargs: Any) -> Prediction:
    sample = next(s for s in LABELLED if s.expected == expected)
    result = Classification(
        priority=predicted,
        reason="Test reason.",
        suggested_response_minutes=10,
        source=kwargs.get("source", ClassificationSource.AI),
    )
    return Prediction(sample=sample, result=result)


# --- pure helpers -------------------------------------------------------------------


def test_accuracy_is_the_share_of_exact_matches() -> None:
    preds = [prediction(C, C), prediction(H, H), prediction(M, M), prediction(L, M)]

    assert accuracy(preds) == 0.75


def test_accuracy_of_nothing_is_zero() -> None:
    assert accuracy([]) == 0.0


def test_confusion_matrix_counts_every_cell() -> None:
    preds = [prediction(C, C), prediction(C, H), prediction(L, M), prediction(L, M)]

    matrix = confusion_matrix(preds)

    assert list(matrix) == [C, H, M, L]  # brief §7 order
    assert all(list(row) == [C, H, M, L] for row in matrix.values())
    assert matrix[C][C] == 1
    assert matrix[C][H] == 1
    assert matrix[L][M] == 2
    assert sum(sum(row.values()) for row in matrix.values()) == 4


def test_critical_misses_are_criticals_predicted_moderate_or_low() -> None:
    to_high = prediction(C, H)  # acceptable: still urgent
    to_moderate = prediction(C, M)
    to_low = prediction(C, L)
    other = prediction(H, L)  # not a critical email

    assert critical_misses([to_high, to_moderate, to_low, other]) == [to_moderate, to_low]


def test_format_matrix_lists_priorities_in_order() -> None:
    text = format_matrix(confusion_matrix([prediction(C, C), prediction(L, M)]))
    lines = text.splitlines()

    assert "critical" in lines[0] and "low" in lines[0]  # header
    assert [line.split()[0] for line in lines[1:]] == ["critical", "high", "moderate", "low"]
    assert lines[1].split()[1:] == ["1", "0", "0", "0"]
    assert lines[4].split()[1:] == ["0", "0", "1", "0"]


# --- evaluate() -----------------------------------------------------------------------


def test_evaluate_with_ai_counts_sources() -> None:
    result = evaluate(LABELLED, EchoClassifierAI(priority="high"))  # type: ignore[arg-type]

    assert len(result.predictions) == len(LABELLED)
    assert result.by_source == {"ai": len(LABELLED), "fallback": 0}
    assert result.ai_answered_all
    assert {p.predicted for p in result.predictions} == {H}
    expected_correct = sum(s.expected == H for s in LABELLED)
    assert accuracy(result.predictions) == pytest.approx(expected_correct / len(LABELLED))


def test_evaluate_when_the_ai_is_unreachable_flags_the_ai_score() -> None:
    failing = EchoClassifierAI(error=AIServiceError("could not reach the AI service."))

    result = evaluate(LABELLED, failing)  # type: ignore[arg-type]

    assert result.by_source == {"ai": 0, "fallback": len(LABELLED)}
    assert not result.ai_answered_all
    assert result.ai_predictions == []  # nothing to score as "AI"


def test_evaluate_without_ai_uses_the_rules() -> None:
    result = evaluate(LABELLED, None)

    assert result.by_source == {"ai": 0, "fallback": len(LABELLED)}
    assert accuracy(result.predictions) >= 0.80  # same bar as story 2.1


# --- main() ---------------------------------------------------------------------------


def test_main_without_a_key_runs_the_rules_and_skips_the_ai(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # conftest.py removes ANTHROPIC_API_KEY and hides the real .env
    exit_code = main(["--runs", "1"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Rules (fallback)" in out
    assert "accuracy" in out.lower()
    assert "AI part skipped" in out
