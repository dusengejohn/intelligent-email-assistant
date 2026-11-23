"""Tests for the Alembic migrations (story 3.2, issue #63).

Every test gets its own temporary database file (DATABASE_URL from conftest.py),
so real migrations run here, never against data/app.db.
"""

from datetime import UTC, datetime
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel

from app.db import BASELINE_REVISION, alembic_config, get_engine, migrate_database
from app.main import app
from app.models import Email, Priority

VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def head_revision() -> str:
    head = ScriptDirectory.from_config(alembic_config("sqlite://")).get_current_head()
    assert head is not None
    return head


def current_revision() -> str | None:
    with get_engine().connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def table_names() -> set[str]:
    return set(inspect(get_engine()).get_table_names())


def all_rows() -> list[tuple[object, ...]]:
    with get_engine().connect() as connection:
        return list(connection.execute(text("SELECT * FROM email ORDER BY id")))


# --- fresh and existing databases ----------------------------------------------------


def test_fresh_database_is_created_by_the_migrations() -> None:
    migrate_database()

    assert {"email", "alembic_version"} <= table_names()
    assert current_revision() == head_revision()


def test_existing_database_is_stamped_and_keeps_its_data() -> None:
    # Like data/app.db today: tables made by create_all(), no migration history
    SQLModel.metadata.create_all(get_engine())
    with Session(get_engine()) as session:
        for i in range(3):
            session.add(
                Email(
                    sender_name=f"Sender {i}",
                    sender_email=f"s{i}@example.com",
                    subject=f"Subject {i}",
                    body="Body",
                    received_at=datetime(2026, 11, 23, 9, i, tzinfo=UTC),
                    priority=Priority.HIGH if i else None,
                )
            )
        session.commit()
    before = all_rows()
    assert "alembic_version" not in table_names()

    migrate_database()

    assert all_rows() == before  # every row and field unchanged
    assert current_revision() == head_revision()


def test_migrating_twice_changes_nothing() -> None:
    migrate_database()
    with Session(get_engine()) as session:
        session.add(
            Email(
                sender_name="Ada",
                sender_email="ada@example.com",
                subject="Keep me",
                body="Body",
                received_at=datetime(2026, 11, 23, 9, 0, tzinfo=UTC),
            )
        )
        session.commit()
    before = all_rows()

    migrate_database()

    assert all_rows() == before
    assert current_revision() == head_revision()


def test_app_startup_runs_the_migrations() -> None:
    with TestClient(app):  # `with` runs the lifespan (startup)
        pass

    assert current_revision() == head_revision()


# --- the migrations themselves ----------------------------------------------------------


def test_migrations_match_the_models() -> None:
    # Schema drift check: a model change without a migration fails here (and in CI)
    migrate_database()

    with get_engine().connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, SQLModel.metadata)

    assert differences == []


def test_baseline_is_the_first_revision() -> None:
    script = ScriptDirectory.from_config(alembic_config("sqlite://"))
    base = script.get_base()

    assert base == BASELINE_REVISION


def test_migration_files_do_not_import_app_code() -> None:
    # Old migrations must keep working when app code changes later
    for path in VERSIONS.glob("*.py"):
        source = path.read_text()
        assert "from app" not in source and "import app" not in source, path.name
