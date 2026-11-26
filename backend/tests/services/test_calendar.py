"""Tests for the mock calendar (story 4.2, issue #96).

The mock builds any day from a weekly template in local time (APP_TIMEZONE) and
returns events as UTC instants (the time rule from story 4.1). Toronto is UTC-5 in
winter, UTC-4 in summer; clocks jumped forward on Sunday 2026-03-08.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.services.calendar import (
    MOCK_TEMPLATE,
    CalendarEvent,
    CalendarSource,
    MockCalendar,
    load_template,
)

THURSDAY = date(2026, 11, 26)
SATURDAY = date(2026, 11, 28)


def settings(**values: str) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def week(**days: list[dict[str, str]]) -> dict[str, Any]:
    """A template with every weekday present (empty unless given)."""
    names = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    return {"weekly": {name: days.get(name, []) for name in names}}


def write(tmp_path: Path, content: dict[str, Any]) -> Path:
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def mock(tmp_path: Path, content: dict[str, Any], **values: str) -> MockCalendar:
    return MockCalendar(load_template(write(tmp_path, content)), settings(**values))


# --- the shipped template ---------------------------------------------------------------


def test_the_shipped_template_is_valid() -> None:
    # Fails in CI if someone breaks calendar_mock.json (not in the user's request)
    template = load_template(MOCK_TEMPLATE)

    assert set(template.weekly) == {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }
    assert all(
        template.weekly[day] for day in ("monday", "tuesday", "wednesday", "thursday", "friday")
    )
    assert template.weekly["saturday"] == [] and template.weekly["sunday"] == []


def test_the_shipped_template_has_the_cases_planning_must_handle() -> None:
    # Realistic "mess" for the free-slot algorithm (story 4.3)
    calendar = MockCalendar(load_template(MOCK_TEMPLATE), settings())
    wednesday = calendar.events(date(2026, 11, 25))
    thursday = calendar.events(THURSDAY)
    friday = calendar.events(date(2026, 11, 27))

    assert any(e.start.hour < 14 for e in wednesday)  # before 09:00 Toronto (14:00 UTC)
    assert any(a.end > b.start for a, b in zip(thursday, thursday[1:], strict=False))  # overlap
    assert any(e.end > utc(2026, 11, 27, 22) for e in friday)  # past 17:00 Toronto


# --- invalid templates fail with a clear message ----------------------------------------


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ({"weekly": {"monday": []}}, "tuesday"),  # a missing day
        (week(monday=[{"title": "Stand-up", "start": "9:30", "end": "09:45"}]), "start"),
        # Pydantic alone would accept these: the template allows exactly HH:MM
        (week(monday=[{"title": "Stand-up", "start": "09:30:15", "end": "09:45"}]), "HH:MM|09:30"),
        (week(monday=[{"title": "Stand-up", "start": "09:30Z", "end": "09:45"}]), "24 h time"),
        (week(monday=[{"title": "Stand-up", "start": "10:00", "end": "09:45"}]), "after"),
        (week(monday=[{"title": "", "start": "09:30", "end": "09:45"}]), "title"),
        (
            week(monday=[{"title": "x", "start": "09:30", "end": "09:45", "room": "A"}]),
            "room",
        ),
        ({**week(), "holidays": []}, "holidays"),
    ],
    ids=[
        "missing-day",
        "bad-time",
        "seconds",
        "time-zone-suffix",
        "end-before-start",
        "empty-title",
        "unknown-field",
        "extra-key",
    ],
)
def test_invalid_template_fails_with_a_clear_message(
    tmp_path: Path, content: dict[str, Any], expected: str
) -> None:
    with pytest.raises(ValidationError, match=expected):
        load_template(write(tmp_path, content))


# --- building a day -----------------------------------------------------------------------


def test_a_weekday_gets_its_template_events_in_utc_sorted(tmp_path: Path) -> None:
    calendar = mock(
        tmp_path,
        week(
            thursday=[
                {"title": "Lunch", "start": "12:00", "end": "13:00"},  # unsorted on purpose
                {"title": "Stand-up", "start": "09:30", "end": "09:45"},
            ]
        ),
    )

    events = calendar.events(THURSDAY)

    assert [(e.title, e.start, e.end) for e in events] == [
        ("Stand-up", utc(2026, 11, 26, 14, 30), utc(2026, 11, 26, 14, 45)),
        ("Lunch", utc(2026, 11, 26, 17, 0), utc(2026, 11, 26, 18, 0)),
    ]


def test_the_same_local_time_moves_in_utc_with_the_season(tmp_path: Path) -> None:
    content = week(
        thursday=[{"title": "Stand-up", "start": "09:30", "end": "09:45"}],
        monday=[{"title": "Stand-up", "start": "09:30", "end": "09:45"}],
    )
    calendar = mock(tmp_path, content)

    assert calendar.events(date(2026, 7, 16))[0].start == utc(2026, 7, 16, 13, 30)  # summer
    # Monday after the spring change (Sunday 2026-03-08): already summer time
    assert calendar.events(date(2026, 3, 9))[0].start == utc(2026, 3, 9, 13, 30)
    assert calendar.events(date(2026, 3, 2))[0].start == utc(2026, 3, 2, 14, 30)  # before it


def test_the_configured_time_zone_is_used(tmp_path: Path) -> None:
    calendar = mock(
        tmp_path,
        week(thursday=[{"title": "Stand-up", "start": "09:30", "end": "09:45"}]),
        APP_TIMEZONE="Europe/Berlin",
    )

    assert calendar.events(THURSDAY)[0].start == utc(2026, 11, 26, 8, 30)  # UTC+1


def test_the_weekend_is_free(tmp_path: Path) -> None:
    calendar = MockCalendar(load_template(MOCK_TEMPLATE), settings())

    assert calendar.events(SATURDAY) == []
    assert calendar.events(date(2026, 11, 29)) == []


def test_ids_are_unique_and_stable() -> None:
    calendar = MockCalendar(load_template(MOCK_TEMPLATE), settings())

    first = [e.id for e in calendar.events(THURSDAY)]

    assert len(first) == len(set(first))
    assert first == [e.id for e in calendar.events(THURSDAY)]
    assert all(event_id.startswith("2026-11-26-") for event_id in first)


def test_events_are_returned_as_they_are(tmp_path: Path) -> None:
    # No clipping or merging here: that's the free-slot algorithm's job (story 4.3)
    calendar = mock(
        tmp_path,
        week(
            thursday=[
                {"title": "Workshop", "start": "13:00", "end": "16:00"},
                {"title": "1:1", "start": "15:30", "end": "16:00"},
                {"title": "Early call", "start": "07:00", "end": "07:30"},
            ]
        ),
    )

    titles = [e.title for e in calendar.events(THURSDAY)]

    assert titles == ["Early call", "Workshop", "1:1"]


def test_mock_calendar_is_a_calendar_source() -> None:
    # Structural typing: it fits the Protocol by having events(day), no inheritance
    source: CalendarSource = MockCalendar(load_template(MOCK_TEMPLATE), settings())

    assert isinstance(source, CalendarSource)
    assert all(isinstance(e, CalendarEvent) for e in source.events(THURSDAY))


def test_the_calendar_source_can_only_read() -> None:
    # Advice only (Epic 4): the interface has exactly one method, and it reads
    methods = {name for name in vars(CalendarSource) if not name.startswith("_")}

    assert methods == {"events"}
