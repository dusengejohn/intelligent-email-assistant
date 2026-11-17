"""Tests for the strict GeneratedEmail rules (story 1.4, issue #30)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas import GeneratedEmail, RawEmail


def raw(**overrides: Any) -> RawEmail:
    values: dict[str, Any] = {
        "sender_name": "Maria Chen",
        "sender_email": "maria.chen@example.com",
        "subject": "Database migration tonight",
        "body": "Hi team, the migration starts at 22:00. Please confirm. Maria",
        "received_minutes_ago": 90,
    }
    values.update(overrides)
    return RawEmail(**values)


def test_valid_email_gets_utc_received_at_from_minutes_ago() -> None:
    now = datetime.now(UTC)

    email = GeneratedEmail.from_raw(raw(received_minutes_ago=90), now)

    assert email.received_at == now - timedelta(minutes=90)
    assert email.received_at.tzinfo == UTC
    assert email.sender_email == "maria.chen@example.com"


def test_text_fields_are_trimmed() -> None:
    email = GeneratedEmail.from_raw(
        raw(sender_name="  Maria Chen ", subject=" Hello  "), datetime.now(UTC)
    )

    assert email.sender_name == "Maria Chen"
    assert email.subject == "Hello"


@pytest.mark.parametrize("address", ["ops@example.com", "alerts@it.example.org", "ceo@EXAMPLE.NET"])
def test_fictional_domains_are_accepted(address: str) -> None:
    assert GeneratedEmail.from_raw(raw(sender_email=address), datetime.now(UTC))


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
        ("received_minutes_ago", -1),  # in the future
        ("received_minutes_ago", 2881),  # older than 48 h
    ],
)
def test_invalid_values_are_rejected(field: str, bad_value: Any) -> None:
    with pytest.raises(ValidationError):
        GeneratedEmail.from_raw(raw(**{field: bad_value}), datetime.now(UTC))


@pytest.mark.parametrize("minutes", [0, 2880])
def test_window_boundaries_are_accepted(minutes: int) -> None:
    assert GeneratedEmail.from_raw(raw(received_minutes_ago=minutes), datetime.now(UTC))
