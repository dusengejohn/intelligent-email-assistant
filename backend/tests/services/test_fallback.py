"""Tests for the rule-based fallback classifier (story 2.1, issue #46).

Pure unit tests: no AI, no network, no database (Email objects stay in memory).
"""

from datetime import UTC, datetime

import pytest

from app.models import ClassificationSource, Email, Priority
from app.priorities import default_minutes
from app.services.fallback import classify_fallback
from tests.data.labelled_emails import FIXED_EXAMPLES, LABELLED, LabelledEmail

MIN_ACCURACY = 0.80


def email(subject: str, body: str = "Hi, see subject.", sender: str = "ada@example.com") -> Email:
    return Email(
        sender_name="Ada",
        sender_email=sender,
        subject=subject,
        body=body,
        received_at=datetime(2026, 11, 22, 9, 0, tzinfo=UTC),
    )


# --- the labelled set ---------------------------------------------------------------


@pytest.mark.parametrize("sample", FIXED_EXAMPLES, ids=lambda s: s.subject)
def test_fixed_examples_get_the_expected_priority(sample: LabelledEmail) -> None:
    # The five examples named in the Epic 2 issue (#3) must be exact
    assert classify_fallback(sample.to_email()).priority == sample.expected


def test_accuracy_on_labelled_set_is_at_least_80_percent() -> None:
    misses = []
    for sample in LABELLED:
        got = classify_fallback(sample.to_email()).priority
        if got != sample.expected:
            misses.append(f"{sample.subject!r}: expected {sample.expected}, got {got}")

    accuracy = 1 - len(misses) / len(LABELLED)
    print(f"\nfallback accuracy: {accuracy:.0%} ({len(misses)} misses)")
    for miss in misses:
        print("  -", miss)
    assert accuracy >= MIN_ACCURACY, "\n".join(misses)


@pytest.mark.parametrize(
    "sample", [s for s in LABELLED if s.expected == Priority.CRITICAL], ids=lambda s: s.subject
)
def test_critical_email_is_never_classified_moderate_or_low(sample: LabelledEmail) -> None:
    # The costly mistake: an outage treated as routine. High is acceptable, lower is not.
    assert classify_fallback(sample.to_email()).priority in (Priority.CRITICAL, Priority.HIGH)


# --- individual rules ---------------------------------------------------------------


def test_automated_sender_with_critical_words_is_critical() -> None:
    # Rule order: critical words are checked before the "automated sender" rule
    result = classify_fallback(
        email("Production database DOWN", sender="alerts@monitoring.example.com")
    )

    assert result.priority == Priority.CRITICAL


def test_newsletter_mentioning_customers_is_low() -> None:
    # Rule order: clear low markers are checked before high words like "customer"
    result = classify_fallback(email("Monthly newsletter", "Stories from our customers."))

    assert result.priority == Priority.LOW


def test_plain_automated_notification_is_low() -> None:
    result = classify_fallback(email("Build #12 succeeded", sender="noreply@ci.example.com"))

    assert result.priority == Priority.LOW


@pytest.mark.parametrize(
    "text", ["Downloaded the report", "Cost breakdown attached", "Release slowdown next week"]
)
def test_words_inside_other_words_do_not_match(text: str) -> None:
    assert classify_fallback(email(text)).priority == Priority.MODERATE


@pytest.mark.parametrize("subject", ["OUTAGE in eu-west", "Outage in eu-west", "outage in eu-west"])
def test_matching_ignores_case(subject: str) -> None:
    assert classify_fallback(email(subject)).priority == Priority.CRITICAL


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Escalation from the CEO about the Northwind rollout", Priority.CRITICAL),
        ("Escalation: order delayed", Priority.HIGH),  # escalation without an exec
    ],
)
def test_escalation_is_critical_only_with_an_executive(subject: str, expected: Priority) -> None:
    assert classify_fallback(email(subject)).priority == expected


# --- the result ---------------------------------------------------------------------


def test_result_has_source_reason_and_default_minutes() -> None:
    result = classify_fallback(email("Website outage", "Everything returns 503."))

    assert result.source == ClassificationSource.FALLBACK
    assert result.suggested_response_minutes == default_minutes(Priority.CRITICAL)
    assert '"outage"' in result.reason.lower()  # names the word that matched
    assert result.reason.endswith(".")
    assert result.reason.count(". ") == 0  # one sentence
    assert len(result.reason) <= 200


def test_email_without_signals_is_a_normal_work_request() -> None:
    result = classify_fallback(email("Notes from today's sync", "Here are the notes."))

    assert result.priority == Priority.MODERATE
    assert result.suggested_response_minutes == default_minutes(Priority.MODERATE)
    assert "normal work request" in result.reason


def test_every_labelled_email_gets_a_valid_result() -> None:
    for sample in LABELLED:
        result = classify_fallback(sample.to_email())
        assert result.source == ClassificationSource.FALLBACK
        assert 1 <= len(result.reason) <= 200
        assert result.suggested_response_minutes == default_minutes(result.priority)


# --- regressions found on unseen Claude-generated emails ------------------------------
# These real subjects were misclassified by the first version of the rules (security
# alerts landed in LOW). Security and outage signals must win over "automated sender".


@pytest.mark.parametrize(
    ("subject", "sender"),
    [
        ("Suspicious login attempts on admin account jsmith", "alerts@example.com"),
        ("Unusual admin login from new device", "alerts@example.com"),
        ("Unauthorized access to the backup bucket", "security@example.com"),
        ("Phishing email reported by finance", "it@example.com"),
        ("Production checkout errors spiking since 9:40", "priya@example.com"),
        ("Payments API degraded in eu-west", "noreply@status.example.com"),
        ("Login service unavailable for EU users", "oncall@example.com"),
    ],
)
def test_security_and_outage_signals_are_critical(subject: str, sender: str) -> None:
    assert classify_fallback(email(subject, sender=sender)).priority == Priority.CRITICAL


@pytest.mark.parametrize(
    "subject",
    ["Login page copy review", "Unusual request: can we move the retro?", "Error handling RFC"],
)
def test_similar_harmless_words_are_not_critical(subject: str) -> None:
    # Guard against over-broad patterns: "login", "unusual", "error" alone aren't incidents
    assert classify_fallback(email(subject)).priority != Priority.CRITICAL
