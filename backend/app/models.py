"""Database tables (SQLModel = SQLAlchemy table + Pydantic model in one class)."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Dialect
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


class Priority(StrEnum):
    """Brief §7. Sort order: critical → high → moderate → low."""

    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class ClassificationSource(StrEnum):
    AI = "ai"
    FALLBACK = "fallback"
    MANUAL = "manual"


class EmailStatus(StrEnum):
    NEW = "new"
    HANDLED = "handled"


class UTCDateTime(TypeDecorator[datetime]):
    """A datetime column that is always UTC-aware in Python.

    SQLite has no timezone support: it stores "2026-11-15 14:30:00" and gives it
    back without a timezone ("naive"). This type converts to UTC on the way in
    and re-attaches UTC on the way out, so the API always returns `...+00:00`.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # Fail loudly: we can't know which timezone a naive time was meant in
            raise ValueError("datetime must have a timezone (got a naive datetime)")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


class Email(SQLModel, table=True):
    """One email (brief §6). Classification fields stay empty until Epic 2.

    Note: `Email(...)` does NOT validate (SQLModel skips validation for table
    classes). Use `Email.model_validate({...})` for untrusted data.
    """

    id: int | None = Field(default=None, primary_key=True)
    sender_name: str
    sender_email: str
    subject: str
    body: str
    received_at: datetime = Field(sa_type=UTCDateTime)

    priority: Priority | None = None
    priority_reason: str | None = None
    classification_source: ClassificationSource | None = None
    suggested_response_minutes: int | None = None

    status: EmailStatus = EmailStatus.NEW
    created_at: datetime = Field(default_factory=utc_now, sa_type=UTCDateTime)
    # Soft delete (story 3.3): set when moved to the Trash, None while active.
    # Trashed emails are hidden everywhere except the Trash view.
    deleted_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
