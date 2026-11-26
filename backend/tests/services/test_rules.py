"""Tests for the keyword-rules classifier (story 2.1, #46; rules only since #92).

Pure unit tests: no AI, no network, no database (Email objects stay in memory).
"""

from datetime import UTC, datetime

import pytest

from app.models import ClassificationSource, Email, Priority
from app.priorities import default_minutes
from app.services.rules import MAX_KEYWORDS, classify_by_rules
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
    assert classify_by_rules(sample.to_email()).priority == sample.expected


def test_accuracy_on_labelled_set_is_at_least_80_percent() -> None:
    misses = []
    for sample in LABELLED:
        got = classify_by_rules(sample.to_email()).priority
        if got != sample.expected:
            misses.append(f"{sample.subject!r}: expected {sample.expected}, got {got}")

    accuracy = 1 - len(misses) / len(LABELLED)
    print(f"\nrules accuracy: {accuracy:.0%} ({len(misses)} misses)")
    for miss in misses:
        print("  -", miss)
    assert accuracy >= MIN_ACCURACY, "\n".join(misses)


@pytest.mark.parametrize(
    "sample", [s for s in LABELLED if s.expected == Priority.CRITICAL], ids=lambda s: s.subject
)
def test_critical_email_is_never_classified_moderate_or_low(sample: LabelledEmail) -> None:
    # The costly mistake: an outage treated as routine. High is acceptable, lower is not.
    assert classify_by_rules(sample.to_email()).priority in (Priority.CRITICAL, Priority.HIGH)


# --- individual rules ---------------------------------------------------------------


def test_automated_sender_with_critical_words_is_critical() -> None:
    # Rule order: critical words are checked before the "automated sender" rule
    result = classify_by_rules(
        email("Production database DOWN", sender="alerts@monitoring.example.com")
    )

    assert result.priority == Priority.CRITICAL


def test_newsletter_mentioning_customers_is_low() -> None:
    # Rule order: clear low markers are checked before high words like "customer"
    result = classify_by_rules(email("Monthly newsletter", "Stories from our customers."))

    assert result.priority == Priority.LOW


def test_plain_automated_notification_is_low() -> None:
    result = classify_by_rules(email("Build #12 succeeded", sender="noreply@ci.example.com"))

    assert result.priority == Priority.LOW


@pytest.mark.parametrize(
    "text", ["Downloaded the report", "Cost breakdown attached", "Release slowdown next week"]
)
def test_words_inside_other_words_do_not_match(text: str) -> None:
    assert classify_by_rules(email(text)).priority == Priority.MODERATE


@pytest.mark.parametrize("subject", ["OUTAGE in eu-west", "Outage in eu-west", "outage in eu-west"])
def test_matching_ignores_case(subject: str) -> None:
    assert classify_by_rules(email(subject)).priority == Priority.CRITICAL


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Escalation from the CEO about the Northwind rollout", Priority.CRITICAL),
        ("Escalation: order delayed", Priority.HIGH),  # escalation without an exec
    ],
)
def test_escalation_is_critical_only_with_an_executive(subject: str, expected: Priority) -> None:
    assert classify_by_rules(email(subject)).priority == expected


# --- the result ---------------------------------------------------------------------


def test_result_has_source_reason_and_default_minutes() -> None:
    result = classify_by_rules(email("Website outage", "Everything returns 503."))

    assert result.source == ClassificationSource.RULES
    assert result.suggested_response_minutes == default_minutes(Priority.CRITICAL)
    assert result.reason == 'Critical: matched "outage" (an outage).'


# --- the reason names the keywords that decided (#92) -------------------------------


def test_reason_lists_every_keyword_of_the_deciding_priority() -> None:
    result = classify_by_rules(
        email("Website outage", "The production database is down and a breach is suspected.")
    )

    assert result.priority == Priority.CRITICAL
    assert result.reason == (
        'Critical: matched "outage", "database is down", "breach" '
        "(an outage, a service that is down, a security incident)."
    )


def test_reason_keeps_the_order_found_and_drops_duplicates_ignoring_case() -> None:
    result = classify_by_rules(
        email("Customer escalation", "The customer is blocked. CUSTOMER says ASAP. Customer.")
    )

    assert result.priority == Priority.HIGH
    assert result.reason == (
        'High: matched "Customer", "escalation", "blocked", "ASAP" '
        "(a customer issue, an escalation, a blocked colleague, an urgent request)."
    )


def test_reason_only_lists_keywords_of_the_winning_priority() -> None:
    # "customer" is a high word, but the newsletter (low) rule decides first
    result = classify_by_rules(email("Monthly newsletter", "Stories from our customers. FYI."))

    assert result.priority == Priority.LOW
    assert result.reason == 'Low: matched "newsletter", "FYI" (a newsletter or FYI).'
    assert "customer" not in result.reason.lower()


def test_reason_lists_at_most_the_first_keywords() -> None:
    body = "outage breach ransomware malware phishing lawsuit"
    result = classify_by_rules(email("Bad day", body))

    assert MAX_KEYWORDS == 4
    assert result.reason.startswith(
        'Critical: matched "outage", "breach", "ransomware", "malware" ('
    )


def test_reason_never_exceeds_200_characters() -> None:
    # Long matches (up to 40 characters each) and four signals would be too long
    body = (
        "The payments service is unreachable. The website is unreachable. "
        "Suspicious admin sign-in activity. Escalation to the vice president. "
        "Errors are spiking. Deadline today."
    )
    result = classify_by_rules(email("Production website went down", body))

    assert result.priority == Priority.CRITICAL
    assert len(result.reason) <= 200
    assert result.reason.startswith("Critical: matched ")
    assert result.reason.endswith(".")


def test_automated_sender_reason() -> None:
    result = classify_by_rules(email("Build #12 succeeded", sender="noreply@ci.example.com"))

    assert result.reason == 'Low: sent by an automated address ("noreply@").'


def test_email_without_signals_is_a_normal_work_request() -> None:
    result = classify_by_rules(email("Notes from today's sync", "Here are the notes."))

    assert result.priority == Priority.MODERATE
    assert result.suggested_response_minutes == default_minutes(Priority.MODERATE)
    assert result.reason == "Moderate: no urgent or low-priority keywords found."


def test_every_labelled_email_gets_a_valid_result() -> None:
    for sample in LABELLED:
        result = classify_by_rules(sample.to_email())
        assert result.source == ClassificationSource.RULES
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
    assert classify_by_rules(email(subject, sender=sender)).priority == Priority.CRITICAL


@pytest.mark.parametrize(
    "subject",
    ["Login page copy review", "Unusual request: can we move the retro?", "Error handling RFC"],
)
def test_similar_harmless_words_are_not_critical(subject: str) -> None:
    # Guard against over-broad patterns: "login", "unusual", "error" alone aren't incidents
    assert classify_by_rules(email(subject)).priority != Priority.CRITICAL
