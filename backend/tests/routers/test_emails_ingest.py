"""Tests for POST /api/emails/ingest (story 3b.1, issue #80).

Another service (the generator) delivers emails here with a shared token in the
`X-Ingest-Token` header. The inbox never trusts the sender: every email is
validated again, and one bad email rejects the whole request (all or nothing).
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.models import Email

URL = "/api/emails/ingest"
TOKEN = "test-ingest-token-0123456789"
HEADERS = {"X-Ingest-Token": TOKEN}


@pytest.fixture(autouse=True)
def ingest_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure the inbox's token (conftest clears the settings cache per test)."""
    monkeypatch.setenv("INGEST_TOKEN", TOKEN)


def email(i: int = 0, **changes: Any) -> dict[str, Any]:
    """One valid email as the generator would send it (JSON-ready)."""
    data: dict[str, Any] = {
        "sender_name": f"Sender {i}",
        "sender_email": f"sender{i}@example.com",
        "subject": f"Subject {i}",
        "body": f"Body of email {i}.",
        "received_at": (datetime.now(UTC) - timedelta(minutes=10 + i)).isoformat(),
    }
    data.update(changes)
    return data


def emails(n: int) -> dict[str, Any]:
    return {"emails": [email(i) for i in range(n)]}


def row_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(Email)).one()


# --- Happy path ------------------------------------------------------------------


def test_ingest_saves_all_emails_and_returns_their_ids(
    client: TestClient, session: Session
) -> None:
    response = client.post(URL, json=emails(10), headers=HEADERS)

    assert response.status_code == 201
    body = response.json()
    assert body["created"] == 10
    assert len(body["ids"]) == 10
    # Throw away anything not committed: the emails must really be saved
    session.rollback()
    assert row_count(session) == 10


def test_ingested_emails_arrive_unclassified_and_new(client: TestClient) -> None:
    ids = client.post(URL, json=emails(3), headers=HEADERS).json()["ids"]

    listed = client.get("/api/emails").json()

    assert sorted(e["id"] for e in listed) == sorted(ids)
    for item in listed:
        assert item["priority"] is None
        assert item["classification_source"] is None
        assert item["status"] == "new"
        assert item["received_at"].endswith("Z")


def test_ingest_keeps_the_fields_as_sent(client: TestClient) -> None:
    sent = email(0, subject="  Server room temperature alarm  ")
    new_id = client.post(URL, json={"emails": [sent]}, headers=HEADERS).json()["ids"][0]

    saved = client.get(f"/api/emails/{new_id}").json()

    assert saved["subject"] == "Server room temperature alarm"  # whitespace stripped
    assert saved["sender_email"] == "sender0@example.com"
    assert datetime.fromisoformat(saved["received_at"]) == datetime.fromisoformat(
        sent["received_at"]
    )


def test_ingest_accepts_50_emails(client: TestClient, session: Session) -> None:
    response = client.post(URL, json=emails(50), headers=HEADERS)

    assert response.status_code == 201
    assert row_count(session) == 50


# --- The shared token --------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Ingest-Token": "wrong"}, {"X-Ingest-Token": ""}, {"X-Ingest-Token": TOKEN + "x"}],
    ids=["missing", "wrong", "empty", "longer"],
)
def test_missing_or_wrong_token_is_401(
    client: TestClient, session: Session, headers: dict[str, str]
) -> None:
    response = client.post(URL, json=emails(2), headers=headers)

    assert response.status_code == 401
    assert row_count(session) == 0


def test_token_is_checked_before_the_body(client: TestClient) -> None:
    # An outsider must not learn our validation rules: 401, not 422
    response = client.post(URL, json={"emails": [{"nonsense": 1}]}, headers={"X-Ingest-Token": "x"})

    assert response.status_code == 401


def test_ingest_is_disabled_without_a_configured_token(
    client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("INGEST_TOKEN")

    response = client.post(URL, json=emails(2), headers=HEADERS)

    assert response.status_code == 503
    assert "INGEST_TOKEN" in response.json()["detail"]
    assert row_count(session) == 0


def test_blank_configured_token_also_disables_ingest(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A blank setting must never mean "an empty header is the right token"
    monkeypatch.setenv("INGEST_TOKEN", "  ")

    response = client.post(URL, json=emails(1), headers={"X-Ingest-Token": ""})

    assert response.status_code == 503


def test_token_never_appears_in_responses_or_logs(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    ok = client.post(URL, json=emails(1), headers=HEADERS)
    bad = client.post(URL, json={"emails": [email(0, subject="")]}, headers=HEADERS)

    assert ok.status_code == 201
    assert bad.status_code == 422
    assert TOKEN not in ok.text
    assert TOKEN not in bad.text
    assert TOKEN not in caplog.text
    assert "Ingested 1 emails" in caplog.text


# --- Never trust the sender: all or nothing -------------------------------------------


def _future() -> str:
    return (datetime.now(UTC) + timedelta(hours=1)).isoformat()


def _too_old() -> str:
    return (datetime.now(UTC) - timedelta(hours=49)).isoformat()


@pytest.mark.parametrize(
    "bad",
    [
        email(9, sender_email="ceo@realcompany.com"),
        email(9, sender_email="not-an-email"),
        email(9, subject=""),
        email(9, body="x" * 2001),
        email(9, received_at=_future()),
        email(9, received_at=_too_old()),
        email(9, received_at="2026-11-25T10:00:00"),  # naive: no timezone
        email(9, priority="low"),  # the sender may not set our fields
        email(9, status="handled"),
        {k: v for k, v in email(9).items() if k != "body"},
    ],
    ids=[
        "real-domain",
        "bad-address",
        "empty-subject",
        "body-too-long",
        "future",
        "older-than-48h",
        "naive-date",
        "extra-priority",
        "extra-status",
        "missing-body",
    ],
)
def test_one_invalid_email_rejects_the_whole_request(
    client: TestClient, session: Session, bad: dict[str, Any]
) -> None:
    payload = {"emails": [email(0), email(1), bad]}

    response = client.post(URL, json=payload, headers=HEADERS)

    assert response.status_code == 422
    assert row_count(session) == 0


@pytest.mark.parametrize("n", [0, 51])
def test_batch_size_must_be_1_to_50(client: TestClient, session: Session, n: int) -> None:
    response = client.post(URL, json=emails(n), headers=HEADERS)

    assert response.status_code == 422
    assert row_count(session) == 0


def test_unknown_top_level_field_is_rejected(client: TestClient) -> None:
    payload = {**emails(1), "deliver_to": "someone-else"}

    response = client.post(URL, json=payload, headers=HEADERS)

    assert response.status_code == 422
