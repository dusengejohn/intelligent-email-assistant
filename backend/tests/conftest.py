"""Shared pytest fixtures.

Every test runs isolated from the developer's machine: no real `.env`, no
app-related environment variables, and a fresh settings cache. This guarantees
that a real ANTHROPIC_API_KEY on your machine can never be used by a test.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app import config

# Environment variables read by Settings. VS Code's `python.terminal.useEnvFile`
# can load these into your terminal, so tests must remove them.
APP_ENV_VARS = (
    "APP_ENV",
    "DATABASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "AI_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    for name in APP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # Point get_settings() at a .env file that does not exist
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "no-such.env")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()
