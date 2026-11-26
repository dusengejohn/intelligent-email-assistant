"""Tests for the generator's settings (story 3b.2, issue #81)."""

import pytest

from app.config import get_settings


def test_defaults_point_at_a_local_inbox() -> None:
    settings = get_settings()

    assert settings.inbox_url == "http://localhost:8000"
    assert settings.inbox_timeout_seconds == 10
    assert settings.ingest_token is None
    assert settings.anthropic_api_key is None


def test_values_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INBOX_URL", "http://backend:8000")
    monkeypatch.setenv("INGEST_TOKEN", "abc-token")

    settings = get_settings()

    assert settings.inbox_url == "http://backend:8000"
    assert settings.ingest_token is not None
    assert settings.ingest_token.get_secret_value() == "abc-token"
    assert "abc-token" not in repr(settings)


@pytest.mark.parametrize("name", ["ANTHROPIC_API_KEY", "INGEST_TOKEN"])
def test_blank_secrets_mean_not_configured(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, "  ")

    settings = get_settings()

    assert settings.anthropic_api_key is None
    assert settings.ingest_token is None
