"""Tests for the free-slot algorithm (story 4.3, issue #97).

`free_slots` and `planning_window` are pure functions (no database, no clock), so
they are tested three ways:
1. an edge-case table with known events (the epic's "unit tested with known events");
2. the real mock calendar, to see the pieces fit together;
3. property-based tests (hypothesis): rules that must hold for ANY calendar, checked
   on hundreds of generated ones, and compared with a simple brute-force version.
"""

from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from app.config import Settings
from app.services.calendar import MOCK_TEMPLATE, MockCalendar, load_template
from app.services.planner import Slot, free_slots, planning_window

DAY = date(2026, 11, 26)  # a Thursday
TORONTO = ZoneInfo("America/Toronto")


class Busy(NamedTuple):
    """Anything with start/end works as an event (CalendarEvent does too)."""

    start: datetime
    end: datetime


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    """A UTC moment on DAY (free_slots itself doesn't care about time zones)."""
    return datetime(2026, 11, 26, hour, minute, second, tzinfo=UTC)


def busy(h1: int, m1: int, h2: int, m2: int) -> Busy:
    return Busy(at(h1, m1), at(h2, m2))


def spans(slots: list[Slot]) -> list[tuple[str, str]]:
    return [(f"{s.start:%H:%M}", f"{s.end:%H:%M}") for s in slots]


def settings(**values: str) -> Settings:
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


# --- 1. the edge-case table -------------------------------------------------------------

START, END = at(9), at(17)


@pytest.mark.parametrize(
    ("events", "expected"),
    [
        ([], [("09:00", "17:00")]),
        ([busy(9, 0, 17, 0)], []),  # fully booked
        ([busy(8, 0, 18, 0)], []),  # booked beyond both edges
        ([busy(10, 0, 11, 0)], [("09:00", "10:00"), ("11:00", "17:00")]),
        # overlapping (the Thursday workshop + 1:1) and nested events merge
        ([busy(13, 0, 16, 0), busy(15, 30, 16, 0)], [("09:00", "13:00"), ("16:00", "17:00")]),
        ([busy(10, 0, 12, 0), busy(10, 30, 11, 0)], [("09:00", "10:00"), ("12:00", "17:00")]),
        # touching events: one busy block, no 0-minute slot between them
        ([busy(12, 0, 13, 0), busy(13, 0, 16, 0)], [("09:00", "12:00"), ("16:00", "17:00")]),
        # outside or across the window: ignored or clipped
        ([busy(7, 0, 8, 0), busy(18, 0, 19, 0)], [("09:00", "17:00")]),
        ([busy(8, 0, 9, 30), busy(16, 30, 18, 0)], [("09:30", "16:30")]),
        # the 15-minute threshold: 14 min dropped, exactly 15 kept
        ([busy(9, 0, 10, 0), busy(10, 14, 17, 0)], []),
        ([busy(9, 0, 10, 0), busy(10, 15, 17, 0)], [("10:00", "10:15")]),
        # zero-length and reversed events are ignored
        ([busy(10, 0, 10, 0), busy(12, 0, 11, 0)], [("09:00", "17:00")]),
    ],
    ids=[
        "no-events",
        "fully-booked",
        "booked-beyond-edges",
        "one-meeting",
        "overlapping",
        "nested",
        "touching",
        "outside-window",
        "across-edges",
        "gap-14-min",
        "gap-15-min",
        "zero-and-reversed",
    ],
)
def test_free_slots(events: list[Busy], expected: list[tuple[str, str]]) -> None:
    assert spans(free_slots(START, END, events)) == expected


def test_unsorted_input_gives_the_same_result() -> None:
    events = [busy(15, 0, 16, 0), busy(9, 30, 9, 45), busy(12, 0, 13, 0)]

    assert free_slots(START, END, events) == free_slots(START, END, sorted(events))


def test_minimum_length_can_be_changed() -> None:
    events = [busy(9, 20, 12, 0), busy(12, 30, 17, 0)]  # gaps of 20 and 30 minutes

    assert spans(free_slots(START, END, events, min_minutes=30)) == [("12:00", "12:30")]


