"""Tests for PATCH /api/emails/{id} (story 2.4, issue #49).

Rows are inserted directly into the in-memory database (`session` fixture).
No AI is involved.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import ClassificationSource, Email, EmailStatus, Priority


def add_email(session: Session, **fields: Any) -> Email:
    """An email the AI classified as moderate (unless overridden)."""
    values: dict[str, Any] = {
        "sender_name": "Ada Lovelace",
        "sender_email": "ada@example.com",
        "subject": "Quarterly report",
        "body": "Please review.",
        "received_at": datetime(2026, 11, 22, 9, 0, tzinfo=UTC),
        "priority": Priority.MODERATE,
        "priority_reason": "A normal review request.",
        "classification_source": ClassificationSource.AI,
        "suggested_response_minutes": 25,
    }
    values.update(fields)
    email = Email.model_validate(values)
    session.add(email)
    session.commit()
    session.refresh(email)
    return email


def snapshot(session: Session, email_id: int | None) -> dict[str, Any]:
    session.expire_all()
    email = session.get(Email, email_id)
    assert email is not None
    return email.model_dump()


def patch(client: TestClient, email_id: int | None, body: dict[str, Any]) -> Any:
    return client.patch(f"/api/emails/{email_id}", json=body)


# --- priority override -----------------------------------------------------------


def test_priority_override_is_manual_with_default_minutes(
    client: TestClient, session: Session
) -> None:
    email = add_email(session)

    response = patch(client, email.id, {"priority": "high"})

    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "high"
    assert body["classification_source"] == "manual"
    assert body["priority_reason"] == "Set manually."
    assert body["suggested_response_minutes"] == 15
    # saved, not just returned
    assert client.get(f"/api/emails/{email.id}").json() == body


def test_minutes_follow_the_new_priority(client: TestClient, session: Session) -> None:
    email = add_email(session)

    body = patch(client, email.id, {"priority": "low"}).json()

    assert body["suggested_response_minutes"] == 5


def test_same_priority_as_the_ai_still_becomes_manual(client: TestClient, session: Session) -> None:
    email = add_email(session, priority=Priority.MODERATE)

    body = patch(client, email.id, {"priority": "moderate"}).json()

    assert body["classification_source"] == "manual"


def test_unclassified_email_can_get_a_manual_priority(client: TestClient, session: Session) -> None:
    email = add_email(
        session,
        priority=None,
        priority_reason=None,
        classification_source=None,
        suggested_response_minutes=None,
    )

    body = patch(client, email.id, {"priority": "critical"}).json()

    assert body["priority"] == "critical"
    assert body["classification_source"] == "manual"


# --- status ------------------------------------------------------------------------


def test_status_change_leaves_the_classification_alone(
    client: TestClient, session: Session
) -> None:
    email = add_email(session)
    before = snapshot(session, email.id)

    response = patch(client, email.id, {"status": "handled"})

    assert response.status_code == 200
    after = snapshot(session, email.id)
    assert after["status"] == EmailStatus.HANDLED
    assert {k: v for k, v in after.items() if k != "status"} == {
        k: v for k, v in before.items() if k != "status"
    }


def test_status_can_go_back_to_new(client: TestClient, session: Session) -> None:
    email = add_email(session, status=EmailStatus.HANDLED)

    assert patch(client, email.id, {"status": "new"}).json()["status"] == "new"


def test_priority_and_status_together(client: TestClient, session: Session) -> None:
    email = add_email(session)

    body = patch(client, email.id, {"priority": "critical", "status": "handled"}).json()

    assert body["priority"] == "critical"
    assert body["status"] == "handled"
    assert body["classification_source"] == "manual"


# --- invalid requests ------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"priority": "urgent"},
        {"priority": None},
        {"status": None},
        {"status": "archived"},
        {"subject": "Changed"},
        {"priority": "high", "subject": "Changed"},
    ],
    ids=[
        "empty",
        "unknown-priority",
        "null-priority",
        "null-status",
        "unknown-status",
        "unknown-field",
        "valid-plus-unknown-field",
    ],
)
def test_invalid_update_returns_422_and_changes_nothing(
    client: TestClient, session: Session, body: dict[str, Any]
) -> None:
    email = add_email(session)
    before = snapshot(session, email.id)

    response = patch(client, email.id, body)

    assert response.status_code == 422
    assert snapshot(session, email.id) == before


def test_unknown_email_returns_404(client: TestClient) -> None:
    response = client.patch("/api/emails/999", json={"status": "handled"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Email not found"}


def test_non_numeric_id_returns_422(client: TestClient) -> None:
    assert client.patch("/api/emails/abc", json={"status": "handled"}).status_code == 422


# --- works together with bulk classify (story 2.3) -------------------------------------


def test_manual_override_survives_bulk_classify(client: TestClient, session: Session) -> None:
    email = add_email(
        session,
        priority=None,
        priority_reason=None,
        classification_source=None,
        suggested_response_minutes=None,
    )
    patch(client, email.id, {"priority": "low"})

    body = client.post("/api/emails/classify").json()

    assert body["classified"] == 0  # nothing unclassified: the manual priority wins
    after = snapshot(session, email.id)
    assert after["priority"] == Priority.LOW
    assert after["classification_source"] == ClassificationSource.MANUAL


# --- documentation -------------------------------------------------------------------------


def test_patch_endpoint_is_documented(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()

    assert "patch" in spec["paths"]["/api/emails/{email_id}"]
    assert "EmailUpdate" in spec["components"]["schemas"]
