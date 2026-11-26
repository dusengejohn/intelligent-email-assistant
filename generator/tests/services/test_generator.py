"""Tests for the email generator (copied from the inbox, story 1.4 / 3b.2).

Fakes: tests/fakes.py.
"""

import logging
from datetime import UTC, datetime, timedelta

import pytest

from app.schemas import GeneratedBatch, GeneratedEmail
from app.services.errors import AIServiceError
from app.services.generator import generate_emails
from tests.fakes import FakeAI, batch, raw


def generate(ai: FakeAI, count: int, scenario: str | None = None) -> list[GeneratedEmail]:
    return generate_emails(ai, count=count, scenario=scenario)  # type: ignore[arg-type]


def test_ten_valid_emails_are_returned_with_recent_utc_timestamps() -> None:
    before = datetime.now(UTC)

    emails = generate(FakeAI(batch(10)), count=10)

    assert len(emails) == 10
    assert all(isinstance(email, GeneratedEmail) for email in emails)
    for email in emails:
        assert email.received_at.tzinfo == UTC
        assert before - timedelta(hours=47) <= email.received_at <= datetime.now(UTC)


def test_invalid_items_are_skipped_and_counted(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.services.generator")
    items = batch(10).emails
    items[3] = raw(3, sender_email="not-an-address")
    items[7] = raw(7, subject="")

    emails = generate(FakeAI(GeneratedBatch(emails=items)), count=10)

    assert len(emails) == 8
    assert "2 skipped" in caplog.text
    assert "SECRET-BODY-TEXT" not in caplog.text  # counts only, never email content


def test_no_valid_items_raises_service_error() -> None:
    bad = GeneratedBatch(emails=[raw(i, sender_email="john@gmail.com") for i in range(3)])

    with pytest.raises(AIServiceError, match="no valid emails"):
        generate(FakeAI(bad), count=3)


def test_empty_batch_raises_service_error() -> None:
    with pytest.raises(AIServiceError):
        generate(FakeAI(GeneratedBatch(emails=[])), count=3)


def test_extra_items_are_cut_to_count() -> None:
    emails = generate(FakeAI(batch(8)), count=5)

    assert len(emails) == 5


def test_large_count_is_split_into_batches_of_ten() -> None:
    ai = FakeAI(batch(10), batch(10, start=10), batch(5, start=20))

    emails = generate(ai, count=25)

    assert len(emails) == 25
    assert len(ai.calls) == 3
    assert ["exactly 10 " in c["prompt"] for c in ai.calls] == [True, True, False]
    assert "exactly 5 " in ai.calls[2]["prompt"]


def test_failing_batch_fails_the_whole_request() -> None:
    ai = FakeAI(batch(10), AIServiceError("AI request timed out; try again."))

    with pytest.raises(AIServiceError, match="timed out"):
        generate(ai, count=20)


def test_prompt_includes_scenario_and_forbids_priority_labels() -> None:
    ai = FakeAI(batch(3))

    generate(ai, count=3, scenario="IT infrastructure team")

    (call,) = ai.calls
    assert "IT infrastructure team" in call["prompt"]
    assert "do not label" in call["system"].lower()
    assert "example.com" in call["system"]
    assert call["output_model"] is GeneratedBatch


def test_prompt_without_scenario_has_no_scenario_line() -> None:
    ai = FakeAI(batch(3))

    generate(ai, count=3)

    assert "scenario" not in ai.calls[0]["prompt"].lower()


@pytest.mark.parametrize("count", [0, -1])
def test_count_below_one_is_rejected(count: int) -> None:
    with pytest.raises(ValueError):
        generate(FakeAI(), count=count)


def test_prompt_asks_for_at_most_47_hours() -> None:
    # Stricter than the inbox's 48 h: emails must still be valid when delivered
    ai = FakeAI(batch(1))

    generate(ai, count=1)

    assert "0 to 2820" in ai.calls[0]["system"]
