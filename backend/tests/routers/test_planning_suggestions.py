"""Tests for GET /api/planning/suggestions (story 4.4, issue #98).

The in-memory database (conftest `client`/`session`), a fixed "now" and a calendar
that records every call. The scenario is Thursday 2026-11-26 in Toronto (UTC-5),
planned at 08:00 local time, with the shipped mock calendar:
free 09:00-09:30, 09:45-12:00 and 16:00-17:00 (local) = 14:00-14:30, 14:45-17:00
and 21:00-22:00 UTC.
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import Email, EmailStatus, Priority
from app.services.calendar import MOCK_TEMPLATE, CalendarEvent, MockCalendar, load_template
from app.services.clock import get_now

URL = "/api/planning/suggestions"
THURSDAY = "2026-11-26"
EIGHT_AM_TORONTO = datetime(2026, 11, 26, 13, 0, tzinfo=UTC)


class RecordingCalendar:
    """The real mock calendar, recording every call made to it."""

    def __init__(self) -> None:
        from app.config import Settings

        self._inner = MockCalendar(load_template(MOCK_TEMPLATE), Settings(_env_file=None))
        self.calls: list[tuple[str, date]] = []

    def events(self, day: date) -> list[CalendarEvent]:
        self.calls.append(("events", day))
        return self._inner.events(day)


@pytest.fixture
def calendar(client: TestClient) -> Iterator[RecordingCalendar]:
    from app.services.calendar import get_calendar

    recording = RecordingCalendar()
    app.dependency_overrides[get_calendar] = lambda: recording
    app.dependency_overrides[get_now] = lambda: EIGHT_AM_TORONTO
    yield recording
    app.dependency_overrides.pop(get_calendar, None)
    app.dependency_overrides.pop(get_now, None)


def add(
    session: Session,
    subject: str,
    priority: Priority | None,
    minutes: int | None,
    received: datetime,
    **fields: Any,
) -> Email:
    email = Email(
        sender_name="Ada",
        sender_email="ada@example.com",
        subject=subject,
        body="Body",
        received_at=received,
        priority=priority,
        suggested_response_minutes=minutes,
        classification_source="rules" if priority else None,
        **fields,
    )
    session.add(email)
    session.commit()
    session.refresh(email)
    return email


def scenario(session: Session) -> dict[str, Email]:
    yesterday = datetime(2026, 11, 25, 15, tzinfo=UTC)
    today = datetime(2026, 11, 26, 13, tzinfo=UTC)
    emails = {
        "C1": add(session, "Database down (old)", Priority.CRITICAL, 45, yesterday),
        "C2": add(session, "Breach suspected (new)", Priority.CRITICAL, 20, today),
        "H1": add(session, "Customer blocked", Priority.HIGH, 30, yesterday),
        "M1": add(session, "Review my PR", Priority.MODERATE, 10, yesterday),
        "M2": add(session, "Long design doc", Priority.MODERATE, 90, yesterday),
        "L1": add(session, "Newsletter", Priority.LOW, 5, yesterday),
        "L2": add(session, "FYI", Priority.LOW, None, today),  # default: 5 min
        # Not planned:
        "handled": add(
            session, "Done", Priority.CRITICAL, 15, yesterday, status=EmailStatus.HANDLED
        ),
        "trashed": add(session, "Gone", Priority.HIGH, 15, yesterday, deleted_at=today),
        "U1": add(session, "Unclassified 1", None, None, today),
        "U2": add(session, "Unclassified 2", None, None, today),
    }
    return emails


def compact(body: dict[str, Any]) -> list[tuple[str, str, str, list[str]]]:
    return [
        (b["start"][11:16], b["end"][11:16], b["priority"], [e["subject"] for e in b["emails"]])
        for b in body["suggestions"]
    ]


def test_the_thursday_plan(
    client: TestClient, session: Session, calendar: RecordingCalendar
) -> None:
    scenario(session)

    response = client.get(URL, params={"date": THURSDAY})

    assert response.status_code == 200
    body = response.json()
    assert body["date"] == THURSDAY
    assert body["window"] == {"start": "2026-11-26T14:00:00Z", "end": "2026-11-26T22:00:00Z"}
    assert [(s["start"][11:16], s["end"][11:16], s["minutes"]) for s in body["free_slots"]] == [
        ("14:00", "14:30", 30),
        ("14:45", "17:00", 135),
        ("21:00", "22:00", 60),
    ]
    assert len(body["events"]) == 4  # the day's meetings, for the Plan view
    # UTC times; in Toronto: 09:00, 09:20, 09:45, 10:30, 16:50
    assert compact(body) == [
        ("14:00", "14:20", "critical", ["Breach suspected (new)"]),  # C1 (45) doesn't fit 30
        ("14:20", "14:30", "moderate", ["Review my PR"]),  # first pick: the gap left over
        ("14:45", "15:30", "critical", ["Database down (old)"]),
        ("15:30", "16:00", "high", ["Customer blocked"]),
        ("21:50", "22:00", "low", ["Newsletter", "FYI"]),  # one batch, ends with the day
    ]
    assert body["suggestions"][-1]["emails"][1]["minutes"] == 5  # the low default
    assert [(e["subject"], e["minutes"]) for e in body["not_today"]] == [("Long design doc", 90)]
    assert body["unclassified"] == 2


def test_handled_trashed_and_unclassified_emails_are_not_planned(
    client: TestClient, session: Session, calendar: RecordingCalendar
) -> None:
    emails = scenario(session)

    body = client.get(URL, params={"date": THURSDAY}).json()

    planned = {e["id"] for b in body["suggestions"] for e in b["emails"]}
    planned |= {e["id"] for e in body["not_today"]}
    for name in ("handled", "trashed", "U1", "U2"):
        assert emails[name].id not in planned, name


def test_advice_only_nothing_is_written(
    client: TestClient, session: Session, calendar: RecordingCalendar
) -> None:
    scenario(session)
    before = [e.model_dump() for e in session.exec(select(Email).order_by(Email.id))]

    client.get(URL, params={"date": THURSDAY})

    session.expire_all()
    after = [e.model_dump() for e in session.exec(select(Email).order_by(Email.id))]
    assert after == before  # no email changed
    assert calendar.calls == [("events", date(2026, 11, 26))]  # the calendar was only read
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths[URL]) == {"get"}
    assert client.post(URL).status_code == 405


def test_today_is_the_default_date(
    client: TestClient, session: Session, calendar: RecordingCalendar
) -> None:
    assert client.get(URL).json()["date"] == THURSDAY  # 08:00 in Toronto


def test_today_after_work_plans_nothing(
    client: TestClient, session: Session, calendar: RecordingCalendar
) -> None:
    scenario(session)
    app.dependency_overrides[get_now] = lambda: EIGHT_AM_TORONTO + timedelta(hours=10)  # 18:00

    body = client.get(URL, params={"date": THURSDAY}).json()

    assert body["window"] is None
    assert body["free_slots"] == [] and body["suggestions"] == []
    assert len(body["not_today"]) == 7  # every plannable email waits


def test_a_past_date_is_422(client: TestClient, calendar: RecordingCalendar) -> None:
    response = client.get(URL, params={"date": "2026-11-25"})

    assert response.status_code == 422
    assert "past" in response.json()["detail"]
    assert calendar.calls == []


def test_a_future_day_uses_the_whole_working_day(
    client: TestClient, session: Session, calendar: RecordingCalendar
) -> None:
    body = client.get(URL, params={"date": "2026-11-27"}).json()  # Friday

    assert body["window"] == {"start": "2026-11-27T14:00:00Z", "end": "2026-11-27T22:00:00Z"}
    assert body["suggestions"] == [] and body["unclassified"] == 0  # no emails yet


def test_an_invalid_date_is_422(client: TestClient, calendar: RecordingCalendar) -> None:
    assert client.get(URL, params={"date": "2026-02-30"}).status_code == 422
