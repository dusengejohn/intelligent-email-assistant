"""Tests for the classify endpoints (story 2.3, #48; keyword rules only since #92).

`client` and `session` (conftest.py) use the in-memory database. No AI and no
API key are involved: the inbox classifies with keyword rules only.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import ClassificationSource, Email, Priority

URL = "/api/emails/classify"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
APP_DIR = Path(__file__).resolve().parents[2] / "app"


def add_email(
    session: Session, subject: str = "Notes", hours_ago: float = 1, **fields: Any
) -> Email:
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


def reload(session: Session, email: Email) -> Email:
    session.expire_all()
    loaded = session.get(Email, email.id)
    assert loaded is not None
    return loaded


# --- POST /api/emails/classify -------------------------------------------------------


def test_classify_uses_the_keyword_rules_and_saves(client: TestClient, session: Session) -> None:
    outage = add_email(session, "Website outage")
    add_email(session, "Weekly newsletter")
    add_email(session, "Notes from the sync")

    response = client.post(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["classified"] == 3
    assert body["remaining"] == 0
    assert "by_source" not in body  # only one source now
    priorities = {e["subject"]: e["priority"] for e in body["emails"]}
    assert priorities == {
        "Website outage": "critical",
        "Weekly newsletter": "low",
        "Notes from the sync": "moderate",
    }
    assert {e["classification_source"] for e in body["emails"]} == {"rules"}
    saved = reload(session, outage)
    assert saved.priority == Priority.CRITICAL
    assert saved.priority_reason == 'Critical: matched "outage" (an outage).'
    assert saved.classification_source == ClassificationSource.RULES


def test_at_most_50_per_request_newest_first(client: TestClient, session: Session) -> None:
    emails = [add_email(session, f"Email {i}", hours_ago=i) for i in range(60)]  # 0 = newest

    first = client.post(URL).json()

    assert first["classified"] == 50
    assert first["remaining"] == 10
    assert {e["id"] for e in first["emails"]} == {e.id for e in emails[:50]}

    second = client.post(URL).json()

    assert second["classified"] == 10
    assert second["remaining"] == 0
    assert {e["id"] for e in second["emails"]} == {e.id for e in emails[50:]}


def test_nothing_to_classify(client: TestClient, session: Session) -> None:
    add_email(session, "Done", priority=Priority.LOW, classification_source="rules")

    assert client.post(URL).json() == {"classified": 0, "remaining": 0, "emails": []}


def test_ai_and_manual_labels_are_left_alone(client: TestClient, session: Session) -> None:
    # Decision (#92): emails Claude classified before keep their label; manual wins
    by_ai = add_email(
        session,
        "Website outage",
        priority=Priority.MODERATE,
        priority_reason="Claude's reason.",
        classification_source="ai",
        suggested_response_minutes=10,
    )
    manual = add_email(
        session,
        "Production database is down",
        priority=Priority.LOW,
        priority_reason="Set manually.",
        classification_source="manual",
        suggested_response_minutes=5,
    )
    new = add_email(session, "New one")

    body = client.post(URL).json()

    assert [e["id"] for e in body["emails"]] == [new.id]
    kept_ai = reload(session, by_ai)
    assert (kept_ai.priority, kept_ai.classification_source) == (
        Priority.MODERATE,
        ClassificationSource.AI,
    )
    assert kept_ai.priority_reason == "Claude's reason."
    kept_manual = reload(session, manual)
    assert (kept_manual.priority, kept_manual.classification_source) == (
        Priority.LOW,
        ClassificationSource.MANUAL,
    )


# --- POST /api/emails/{id}/classify ("Classify by keywords") -------------------------


def test_classify_one_names_the_keywords(client: TestClient, session: Session) -> None:
    email = add_email(session, "Customer escalation", body="The customer is blocked.")

    response = client.post(f"/api/emails/{email.id}/classify")

    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "high"
    assert body["classification_source"] == "rules"
    assert body["priority_reason"] == (
        'High: matched "Customer", "escalation", "blocked" '
        "(a customer issue, an escalation, a blocked colleague)."
    )


def test_classify_one_replaces_an_ai_or_manual_label_when_asked(
    client: TestClient, session: Session
) -> None:
    # An explicit click on one email: the rules decide, whatever was there before
    for source in ("ai", "manual"):
        email = add_email(
            session, "Website outage", priority=Priority.LOW, classification_source=source
        )

        body = client.post(f"/api/emails/{email.id}/classify").json()

        assert (body["priority"], body["classification_source"]) == ("critical", "rules")


def test_classify_one_unknown_email_returns_404(client: TestClient) -> None:
    response = client.post("/api/emails/999/classify")

    assert response.status_code == 404
    assert response.json() == {"detail": "Email not found"}


def test_classify_one_non_numeric_id_returns_422(client: TestClient) -> None:
    assert client.post("/api/emails/abc/classify").status_code == 422


# --- no AI in the inbox ------------------------------------------------------------------


def test_the_inbox_code_never_imports_the_anthropic_sdk() -> None:
    # Guard (#92): the inbox classifies with rules only; Claude lives in generator/
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in APP_DIR.rglob("*.py")
        if "anthropic" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_classify_endpoints_are_documented(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()

    assert "post" in spec["paths"][URL]
    assert "post" in spec["paths"]["/api/emails/{email_id}/classify"]
    assert "ClassifyResult" in spec["components"]["schemas"]
