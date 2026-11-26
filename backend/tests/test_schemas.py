"""Tests for the IncomingEmail rules (story 1.4; renamed in story 3b.5).

Every email the inbox saves must pass them. They arrive through the ingest API
(tests/routers/test_emails_ingest.py tests that endpoint end to end).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.schemas import IncomingEmail


def incoming(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "sender_name": "Maria Chen",
        "sender_email": "maria.chen@example.com",
        "subject": "Database migration tonight",
        "body": "Hi team, the migration starts at 22:00. Please confirm. Maria",
        "received_at": datetime.now(UTC) - timedelta(minutes=90),
    }
    values.update(overrides)
    return values


def test_valid_email_keeps_a_utc_received_at() -> None:
    sent = datetime.now(UTC) - timedelta(minutes=90)

    email = IncomingEmail.model_validate(incoming(received_at=sent))

    assert email.received_at == sent
    assert email.received_at.tzinfo == UTC


def test_other_timezones_are_converted_to_utc() -> None:
    toronto = datetime.now(UTC).astimezone(ZoneInfo("America/Toronto"))

    email = IncomingEmail.model_validate(incoming(received_at=toronto))

    assert email.received_at.tzinfo == UTC
    assert email.received_at == toronto


def test_text_fields_are_trimmed() -> None:
    email = IncomingEmail.model_validate(incoming(sender_name="  Maria Chen ", subject=" Hello  "))

    assert email.sender_name == "Maria Chen"
    assert email.subject == "Hello"


@pytest.mark.parametrize("address", ["ops@example.com", "alerts@it.example.org", "ceo@EXAMPLE.NET"])
def test_fictional_domains_are_accepted(address: str) -> None:
    assert IncomingEmail.model_validate(incoming(sender_email=address))


def _hours_ago(hours: float) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("sender_name", "   "),
        ("sender_name", "x" * 101),
        ("subject", ""),
        ("subject", "x" * 201),
        ("body", ""),
        ("body", "x" * 2001),
        ("sender_email", "not-an-address"),
        ("sender_email", "bob@acme.test"),  # special-use domain: rejected by EmailStr
        ("sender_email", "john@gmail.com"),  # real-looking domain: not fictional
        ("sender_email", "x@notexample.com"),  # suffix trick: not a subdomain of example.com
        ("received_at", _hours_ago(-0.1)),  # in the future
        ("received_at", _hours_ago(48.1)),  # older than 48 h
        ("received_at", datetime(2026, 11, 25, 10, 0)),  # naive: no timezone
    ],
)
def test_invalid_values_are_rejected(field: str, bad_value: Any) -> None:
    with pytest.raises(ValidationError):
        IncomingEmail.model_validate(incoming(**{field: bad_value}))


@pytest.mark.parametrize("hours", [0, 47.99])
def test_window_boundaries_are_accepted(hours: float) -> None:
    assert IncomingEmail.model_validate(incoming(received_at=_hours_ago(hours)))
