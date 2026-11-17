"""Tests for the database setup and the Email model (story 1.2, issue #28)."""

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect
from sqlalchemy.exc import StatementError
from sqlmodel import Session, create_engine, select

from app.config import Settings, get_settings
from app.main import app
from app.models import Email, EmailStatus, Priority

REPO_ROOT = Path(__file__).resolve().parents[2]


def make_email(**overrides: object) -> Email:
    data: dict[str, object] = {
        "sender_name": "Ada Lovelace",
        "sender_email": "ada@example.com",
        "subject": "Quarterly report",
        "body": "Please review the attached report by Friday.",
        "received_at": datetime(2026, 11, 15, 14, 30, tzinfo=UTC),
    }
    data.update(overrides)
    return Email.model_validate(data)


def save(session: Session, email: Email) -> Email:
    session.add(email)
    session.commit()
    session.refresh(email)
    return email


def test_saved_email_reads_back_with_defaults(session: Session) -> None:
    saved = save(session, make_email())

    loaded = session.get(Email, saved.id)

    assert loaded is not None
    assert loaded.id is not None
    assert loaded.subject == "Quarterly report"
    assert loaded.status == EmailStatus.NEW
    assert loaded.status == "new"  # str enum: compares equal to the plain text
    assert loaded.priority is None
    assert loaded.priority_reason is None
    assert loaded.classification_source is None
    assert loaded.suggested_response_minutes is None


def test_datetimes_read_back_as_utc_aware(session: Session) -> None:
    saved = save(session, make_email())
    session.expire_all()  # force a real reload from SQLite, not the cached object

    loaded = session.exec(select(Email)).one()

    assert loaded.received_at == datetime(2026, 11, 15, 14, 30, tzinfo=UTC)
    assert loaded.received_at.tzinfo == UTC
    assert loaded.created_at.tzinfo == UTC
    assert saved.id == loaded.id


def test_non_utc_datetime_is_stored_as_utc(session: Session) -> None:
    toronto_time = datetime(2026, 11, 15, 9, 30, tzinfo=ZoneInfo("America/Toronto"))
    save(session, make_email(received_at=toronto_time))
    session.expire_all()

    loaded = session.exec(select(Email)).one()

    assert loaded.received_at == datetime(2026, 11, 15, 14, 30, tzinfo=UTC)  # EST = UTC-5
    assert loaded.received_at.tzinfo == UTC


def test_naive_datetime_is_rejected(session: Session) -> None:
    # A time without a timezone is ambiguous; fail loudly instead of guessing
    session.add(make_email(received_at=datetime(2026, 11, 15, 14, 30)))

    with pytest.raises(StatementError, match="timezone"):
        session.commit()


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [("status", "archived"), ("priority", "urgent"), ("classification_source", "guess")],
)
def test_invalid_enum_value_is_rejected(field: str, bad_value: str) -> None:
    with pytest.raises(ValidationError):
        make_email(**{field: bad_value})


def test_valid_enum_values_are_accepted() -> None:
    email = make_email(priority="critical", status="handled", classification_source="ai")

    assert email.priority == Priority.CRITICAL
    assert email.status == EmailStatus.HANDLED


def test_email_survives_a_restart(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"
    first_engine = create_engine(url)
    Email.metadata.create_all(first_engine)
    with Session(first_engine) as session:
        save(session, make_email(subject="Still here?"))
    first_engine.dispose()  # simulate stopping the app

    second_engine = create_engine(url)  # simulate starting it again
    with Session(second_engine) as session:
        subjects = [email.subject for email in session.exec(select(Email))]
    second_engine.dispose()

    assert subjects == ["Still here?"]


def test_app_startup_creates_database_file_and_email_table(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_file = tmp_path / "nested" / "folder" / "app.db"  # parent folders don't exist yet
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")

    with TestClient(app):  # `with` runs the lifespan (startup + shutdown)
        pass

    assert db_file.exists()
    assert "email" in inspect(create_engine(f"sqlite:///{db_file.as_posix()}")).get_table_names()


def test_default_database_is_repo_root_data_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL")

    settings = Settings(_env_file=None)

    assert settings.database_url == f"sqlite:///{(REPO_ROOT / 'data' / 'app.db').as_posix()}"


def test_tests_never_use_the_real_database(tmp_path: Path) -> None:
    assert get_settings().database_url == f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
