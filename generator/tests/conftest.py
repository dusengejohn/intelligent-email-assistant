"""Shared pytest fixtures.

Every test runs isolated from the developer's machine: no real `.env` and no
app-related environment variables, so a real ANTHROPIC_API_KEY or INGEST_TOKEN
can never be used by a test, and no test talks to a real inbox or to Claude.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app import config

APP_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "AI_TIMEOUT_SECONDS",
    "INBOX_URL",
    "INBOX_TIMEOUT_SECONDS",
    "INGEST_TOKEN",
)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    for name in APP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "no-such.env")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
