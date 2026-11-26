"""Tests for the planning time helpers (story 4.1, issue #95).

Every function takes `now` or a date as a parameter, so these tests fix the time
(including daylight-saving change days) instead of depending on the real clock.
Toronto: UTC-5 in winter (EST), UTC-4 in summer (EDT). In 2026 clocks jump forward
on Sunday 2026-03-08 (02:00 -> 03:00) and fall back on Sunday 2026-11-01 (02:00 -> 01:00).
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.config import Settings
from app.services.clock import local_today, utc_now, work_window


def settings(**values: str) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


# --- work_window --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "start_utc", "end_utc"),
    [
        (date(2026, 11, 26), utc(2026, 11, 26, 14), utc(2026, 11, 26, 22)),  # winter, UTC-5
        (date(2026, 7, 15), utc(2026, 7, 15, 13), utc(2026, 7, 15, 21)),  # summer, UTC-4
        (date(2026, 3, 8), utc(2026, 3, 8, 13), utc(2026, 3, 8, 21)),  # spring change day
        (date(2026, 11, 1), utc(2026, 11, 1, 14), utc(2026, 11, 1, 22)),  # autumn change day
    ],
    ids=["winter", "summer", "spring-forward-day", "fall-back-day"],
)
def test_work_window_is_9_to_5_local_time(
    day: date, start_utc: datetime, end_utc: datetime
) -> None:
    start, end = work_window(day, settings())

    assert (start, end) == (start_utc, end_utc)
    # Returned in UTC (safe arithmetic); in Toronto these are 09:00 and 17:00
    assert start.utcoffset() == timedelta(0) and end.utcoffset() == timedelta(0)
    toronto = ZoneInfo("America/Toronto")
    assert (start.astimezone(toronto).hour, end.astimezone(toronto).hour) == (9, 17)


def test_work_window_uses_the_configured_hours_and_zone() -> None:
    start, end = work_window(
        date(2026, 11, 26), settings(APP_TIMEZONE="Europe/Berlin", WORK_HOURS="08:30-12:15")
    )

    assert (start, end) == (utc(2026, 11, 26, 7, 30), utc(2026, 11, 26, 11, 15))  # UTC+1


def test_python_subtracts_same_zone_datetimes_by_wall_clock() -> None:
    # The trap this module avoids: with the SAME tzinfo, Python ignores the DST jump
    toronto = ZoneInfo("America/Toronto")
    one = datetime(2026, 3, 8, 1, 0, tzinfo=toronto)
    four = datetime(2026, 3, 8, 4, 0, tzinfo=toronto)

    assert four - one == timedelta(hours=3)  # wall clock: wrong
    assert four.astimezone(UTC) - one.astimezone(UTC) == timedelta(hours=2)  # real time


def test_window_across_the_spring_gap_is_one_hour_shorter() -> None:
    # 02:00-03:00 doesn't exist on 2026-03-08 in Toronto: 01:00-04:00 lasts 2 hours
    start, end = work_window(date(2026, 3, 8), settings(WORK_HOURS="01:00-04:00"))

    assert end - start == timedelta(hours=2)


def test_window_across_the_autumn_repeat_is_one_hour_longer() -> None:
    # 01:00-02:00 happens twice on 2026-11-01 in Toronto: 00:30-03:00 lasts 3.5 hours
    start, end = work_window(date(2026, 11, 1), settings(WORK_HOURS="00:30-03:00"))

    assert end - start == timedelta(hours=3, minutes=30)


# --- local_today --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "zone", "expected"),
    [
        (utc(2026, 11, 27, 2, 0), "America/Toronto", date(2026, 11, 26)),  # 21:00 the day before
        (utc(2026, 11, 27, 2, 0), "Europe/Berlin", date(2026, 11, 27)),  # 03:00 the same day
        (utc(2026, 11, 26, 4, 59), "America/Toronto", date(2026, 11, 25)),  # 23:59 local
        (utc(2026, 11, 26, 5, 0), "America/Toronto", date(2026, 11, 26)),  # 00:00 local
    ],
)
def test_local_today_is_the_date_in_the_app_time_zone(
    now: datetime, zone: str, expected: date
) -> None:
    assert local_today(settings(APP_TIMEZONE=zone), now) == expected


def test_local_today_rejects_a_naive_now() -> None:
    # A naive datetime has no time zone: it can't name one exact moment
    with pytest.raises(ValueError, match="aware"):
        local_today(settings(), datetime(2026, 11, 26, 12, 0))


# --- utc_now ------------------------------------------------------------------------


def test_utc_now_is_aware_and_current() -> None:
    before = datetime.now(UTC)

    now = utc_now()

    assert now.tzinfo is not None and now.utcoffset() == timedelta(0)
    assert before <= now <= datetime.now(UTC)
