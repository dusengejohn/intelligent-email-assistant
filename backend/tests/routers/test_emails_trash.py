"""Tests for soft delete and the Trash (story 3.3, issue #64).

DELETE moves an email to the Trash (reversible); POST /restore brings it back;
DELETE /trash empties the Trash for good. Trashed emails are invisible
everywhere else.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import ClassificationSource, Email, EmailStatus, Priority

URL = "/api/emails"
NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
FIELDS = (
    "subject",
    "priority",
    "priority_reason",
    "classification_source",
    "suggested_response_minutes",
    "status",
    "received_at",
)


def add_email(session: Session, subject: str, hours_ago: float = 1, **fields: Any) -> Email:
    email = Email.model_validate(
        {
            "sender_name": "Ada",
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


def ids(client: TestClient, **params: Any) -> list[int]:
    response = client.get(URL, params=params)
    assert response.status_code == 200
    return [e["id"] for e in response.json()]


def delete(client: TestClient, email_id: int | None) -> Any:
    return client.delete(f"{URL}/{email_id}")


# --- delete (move to Trash) ---------------------------------------------------------


def test_delete_moves_the_email_to_the_trash(client: TestClient, session: Session) -> None:
    keep = add_email(session, "keep", priority=Priority.HIGH)
    gone = add_email(session, "gone", priority=Priority.HIGH)

    response = delete(client, gone.id)

    assert response.status_code == 204
    assert response.content == b""
    assert ids(client) == [keep.id]
    assert ids(client, trash="true") == [gone.id]
    trashed = client.get(f"{URL}/{gone.id}").json()  # still readable (reading pane)
    assert trashed["deleted_at"] is not None
    assert trashed["deleted_at"].endswith("Z")


def test_trashed_emails_are_left_out_of_the_summary(client: TestClient, session: Session) -> None:
    add_email(session, "a", priority=Priority.CRITICAL)
    gone = add_email(session, "b", priority=Priority.CRITICAL)
    delete(client, gone.id)

    summary = client.get(f"{URL}/summary").json()

    assert summary["all"] == 1
    assert summary["critical"] == 1
    assert summary["trash"] == 1


def test_bulk_classify_ignores_trashed_emails(client: TestClient, session: Session) -> None:
    active = add_email(session, "active")
    trashed = add_email(session, "trashed")
    delete(client, trashed.id)

    body = client.post(f"{URL}/classify").json()

    assert [e["id"] for e in body["emails"]] == [active.id]  # the trashed email stays as is
    assert body["classified"] == 1
    assert body["remaining"] == 0  # the trashed, unclassified email isn't "remaining"


# --- restore ---------------------------------------------------------------------------


def test_restore_brings_the_email_back_unchanged(client: TestClient, session: Session) -> None:
    email = add_email(
        session,
        "restore me",
        priority=Priority.MODERATE,
        priority_reason="A normal review request.",
        classification_source=ClassificationSource.AI,
        suggested_response_minutes=25,
        status=EmailStatus.HANDLED,
    )
    before = client.get(f"{URL}/{email.id}").json()
    delete(client, email.id)

    response = client.post(f"{URL}/{email.id}/restore")

    assert response.status_code == 200
    after = response.json()
    assert after["deleted_at"] is None
    assert {k: after[k] for k in FIELDS} == {k: before[k] for k in FIELDS}
    assert email.id in ids(client)
    assert ids(client, trash="true") == []


# --- empty the Trash -------------------------------------------------------------------


def test_empty_trash_deletes_only_trashed_emails_for_good(
    client: TestClient, session: Session
) -> None:
    keep = add_email(session, "keep")
    for subject in ("x", "y"):
        delete(client, add_email(session, subject).id)

    response = client.delete(f"{URL}/trash")  # must not be read as an email id

    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    assert ids(client) == [keep.id]
    assert ids(client, trash="true") == []
    assert client.get(f"{URL}/summary").json()["trash"] == 0


def test_empty_trash_when_empty(client: TestClient) -> None:
    assert client.delete(f"{URL}/trash").json() == {"deleted": 0}


def test_trash_is_ordered_by_deletion_time(client: TestClient, session: Session) -> None:
    critical = add_email(session, "critical", priority=Priority.CRITICAL)
    low = add_email(session, "low", priority=Priority.LOW)
    delete(client, critical.id)
    delete(client, low.id)  # deleted last

    assert ids(client, trash="true") == [low.id, critical.id]  # newest deleted first


# --- 404s --------------------------------------------------------------------------------


def test_delete_unknown_or_already_trashed_returns_404(
    client: TestClient, session: Session
) -> None:
    email = add_email(session, "once")
    delete(client, email.id)

    assert delete(client, email.id).status_code == 404
    assert delete(client, 999).json() == {"detail": "Email not found"}


def test_restore_active_or_unknown_returns_404(client: TestClient, session: Session) -> None:
    email = add_email(session, "active")

    assert client.post(f"{URL}/{email.id}/restore").status_code == 404
    assert client.post(f"{URL}/999/restore").status_code == 404


def test_trashed_email_cannot_be_changed_or_classified(
    client: TestClient, session: Session
) -> None:
    email = add_email(session, "in trash")
    delete(client, email.id)

    assert client.patch(f"{URL}/{email.id}", json={"priority": "high"}).status_code == 404
    assert client.post(f"{URL}/{email.id}/classify").status_code == 404
    assert session.get(Email, email.id).priority is None  # type: ignore[union-attr]


# --- summary consistency (extends story 3.1) ----------------------------------------------


def test_trash_count_matches_the_trash_list(client: TestClient, session: Session) -> None:
    for i in range(3):
        email = add_email(session, f"e{i}", priority=Priority.LOW)
        if i:
            delete(client, email.id)

    assert client.get(f"{URL}/summary").json()["trash"] == len(ids(client, trash="true"))


def test_trash_endpoints_are_documented(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "delete" in paths[f"{URL}/trash"]
    assert "delete" in paths[f"{URL}/{{email_id}}"]
    assert "post" in paths[f"{URL}/{{email_id}}/restore"]
