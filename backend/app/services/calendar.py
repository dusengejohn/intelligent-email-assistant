"""The calendar the planner reads (story 4.2, issue #96). Read-only by design.

- `CalendarEvent`: one busy period, as UTC instants (the time rule, see clock.py).
- `CalendarSource`: what any calendar must offer, exactly one method, `events(day)`.
  It is a Protocol (structural typing): any class with that method fits, so the mock
  can later be swapped for Google Calendar or Microsoft Graph without touching the
  router or the planner. There is deliberately no write method: planning is
  advice only, so it cannot create or change events.
- `MockCalendar`: builds any day from a weekly template in local time
  (`app/data/calendar_mock.json`), so "today" always has a realistic calendar.
"""

import json
import re
from datetime import UTC, date, datetime, time
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Protocol, runtime_checkable

from fastapi import Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import Settings, get_settings

MOCK_TEMPLATE = Path(__file__).resolve().parents[1] / "data" / "calendar_mock.json"
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
HH_MM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class CalendarEvent(BaseModel):
    """One busy period of the day (read-only; times are UTC instants)."""

    id: str
    title: str
    start: AwareDatetime
    end: AwareDatetime


@runtime_checkable
class CalendarSource(Protocol):
    def events(self, day: date) -> list[CalendarEvent]:
        """The events of `day` (a local date in APP_TIMEZONE), sorted by start."""
        ...


# --- the mock: a weekly template, validated like API input ----------------------------


class TemplateEvent(BaseModel):
    """One event of the template, in local time ("09:30")."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    start: time
    end: time

    @field_validator("start", "end", mode="before")
    @classmethod
    def must_be_hh_mm(cls, value: object) -> object:
        if not isinstance(value, str) or not HH_MM.match(value):
            raise ValueError(f"must be a 24 h time like 09:30; got {value!r}")
        return value

    @model_validator(mode="after")
    def end_after_start(self) -> "TemplateEvent":
        if self.end <= self.start:
            raise ValueError(f"end ({self.end:%H:%M}) must be after start ({self.start:%H:%M})")
        return self


class CalendarTemplate(BaseModel):
    """`{"weekly": {"monday": [...], ..., "sunday": [...]}}`: every day present."""

    model_config = ConfigDict(extra="forbid")

    weekly: dict[str, list[TemplateEvent]]

    @field_validator("weekly")
    @classmethod
    def all_seven_days(cls, value: dict[str, list[TemplateEvent]]) -> dict:
        missing = [day for day in WEEKDAYS if day not in value]
        unknown = sorted(set(value) - set(WEEKDAYS))
        if missing or unknown:
            raise ValueError(
                f"needs exactly the days {', '.join(WEEKDAYS)}; "
                f"missing: {', '.join(missing) or '-'}; unknown: {', '.join(unknown) or '-'}"
            )
        return value


def load_template(path: Path) -> CalendarTemplate:
    """Read and validate a template file (raises ValidationError with the reason)."""
    return CalendarTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))


class MockCalendar:
    """A calendar built from a weekly template in APP_TIMEZONE (implements CalendarSource)."""

    def __init__(self, template: CalendarTemplate, settings: Settings) -> None:
        self._template = template
        self._zone = settings.timezone

    def events(self, day: date) -> list[CalendarEvent]:
        entries = self._template.weekly[WEEKDAYS[day.weekday()]]
        # Local time -> that day's UTC instants (zoneinfo applies DST)
        spans = sorted(
            (
                datetime.combine(day, entry.start, tzinfo=self._zone).astimezone(UTC),
                datetime.combine(day, entry.end, tzinfo=self._zone).astimezone(UTC),
                entry.title,
            )
            for entry in entries
        )
        # Stable, readable ids: the date and the position in the day
        return [
            CalendarEvent(id=f"{day.isoformat()}-{n}", title=title, start=start, end=end)
            for n, (start, end, title) in enumerate(spans, start=1)
        ]


@lru_cache
def _shipped_template() -> CalendarTemplate:
    return load_template(MOCK_TEMPLATE)  # read and validated once, then cached


def get_calendar(settings: Annotated[Settings, Depends(get_settings)]) -> CalendarSource:
    """FastAPI dependency: the calendar to read (the mock, for now)."""
    return MockCalendar(_shipped_template(), settings)
