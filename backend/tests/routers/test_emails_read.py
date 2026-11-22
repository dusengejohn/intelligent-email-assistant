"""Tests for GET /api/emails and GET /api/emails/{id} (story 1.6, issue #32).

Rows are inserted directly into the in-memory database (`session` fixture);
`client` reads them through the API.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Email, EmailStatus, Priority

URL = "/api/emails"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def add_email(session: Session, subject: str, hours_ago: float = 1, **fields: Any) -> Email:
    email = Email.model_validate(
        {
            "sender_name": "Ada Lovelace",
            "sender_email": "ada@example.com",
            "subject": subject,
            "body": "Body",
            "received_at": NOW - timedelta(hours=hours_ago),
            **fields,
        }
    )
    session.add(email)
    session.commit()
    session.refresh(email)
    return email


def subjects(response_json: list[dict[str, Any]]) -> list[str]:
    return [email["subject"] for email in response_json]


# --- GET /api/emails --------------------------------------------------------


def test_list_returns_all_emails_newest_first(client: TestClient, session: Session) -> None:
    add_email(session, "middle", hours_ago=5)
    add_email(session, "newest", hours_ago=1)
    add_email(session, "oldest", hours_ago=30)

    response = client.get(URL)

    assert response.status_code == 200
    assert subjects(response.json()) == ["newest", "middle", "oldest"]


def test_same_received_at_is_ordered_by_id_descending(client: TestClient, session: Session) -> None:
    first = add_email(session, "first saved", hours_ago=2)
    second = add_email(session, "second saved", hours_ago=2)

    ids = [email["id"] for email in client.get(URL).json()]

    assert ids == [second.id, first.id]


def test_empty_database_returns_empty_list(client: TestClient) -> None:
    response = client.get(URL)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("value", ["new", "handled"])
def test_filter_by_status(client: TestClient, session: Session, value: str) -> None:
    add_email(session, "new one", status=EmailStatus.NEW)
    add_email(session, "handled one", status=EmailStatus.HANDLED)

    response = client.get(URL, params={"status": value})

    assert response.status_code == 200
    assert subjects(response.json()) == [f"{value} one"]


def test_filter_by_priority(client: TestClient, session: Session) -> None:
    add_email(session, "high", priority=Priority.HIGH)
    add_email(session, "low", priority=Priority.LOW)
    add_email(session, "unclassified")

    response = client.get(URL, params={"priority": "high"})

    assert subjects(response.json()) == ["high"]


def test_filters_combine(client: TestClient, session: Session) -> None:
    add_email(session, "high new", priority=Priority.HIGH)
    add_email(session, "high handled", priority=Priority.HIGH, status=EmailStatus.HANDLED)
    add_email(session, "low new", priority=Priority.LOW)

    response = client.get(URL, params={"priority": "high", "status": "new"})

    assert subjects(response.json()) == ["high new"]


@pytest.mark.parametrize("params", [{"status": "archived"}, {"priority": "urgent"}])
def test_invalid_filter_value_returns_422(client: TestClient, params: dict[str, str]) -> None:
    assert client.get(URL, params=params).status_code == 422


# --- GET /api/emails/{id} ---------------------------------------------------


def test_get_one_email(client: TestClient, session: Session) -> None:
    saved = add_email(session, "find me", hours_ago=3)

    response = client.get(f"{URL}/{saved.id}")

    assert response.status_code == 200
    email = response.json()
    assert email["id"] == saved.id
    assert email["subject"] == "find me"
    assert email["status"] == "new"
    assert email["received_at"] == "2026-11-17T09:00:00Z"  # UTC-aware


def test_missing_email_returns_404(client: TestClient) -> None:
    response = client.get(f"{URL}/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Email not found"}


def test_non_numeric_id_returns_422(client: TestClient) -> None:
    assert client.get(f"{URL}/abc").status_code == 422


# --- documentation -----------------------------------------------------------


def test_read_endpoints_are_documented_with_enum_values(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()

    assert "get" in spec["paths"][URL]
    assert "get" in spec["paths"][f"{URL}/{{email_id}}"]
    assert set(spec["components"]["schemas"]["EmailStatus"]["enum"]) == {"new", "handled"}
