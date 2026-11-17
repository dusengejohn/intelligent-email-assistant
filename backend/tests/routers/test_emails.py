"""Tests for POST /api/emails/generate (story 1.5, issue #31).

`client` and `session` (conftest.py) use an in-memory database through a
dependency override; `use_ai` overrides `get_ai_client` with a FakeAI.
"""

from collections.abc import Callable, Iterator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.main import app
from app.models import Email
from app.services.ai_client import get_ai_client
from app.services.errors import AIConfigError, AIServiceError
from tests.fakes import FakeAI, batch, raw

URL = "/api/emails/generate"
UseAI = Callable[..., FakeAI]


@pytest.fixture
def use_ai() -> Iterator[UseAI]:
    """Make the endpoint use a FakeAI that returns/raises the given results."""

    def install(*results: object) -> FakeAI:
        fake = FakeAI(*results)  # type: ignore[arg-type]
        app.dependency_overrides[get_ai_client] = lambda: fake
        return fake

    yield install
    app.dependency_overrides.pop(get_ai_client, None)


def row_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(Email)).one()


def test_generate_returns_201_with_saved_emails(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    use_ai(batch(10))

    response = client.post(URL, json={"count": 10})

    assert response.status_code == 201
    emails = response.json()
    assert len(emails) == 10
    first = emails[0]
    assert isinstance(first["id"], int)
    assert first["sender_name"] == "Sender 0"
    assert first["sender_email"] == "sender0@example.com"
    assert first["subject"] == "Subject 0"
    assert first["body"].startswith("Body of email 0")
    # UTC-aware in JSON: Pydantic writes UTC as "...Z" (same as "+00:00")
    for field in ("received_at", "created_at"):
        assert first[field].endswith("Z")
        assert datetime.fromisoformat(first[field]).utcoffset() == timedelta(0)
    assert first["status"] == "new"
    assert first["priority"] is None
    assert row_count(session) == 10


def test_count_defaults_to_ten_and_scenario_reaches_the_prompt(
    client: TestClient, use_ai: UseAI
) -> None:
    fake = use_ai(batch(10))

    response = client.post(URL, json={"scenario": "IT infrastructure team"})

    assert response.status_code == 201
    assert len(response.json()) == 10
    assert "IT infrastructure team" in fake.calls[0]["prompt"]


def test_missing_api_key_returns_503(client: TestClient, session: Session) -> None:
    # No get_ai_client override: the real dependency runs, and conftest removed the key
    response = client.post(URL, json={"count": 3})

    assert response.status_code == 503
    assert response.json() == {"detail": "AI is not configured: set ANTHROPIC_API_KEY in .env"}
    assert row_count(session) == 0


def test_rejected_api_key_returns_503(client: TestClient, session: Session, use_ai: UseAI) -> None:
    use_ai(AIConfigError("AI is not configured: ANTHROPIC_API_KEY was rejected"))

    response = client.post(URL, json={"count": 3})

    assert response.status_code == 503
    assert response.json()["detail"] == "AI is not configured: ANTHROPIC_API_KEY was rejected"
    assert row_count(session) == 0


def test_ai_failure_returns_502_and_saves_nothing(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    # The first batch succeeds, the second fails: still nothing may be saved
    use_ai(batch(10), AIServiceError("request timed out; try again."))

    response = client.post(URL, json={"count": 20})

    assert response.status_code == 502
    assert response.json() == {"detail": "AI service error: request timed out; try again."}
    assert row_count(session) == 0


def test_only_invalid_emails_returns_502(
    client: TestClient, session: Session, use_ai: UseAI
) -> None:
    use_ai(batch(0).model_copy(update={"emails": [raw(1, sender_email="x@gmail.com")]}))

    response = client.post(URL, json={"count": 1})

    assert response.status_code == 502
    assert response.json()["detail"].startswith("AI service error: ")
    assert row_count(session) == 0


@pytest.mark.parametrize(
    "body",
    [{"count": 0}, {"count": 51}, {"count": "abc"}, {"count": 5, "scenario": "x" * 201}],
    ids=["count-0", "count-51", "count-text", "scenario-201"],
)
def test_invalid_input_returns_422_without_calling_ai(
    client: TestClient, session: Session, use_ai: UseAI, body: dict[str, object]
) -> None:
    fake = use_ai()

    response = client.post(URL, json=body)

    assert response.status_code == 422
    assert fake.calls == []
    assert row_count(session) == 0


def test_endpoint_and_schemas_are_documented(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()

    assert "post" in spec["paths"][URL]
    assert {"GenerateRequest", "EmailRead"} <= set(spec["components"]["schemas"])