@pytest.mark.parametrize("minimum", [0, -15])
def test_minimum_must_be_at_least_one_minute(minimum: int) -> None:
    # A 0-minute "slot" between two touching meetings would be nonsense
    with pytest.raises(ValueError, match="at least 1"):
        free_slots(START, END, [busy(12, 0, 13, 0), busy(13, 0, 14, 0)], min_minutes=minimum)


def test_slot_knows_its_length() -> None:
    assert Slot(at(9), at(10, 30)).minutes == 90


def test_naive_datetimes_are_rejected() -> None:
    naive = datetime(2026, 11, 26, 9, 0)

    with pytest.raises(ValueError, match="aware"):
        free_slots(naive, END, [])
    with pytest.raises(ValueError, match="aware"):
        free_slots(START, END, [Busy(naive, at(10))])


def test_other_time_zones_are_compared_as_instants() -> None:
    # 10:00-11:00 in Toronto (UTC-5) is 15:00-16:00 UTC
    toronto = Busy(
        datetime(2026, 11, 26, 10, tzinfo=TORONTO), datetime(2026, 11, 26, 11, tzinfo=TORONTO)
    )

    slots = free_slots(at(14), at(17), [toronto])

    assert spans(slots) == [("14:00", "15:00"), ("16:00", "17:00")]
    assert all(s.start.utcoffset() == timedelta(0) for s in slots)  # returned in UTC


# --- planning_window: the working day, from "now" if it is today -------------------------


@pytest.mark.parametrize(
    ("day", "now", "expected"),
    [
        # another (future) date: the whole working day, 09:00-17:00 Toronto = 14:00-22:00 UTC
        (
            date(2026, 11, 27),
            at(15),
            (datetime(2026, 11, 27, 14, tzinfo=UTC), datetime(2026, 11, 27, 22, tzinfo=UTC)),
        ),
        (DAY, at(13), (at(14), at(22))),  # today, 08:00 local: before work starts
        (DAY, at(15, 7, 30), (at(15, 10), at(22))),  # 10:07:30 local -> rounded up to 10:10
        (DAY, at(15, 5), (at(15, 5), at(22))),  # exactly 10:05: stays
        (DAY, at(14, 35), (at(14, 35), at(22))),  # inside the stand-up: free_slots removes it
        (DAY, at(21, 58), None),  # 16:58 rounds up to 17:00: nothing left
        (DAY, at(22), None),  # 17:00: the working day is over
        (DAY, at(23, 30), None),  # evening
        (date(2026, 11, 25), at(15), None),  # a past date
    ],
    ids=[
        "future-date",
        "before-work",
        "rounded-up",
        "on-the-5",
        "inside-a-meeting",
        "rounds-to-end",
        "at-end",
        "evening",
        "past-date",
    ],
)
def test_planning_window(
    day: date, now: datetime, expected: tuple[datetime, datetime] | None
) -> None:
    assert planning_window(day, settings(), now) == expected


def test_planning_window_on_a_dst_day() -> None:
    # Monday after the spring change: 09:00-17:00 Toronto is now UTC-4
    window = planning_window(date(2026, 3, 9), settings(), datetime(2026, 3, 1, tzinfo=UTC))

    assert window == (datetime(2026, 3, 9, 13, tzinfo=UTC), datetime(2026, 3, 9, 21, tzinfo=UTC))


def test_planning_window_rejects_a_naive_now() -> None:
    with pytest.raises(ValueError, match="aware"):
        planning_window(DAY, settings(), datetime(2026, 11, 26, 10, 0))


# --- 2. the real mock calendar (story 4.2) ------------------------------------------------


