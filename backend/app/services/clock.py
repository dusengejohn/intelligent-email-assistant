"""Time helpers for planning (story 4.1, issue #95).

Rules that keep time zones and daylight saving time (DST) correct:

1. The database and all planning arithmetic use **UTC** (one unambiguous timeline).
   Python subtracts two datetimes that share a time zone by *wall clock*, ignoring
   DST jumps (01:00 -> 04:00 on the spring change day would be "3 hours" instead of
   2), so durations are only computed between UTC values.
2. Local time (`APP_TIMEZONE`) is used only to answer local questions ("which day is
   today here?", "when does my working day start?") and for display.
3. Nothing here reads the clock except `utc_now()`; every other function takes `now`
   or a date, so tests can fix the time (23:59, DST days, ...).
"""

from datetime import UTC, date, datetime

from app.config import Settings


def utc_now() -> datetime:
    """The current moment, aware, in UTC. The only place that reads the real clock."""
    return datetime.now(UTC)


def local_today(settings: Settings, now: datetime) -> date:
    """Today's date in APP_TIMEZONE (near midnight it differs from the UTC date)."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware (a naive datetime is not one moment)")
    return now.astimezone(settings.timezone).date()


def work_window(day: date, settings: Settings) -> tuple[datetime, datetime]:
    """The working hours of `day` in APP_TIMEZONE, returned as UTC instants.

    Built in local time (09:00 means 09:00 in Toronto, whatever the season), then
    converted to UTC; zoneinfo applies that day's offset, including DST days.
    """
    zone = settings.timezone
    start = datetime.combine(day, settings.work_start, tzinfo=zone)
    end = datetime.combine(day, settings.work_end, tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)
