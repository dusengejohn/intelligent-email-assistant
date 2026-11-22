"""Tests for the classify endpoints (story 2.3, issue #48).

`client` and `session` (conftest.py) use the in-memory database; `use_ai`
overrides `get_optional_ai_client` with a fake (or None = no API key).
"""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.models import ClassificationSource, Email, Priority
from app.services.ai_client import get_optional_ai_client
from app.services.errors import AIServiceError
from tests.fakes import EchoClassifierAI

URL = "/api/emails/classify"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
UseAI = Callable[[Any], Any]


@pytest.fixture
def use_ai() -> Iterator[UseAI]:
    """Make the endpoints use `ai` (a fake, or None for "no API key")."""

    def install(ai: Any) -> Any:
        app.dependency_overrides[get_optional_ai_client] = lambda: ai
        return ai

    yield install
    app.dependency_overrides.pop(get_optional_ai_client, None)


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


def test_classify_uses_the_ai_and_saves(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    emails = [add_email(session, f"Email {i}") for i in range(3)]
    use_ai(EchoClassifierAI(priority="high"))

    response = client.post(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["classified"] == 3
    assert body["by_source"] == {"ai": 3, "fallback": 0}
    assert body["remaining"] == 0
    assert {e["priority"] for e in body["emails"]} == {"high"}
    saved = reload(session, emails[0])
    assert saved.priority == Priority.HIGH
    assert saved.priority_reason == "Classified by the fake AI."
    assert saved.suggested_response_minutes == 20
    assert saved.classification_source == ClassificationSource.AI


def test_without_ai_the_rules_classify_and_it_is_still_200(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    add_email(session, "Website outage")
    add_email(session, "Weekly newsletter")
    add_email(session, "Notes from the sync")
    use_ai(None)

    response = client.post(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["by_source"] == {"ai": 0, "fallback": 3}
    priorities = {e["subject"]: e["priority"] for e in body["emails"]}
    assert priorities == {
        "Website outage": "critical",
        "Weekly newsletter": "low",
        "Notes from the sync": "moderate",
    }


def test_real_dependency_without_a_key_falls_back(client: TestClient, session: Session) -> None:
    # No override: get_optional_ai_client runs, and conftest removed the API key
    add_email(session, "Website outage")

    response = client.post(URL)

    assert response.status_code == 200
    assert response.json()["by_source"] == {"ai": 0, "fallback": 1}


def test_at_most_50_per_request_newest_first(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    emails = [add_email(session, f"Email {i}", hours_ago=i) for i in range(60)]  # 0 = newest
    ai = use_ai(EchoClassifierAI())

    first = client.post(URL).json()

    assert first["classified"] == 50
    assert first["remaining"] == 10
    newest_50 = {e.id for e in emails[:50]}
    assert {e["id"] for e in first["emails"]} == newest_50
    assert len(ai.calls) == 3  # batches of 20 + 20 + 10

    second = client.post(URL).json()

    assert second["classified"] == 10
    assert second["remaining"] == 0
    assert {e["id"] for e in second["emails"]} == {e.id for e in emails[50:]}


def test_nothing_to_classify_does_not_call_the_ai(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    add_email(session, "Done", priority=Priority.LOW, classification_source="fallback")
    ai = use_ai(EchoClassifierAI())

    body = client.post(URL).json()

    assert body == {
        "classified": 0,
        "by_source": {"ai": 0, "fallback": 0},
        "remaining": 0,
        "emails": [],
    }
    assert ai.calls == []


def test_already_classified_emails_are_left_alone(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    manual = add_email(
        session,
        "My call",
        priority=Priority.LOW,
        priority_reason="Set manually.",
        classification_source="manual",
        suggested_response_minutes=5,
    )
    new = add_email(session, "New one")
    ai = use_ai(EchoClassifierAI(priority="critical"))

    client.post(URL)

    assert ai.sent_ids() == [new.id]  # the manual email was never sent to the AI
    kept = reload(session, manual)
    assert kept.priority == Priority.LOW
    assert kept.classification_source == ClassificationSource.MANUAL


def test_ai_failure_falls_back_and_still_saves(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    email = add_email(session, "Website outage")
    use_ai(EchoClassifierAI(error=AIServiceError("request timed out; try again.")))

    response = client.post(URL)

    assert response.status_code == 200
    assert response.json()["by_source"] == {"ai": 0, "fallback": 1}
    assert reload(session, email).priority == Priority.CRITICAL


# --- POST /api/emails/{id}/classify --------------------------------------------------


def test_classify_one_email_even_if_set_manually(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    email = add_email(session, "Recheck me", priority=Priority.LOW, classification_source="manual")
    use_ai(EchoClassifierAI(priority="critical"))

    response = client.post(f"/api/emails/{email.id}/classify")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == email.id
    assert body["priority"] == "critical"
    assert body["classification_source"] == "ai"
    assert reload(session, email).priority == Priority.CRITICAL


def test_classify_one_unknown_email_returns_404(client: TestClient, use_ai: UseAI) -> None:
    use_ai(EchoClassifierAI())

    response = client.post("/api/emails/999/classify")

    assert response.status_code == 404
    assert response.json() == {"detail": "Email not found"}


def test_classify_one_non_numeric_id_returns_422(client: TestClient) -> None:
    assert client.post("/api/emails/abc/classify").status_code == 422


# --- documentation -----------------------------------------------------------------------


def test_classify_endpoints_are_documented(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()

    assert "post" in spec["paths"][URL]
    assert "post" in spec["paths"]["/api/emails/{email_id}/classify"]
    assert "ClassifyResult" in spec["components"]["schemas"]
