"""Tests for POST /api/generate (story 3b.2, issue #81).

Claude is a `FakeAI` and the inbox a `FakeInbox`, installed with FastAPI
dependency overrides: no network, no API key, no cost.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.ai_client import get_ai_client
from app.services.errors import AIConfigError, AIServiceError
from app.services.inbox import InboxClient, get_inbox_client
from tests.fakes import FakeAI, FakeInbox, batch

URL = "/api/generate"


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def use(ai: FakeAI | None = None, inbox: FakeInbox | None = None) -> None:
    """Replace Claude and/or the inbox with fakes (None = keep the real one)."""
    if ai is not None:
        app.dependency_overrides[get_ai_client] = lambda: ai
    if inbox is not None:
        settings = Settings(_env_file=None, ingest_token="t", inbox_url="http://inbox.test")
        fake = InboxClient(settings, transport=inbox.transport)
        app.dependency_overrides[get_inbox_client] = lambda: fake


def test_generate_delivers_to_the_inbox_and_reports_counts(client: TestClient) -> None:
    ai, inbox = FakeAI(batch(10)), FakeInbox()
    use(ai, inbox)

    response = client.post(URL, json={"count": 10})

    assert response.status_code == 201
    assert response.json() == {"generated": 10, "delivered": 10}
    assert len(inbox.requests) == 1
    assert len(inbox.delivered()) == 10


def test_scenario_reaches_the_prompt(client: TestClient) -> None:
    ai = FakeAI(batch(2))
    use(ai, FakeInbox())

    client.post(URL, json={"count": 2, "scenario": "Hospital IT team"})

    assert "Hospital IT team" in ai.calls[0]["prompt"]


def test_invalid_ai_emails_are_not_delivered(client: TestClient) -> None:
    items = batch(3)
    items.emails[1] = items.emails[1].model_copy(update={"sender_email": "real@gmail.com"})
    inbox = FakeInbox()
    use(FakeAI(items), inbox)

    response = client.post(URL, json={"count": 3})

    assert response.json() == {"generated": 2, "delivered": 2}
    assert len(inbox.delivered()) == 2


def test_inbox_failure_is_502_and_says_nothing_was_delivered(client: TestClient) -> None:
    import httpx

    use(FakeAI(batch(10)), FakeInbox(lambda r: httpx.Response(401, json={"detail": "x"})))

    response = client.post(URL, json={"count": 10})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail.startswith("Generated 10 emails but the inbox rejected the token")
    assert "Nothing was delivered" in detail


def test_claude_failure_is_502_and_the_inbox_is_never_called(client: TestClient) -> None:
    inbox = FakeInbox()
    use(FakeAI(AIServiceError("request timed out; try again.")), inbox)

    response = client.post(URL, json={"count": 10})

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service error: request timed out; try again."
    assert inbox.requests == []


def test_rejected_api_key_is_503(client: TestClient) -> None:
    use(FakeAI(AIConfigError("AI is not configured: ANTHROPIC_API_KEY was rejected")), FakeInbox())

    response = client.post(URL, json={"count": 1})

    assert response.status_code == 503


def test_no_api_key_is_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_TOKEN", "t")

    response = client.post(URL, json={"count": 1})

    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_no_ingest_token_is_503_before_any_claude_call(client: TestClient) -> None:
    # Don't pay for emails that can't be delivered
    ai = FakeAI(batch(10))
    use(ai)  # the real inbox dependency: no INGEST_TOKEN configured

    response = client.post(URL, json={"count": 10})

    assert response.status_code == 503
    assert "INGEST_TOKEN" in response.json()["detail"]
    assert ai.calls == []


@pytest.mark.parametrize("body", [{"count": 0}, {"count": 51}, {"count": 5, "scenario": "x" * 201}])
def test_invalid_request_is_422_without_any_call(client: TestClient, body: dict) -> None:
    ai, inbox = FakeAI(), FakeInbox()
    use(ai, inbox)

    response = client.post(URL, json=body)

    assert response.status_code == 422
    assert ai.calls == []
    assert inbox.requests == []
