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
from app.models import Priority
from app.services.calendar import MOCK_TEMPLATE, MockCalendar, load_template
from app.services.planner import (
    Block,
    PlannableEmail,
    Slot,
    allocate,
    free_slots,
    planning_window,
    reply_minutes,
)

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


# === allocate: placing the emails into the free slots (story 4.4, issue #98) ===========

C, H, M, L = Priority.CRITICAL, Priority.HIGH, Priority.MODERATE, Priority.LOW
OLD = datetime(2026, 11, 20, tzinfo=UTC)


def mail(email_id: int, priority: Priority, minutes: int, age_hours: int = 0) -> PlannableEmail:
    """An email that arrived `age_hours` after OLD (bigger = newer)."""
    return PlannableEmail(
        id=email_id,
        subject=f"Email {email_id}",
        priority=priority,
        minutes=minutes,
        received_at=OLD + timedelta(hours=age_hours),
    )


def slot(h1: int, m1: int, h2: int, m2: int) -> Slot:
    return Slot(at(h1, m1), at(h2, m2))


def plan(blocks: list[Block]) -> list[tuple[str, str, str, list[int]]]:
    return [
        (f"{b.start:%H:%M}", f"{b.end:%H:%M}", b.priority.value, [e.id for e in b.emails])
        for b in blocks
    ]


def test_critical_gets_the_earliest_slot_then_high_then_moderate() -> None:
    blocks, not_today = allocate(
        [slot(9, 0, 12, 0)],
        [mail(3, M, 10), mail(2, H, 30), mail(1, C, 15)],  # given in the wrong order
    )

    assert plan(blocks) == [
        ("09:00", "09:15", "critical", [1]),
        ("09:15", "09:45", "high", [2]),
        ("09:45", "09:55", "moderate", [3]),
    ]
    assert not_today == []


def test_oldest_first_within_a_priority() -> None:
    blocks, _ = allocate([slot(9, 0, 12, 0)], [mail(1, H, 10, age_hours=5), mail(2, H, 10)])

    assert [b.emails[0].id for b in blocks] == [2, 1]  # 2 arrived earlier


def test_first_pick_lets_a_lower_priority_use_a_gap_too_small_for_a_higher_one() -> None:
    # Decision A (#98): the 45-min critical can't use 09:00-09:30, so it gets the
    # earliest slot it fits into; the 10-min moderate then uses the early gap
    blocks, _ = allocate([slot(9, 0, 9, 30), slot(9, 45, 12, 0)], [mail(1, C, 45), mail(2, M, 10)])

    assert plan(blocks) == [
        ("09:00", "09:10", "moderate", [2]),
        ("09:45", "10:30", "critical", [1]),
    ]


def test_low_emails_are_batched_at_the_end_of_the_last_slot() -> None:
    blocks, not_today = allocate(
        [slot(9, 0, 12, 0), slot(16, 0, 17, 0)],
        [mail(1, L, 5), mail(2, H, 30), mail(3, L, 10, age_hours=1)],
    )

    assert plan(blocks) == [
        ("09:00", "09:30", "high", [2]),
        ("16:45", "17:00", "low", [1, 3]),  # one block, oldest first, ends with the day
    ]
    assert not_today == []


def test_a_low_batch_takes_what_fits_and_the_rest_waits() -> None:
    lows = [mail(i, L, 10, age_hours=i) for i in range(1, 5)]  # 4 x 10 min

    blocks, not_today = allocate([slot(16, 30, 17, 0)], lows)  # 30 minutes left

    assert plan(blocks) == [("16:30", "17:00", "low", [1, 2, 3])]
    assert [e.id for e in not_today] == [4]


def test_an_email_that_fits_nowhere_waits_but_smaller_ones_are_still_placed() -> None:
    blocks, not_today = allocate(
        [slot(9, 0, 9, 30), slot(10, 0, 10, 45)],
        [mail(1, C, 60), mail(2, C, 20), mail(3, H, 40)],
    )

    assert plan(blocks) == [
        ("09:00", "09:20", "critical", [2]),
        ("10:00", "10:40", "high", [3]),
    ]
    assert [e.id for e in not_today] == [1]  # never squeezed in or split


def test_no_free_time_means_nothing_today() -> None:
    emails = [mail(1, C, 15), mail(2, L, 5)]

    blocks, not_today = allocate([], emails)

    assert blocks == []
    assert [e.id for e in not_today] == [1, 2]


def test_not_today_is_in_priority_order() -> None:
    _, not_today = allocate([], [mail(1, L, 5), mail(2, M, 10), mail(3, C, 15), mail(4, H, 15)])

    assert [e.priority for e in not_today] == [C, H, M, L]


@pytest.mark.parametrize(
    ("suggested", "priority", "expected"),
    [(25, C, 25), (None, C, 15), (None, H, 15), (None, M, 10), (None, L, 5)],
)
def test_reply_minutes_fall_back_to_the_priority_default(
    suggested: int | None, priority: Priority, expected: int
) -> None:
    assert reply_minutes(suggested, priority) == expected


# --- properties of allocate -----------------------------------------------------------

priorities = st.sampled_from([C, H, M, L])


@hypothesis_settings(max_examples=300, deadline=None)
@given(
    # pause >= 1: like free_slots' output, slots never touch (a busy block lies between)
    gaps=st.lists(st.tuples(st.integers(1, 60), st.integers(15, 120)), max_size=5),
    specs=st.lists(st.tuples(priorities, st.integers(1, 60), st.integers(0, 100)), max_size=15),
)
def test_allocate_follows_the_rules_for_any_day(
    gaps: list[tuple[int, int]], specs: list[tuple[Priority, int, int]]
) -> None:
    # Build separate slots: each starts `pause` minutes after the previous one ends
    slots, cursor = [], at(9)
    for pause, length in gaps:
        start = cursor + timedelta(minutes=pause)
        slots.append(Slot(start, start + timedelta(minutes=length)))
        cursor = start + timedelta(minutes=length)
    emails = [mail(i, p, m, age) for i, (p, m, age) in enumerate(specs)]

    blocks, not_today = allocate(slots, emails)

    planned = [e.id for b in blocks for e in b.emails]
    assert sorted(planned + [e.id for e in not_today]) == sorted(e.id for e in emails)  # once
    for block in blocks:
        assert any(s.start <= block.start and block.end <= s.end for s in slots)  # in a slot
        assert block.end - block.start == timedelta(minutes=sum(e.minutes for e in block.emails))
        assert {e.priority for e in block.emails} == {block.priority}
        assert len(block.emails) == 1 or block.priority == L  # only low is batched
    assert [b.start for b in blocks] == sorted(b.start for b in blocks)  # time order
    for earlier, later in zip(blocks, blocks[1:], strict=False):
        assert earlier.end <= later.start  # no overlap
    assert sum(b.priority == L for b in blocks) <= 1  # one low batch at most

    # First pick: an urgent email left for another day really fitted nowhere, because
    # free gaps only shrink after it was turned away
    used = [Busy(b.start, b.end) for b in blocks]
    leftover = free_slots(at(0), cursor, [*used, *_gaps_between(slots, cursor)], min_minutes=1)
    for email in not_today:
        if email.priority != L:
            assert all(gap.minutes < email.minutes for gap in leftover)


def _gaps_between(slots: list[Slot], end: datetime) -> list[Busy]:
    """Everything outside the slots, as busy time (so free_slots returns what is left)."""
    edges = [at(0), *[t for s in slots for t in (s.start, s.end)], end]
    return [Busy(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]
