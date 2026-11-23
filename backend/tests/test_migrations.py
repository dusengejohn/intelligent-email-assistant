"""Tests for the Alembic migrations (story 3.2, issue #63).

Every test gets its own temporary database file (DATABASE_URL from conftest.py),
so real migrations run here, never against data/app.db.
"""

from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel

from app.db import BASELINE_REVISION, alembic_config, get_engine, migrate_database
from app.main import app
from app.models import Email

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
    # Like data/app.db before story 3.2: the 0001 schema, rows, NO migration history.
    # Built from the baseline migration (not create_all with today's models, which
    # already contain later columns such as deleted_at).
    command.upgrade(alembic_config(str(get_engine().url)), BASELINE_REVISION)
    with get_engine().begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
        for i in range(3):
            connection.execute(
                text(
                    "INSERT INTO email (sender_name, sender_email, subject, body, received_at,"
                    " priority, status, created_at) VALUES (:name, :addr, :subject, 'Body',"
                    " '2026-11-23 09:00:00', :priority, 'NEW', '2026-11-23 09:00:00')"
                ),
                {
                    "name": f"Sender {i}",
                    "addr": f"s{i}@example.com",
                    "subject": f"Subject {i}",
                    "priority": "HIGH" if i else None,
                },
            )
    before = all_rows()
    assert "alembic_version" not in table_names()

    migrate_database()

    after = all_rows()
    assert [row[: len(before[0])] for row in after] == before  # old values unchanged
    assert {row[-1] for row in after} == {None}  # later columns (deleted_at) empty
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


def test_0002_adds_deleted_at_and_can_be_undone() -> None:
    # A database at the baseline, with rows, like data/app.db before story 3.3
    config = alembic_config(str(get_engine().url))
    command.upgrade(config, BASELINE_REVISION)
    with get_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO email (sender_name, sender_email, subject, body, received_at,"
                " status, created_at) VALUES ('Ada', 'ada@example.com', 'Old', 'Body',"
                " '2026-11-23 09:00:00', 'NEW', '2026-11-23 09:00:00')"
            )
        )
    before = all_rows()

    command.upgrade(config, "0002")
    columns = {c["name"] for c in inspect(get_engine()).get_columns("email")}
    assert "deleted_at" in columns
    after = all_rows()
    assert [row[:-1] for row in after] == before  # old values unchanged
    assert [row[-1] for row in after] == [None]  # new column empty

    command.downgrade(config, BASELINE_REVISION)
    columns = {c["name"] for c in inspect(get_engine()).get_columns("email")}
    assert "deleted_at" not in columns
    assert all_rows() == before  # undo keeps the data too
