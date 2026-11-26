"""Tests for the inbox client (story 3b.2, issue #81).

No real inbox: `FakeInbox` (tests/fakes.py) answers through `httpx.MockTransport`,
so every failure (refused, timeout, 401, 422, ...) can be played on demand.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.schemas import GeneratedEmail
from app.services.inbox import InboxClient, InboxConfigError, InboxError, get_inbox_client
from tests.fakes import FakeInbox, raw

TOKEN = "test-token-never-logged-0123"
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "inbox_url": "http://inbox.test:8000",
        "ingest_token": TOKEN,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def emails(n: int) -> list[GeneratedEmail]:
    return [GeneratedEmail.from_raw(raw(i), NOW) for i in range(n)]


def client_for(inbox: FakeInbox, **overrides: Any) -> InboxClient:
    return InboxClient(make_settings(**overrides), transport=inbox.transport)


def answer(status: int, body: Any = None) -> FakeInbox:
    return FakeInbox(lambda request: httpx.Response(status, json=body or {"detail": "x"}))


def fail_with(error: type[httpx.TransportError]) -> FakeInbox:
    def respond(request: httpx.Request) -> httpx.Response:
        raise error("simulated", request=request)

    return FakeInbox(respond)


# --- Success ---------------------------------------------------------------------


def test_deliver_posts_all_emails_with_the_token_and_returns_the_count() -> None:
    inbox = FakeInbox()

    created = client_for(inbox).deliver(emails(3))

    assert created == 3
    (request,) = inbox.requests
    assert request.method == "POST"
    assert str(request.url) == "http://inbox.test:8000/api/emails/ingest"
    assert request.headers["X-Ingest-Token"] == TOKEN
    sent = inbox.delivered()
    assert [e["subject"] for e in sent] == ["Subject 0", "Subject 1", "Subject 2"]
    assert set(sent[0]) == {"sender_name", "sender_email", "subject", "body", "received_at"}


def test_received_at_is_sent_as_utc_iso_8601() -> None:
    inbox = FakeInbox()

    client_for(inbox).deliver(emails(2))

    sent = inbox.delivered()
    assert sent[1]["received_at"] == "2026-11-25T11:00:00Z"  # raw(1) = 60 minutes ago
    parsed = datetime.fromisoformat(sent[1]["received_at"])
    assert parsed == NOW - timedelta(hours=1)


def test_trailing_slash_in_inbox_url_is_ignored() -> None:
    inbox = FakeInbox()

    client_for(inbox, inbox_url="http://inbox.test:8000/").deliver(emails(1))

    assert str(inbox.requests[0].url) == "http://inbox.test:8000/api/emails/ingest"


# --- Configuration -------------------------------------------------------------------


@pytest.mark.parametrize("token", [None, "", "   "])
def test_missing_token_is_a_config_error(token: str | None) -> None:
    with pytest.raises(InboxConfigError, match="INGEST_TOKEN"):
        get_inbox_client(make_settings(ingest_token=token))


def test_get_inbox_client_uses_the_settings() -> None:
    client = get_inbox_client(make_settings(inbox_url="http://backend:8000"))

    assert client.url == "http://backend:8000/api/emails/ingest"


# --- Failures ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("inbox", "expected"),
    [
        (fail_with(httpx.ConnectError), "could not be reached at http://inbox.test:8000"),
        (fail_with(httpx.ReadTimeout), "did not answer within 10 s"),
        (answer(401), "rejected the token"),
        (answer(503), "ingest disabled"),
        (answer(422), "rejected the emails as invalid"),
        (answer(500), "answered HTTP 500"),
        (answer(201, {"unexpected": True}), "unexpected answer"),
    ],
    ids=["refused", "timeout", "401", "503", "422", "500", "bad-201"],
)
def test_failures_raise_inbox_error_with_a_clear_message(inbox: FakeInbox, expected: str) -> None:
    with pytest.raises(InboxError, match=expected):
        client_for(inbox).deliver(emails(2))


def test_config_error_is_not_a_delivery_error() -> None:
    # 503 (our setup) and 502 (the inbox failed) are different problems
    assert not issubclass(InboxConfigError, InboxError)


def test_token_never_appears_in_errors_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    client_for(FakeInbox()).deliver(emails(1))
    with pytest.raises(InboxError) as failure:
        client_for(answer(401)).deliver(emails(1))

    assert TOKEN not in str(failure.value)
    assert TOKEN not in caplog.text
    assert "Delivered 1 emails to the inbox" in caplog.text