def local(slots: list[Slot]) -> list[tuple[str, str]]:
    return [
        (f"{s.start.astimezone(TORONTO):%H:%M}", f"{s.end.astimezone(TORONTO):%H:%M}")
        for s in slots
    ]


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        # Monday: a gap of exactly 15 minutes (09:45-10:00) is kept
        (
            date(2026, 11, 23),
            [
                ("09:00", "09:30"),
                ("09:45", "10:00"),
                ("11:00", "12:00"),
                ("13:00", "14:00"),
                ("15:00", "17:00"),
            ],
        ),
        # Wednesday: the 08:00 early call is outside the window
        (
            date(2026, 11, 25),
            [("09:00", "09:30"), ("09:45", "12:00"), ("13:00", "13:30"), ("15:00", "17:00")],
        ),
        # Thursday: lunch touches the workshop, the 1:1 overlaps it
        (date(2026, 11, 26), [("09:00", "09:30"), ("09:45", "12:00"), ("16:00", "17:00")]),
        # Friday: the team social runs past 17:00 and is cut at the window's end
        (
            date(2026, 11, 27),
            [("09:00", "09:30"), ("09:45", "12:00"), ("13:00", "15:00"), ("16:00", "16:30")],
        ),
        (date(2026, 11, 28), [("09:00", "17:00")]),  # Saturday: no events
    ],
    ids=["monday", "wednesday", "thursday", "friday", "saturday"],
)
def test_free_time_in_the_mock_week(day: date, expected: list[tuple[str, str]]) -> None:
    s = settings()
    calendar = MockCalendar(load_template(MOCK_TEMPLATE), s)
    window = planning_window(day, s, datetime(2026, 11, 22, tzinfo=UTC))  # planned in advance
    assert window is not None

    assert local(free_slots(*window, calendar.events(day))) == expected


# --- 3. properties: rules that hold for ANY calendar ------------------------------------

BASE = datetime(2026, 11, 26, tzinfo=UTC)
minutes = st.integers(min_value=-120, max_value=24 * 60 + 120)
events_strategy = st.lists(st.tuples(minutes, minutes), max_size=12)


def brute_force(
    start: int, end: int, events: list[tuple[int, int]], minimum: int
) -> list[tuple[int, int]]:
    """The obvious, slow way: mark every busy minute, then collect free runs."""
    free = [True] * (end - start)
    for a, b in events:
        for m in range(max(a, start), min(b, end)):
            free[m - start] = False
    runs, run_start = [], None
    for i, is_free in enumerate([*free, False]):
        if is_free and run_start is None:
            run_start = i
        elif not is_free and run_start is not None:
            if i - run_start >= minimum:
                runs.append((start + run_start, start + i))
            run_start = None
    return runs


@hypothesis_settings(max_examples=300, deadline=None)
@given(
    window=st.tuples(st.integers(0, 12 * 60), st.integers(1, 12 * 60)),
    events=events_strategy,
    minimum=st.sampled_from([1, 5, 15, 30]),
)
def test_free_slots_follow_the_rules_for_any_calendar(
    window: tuple[int, int], events: list[tuple[int, int]], minimum: int
) -> None:
    start_m, length = window
    start, end = BASE + timedelta(minutes=start_m), BASE + timedelta(minutes=start_m + length)
    busy_list = [Busy(BASE + timedelta(minutes=a), BASE + timedelta(minutes=b)) for a, b in events]

    slots = free_slots(start, end, busy_list, min_minutes=minimum)

    for slot in slots:
        assert start <= slot.start < slot.end <= end  # inside the window
        assert slot.minutes >= minimum  # long enough
        for event in busy_list:
            if event.end > event.start:  # a real event never overlaps a slot
                assert slot.end <= event.start or event.end <= slot.start
    for earlier, later in zip(slots, slots[1:], strict=False):
        assert earlier.end < later.start  # sorted, separate (a busy block lies between)

    # Nothing lost or invented: identical to the slow minute-by-minute version
    expected = brute_force(start_m, start_m + length, events, minimum)
    got = [
        (int((s.start - BASE).total_seconds() // 60), int((s.end - BASE).total_seconds() // 60))
        for s in slots
    ]
    assert got == expected
