"""Shared pytest fixtures.

Every test runs isolated from the developer's machine: no real `.env`, no
app-related environment variables, a fresh settings cache, and a database file
inside the test's temporary folder. This guarantees that a real
ANTHROPIC_API_KEY can never be used by a test and that `data/app.db` is never
touched.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import config, db
from app.main import app

# Environment variables read by Settings. VS Code's `python.terminal.useEnvFile`
# can load these into your terminal, so tests must remove them.
APP_ENV_VARS = (
    "APP_ENV",
    "DATABASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "AI_TIMEOUT_SECONDS",
    "INGEST_TOKEN",
)


def _clear_caches() -> None:
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    for name in APP_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # Point get_settings() at a .env file that does not exist
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "no-such.env")
    # Safety net: even if a test starts the app, it uses a throwaway file, never data/app.db
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    _clear_caches()
    yield
    _clear_caches()


@pytest.fixture
def engine() -> Iterator[Engine]:
    """An in-memory SQLite database with all tables, gone after the test.

    `StaticPool` makes every connection reuse the same single connection, so all
    sessions see the same in-memory database.
    """
    test_engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as test_session:
        yield test_session


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    """A test client whose endpoints use the in-memory database (dependency override)."""

    def get_test_session() -> Iterator[Session]:
        yield session

    app.dependency_overrides[db.get_session] = get_test_session
    yield TestClient(app)
    app.dependency_overrides.clear()
