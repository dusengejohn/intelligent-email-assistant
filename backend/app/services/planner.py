"""Response planning, step 1: free time between meetings (story 4.3, issue #97).

Pure functions: no database, no clock, no I/O. Everything they need comes in as
arguments ("now" too), so they can be tested with any calendar, any day, any time.
All arithmetic is done on UTC instants (the time rule, see clock.py).

    planning_window(day, settings, now) -> the working day still ahead, or None
    free_slots(start, end, events)      -> the gaps of at least 15 minutes
    allocate(slots, emails)             -> reply blocks + what doesn't fit today (#98)
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from app.config import Settings
from app.models import Priority
from app.priorities import PRIORITIES, default_minutes
from app.services.clock import local_today, work_window

MIN_SLOT_MINUTES = 15  # shorter gaps are too small to answer an email in
ROUND_TO = timedelta(minutes=5)  # suggestions start on a 5-minute mark


class Span(Protocol):
    """Anything with a start and an end (CalendarEvent, Slot, ...)."""

    @property
    def start(self) -> datetime: ...

    @property
    def end(self) -> datetime: ...


@dataclass(frozen=True)
class Slot:
    """A free period, as UTC instants."""

    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


def _require_aware(*moments: datetime) -> None:
    for moment in moments:
        if moment.tzinfo is None:
            raise ValueError("datetimes must be timezone-aware (a naive one is not a moment)")


def _round_up(moment: datetime, step: timedelta = ROUND_TO) -> datetime:
    """10:07:30 -> 10:10:00; 10:05:00 stays 10:05:00."""
    hour = moment.replace(minute=0, second=0, microsecond=0)
    past = (moment - hour) % step
    return moment if not past else moment + (step - past)


def planning_window(
    day: date, settings: Settings, now: datetime
) -> tuple[datetime, datetime] | None:
    """The part of `day`'s working hours that can still be planned (UTC instants).

    A future day: the whole working day. Today: from now on, rounded up to the next
    5 minutes (past time can't be used). A past day, or after work today: None.
    """
    today = local_today(settings, now)  # also rejects a naive `now`
    if day < today:
        return None
    start, end = work_window(day, settings)
    if day == today:
        start = max(start, _round_up(now.astimezone(UTC)))
    return (start, end) if start < end else None


def free_slots(
    start: datetime,
    end: datetime,
    events: Iterable[Span],
    min_minutes: int = MIN_SLOT_MINUTES,
) -> list[Slot]:
    """The free periods of at least `min_minutes` between `start` and `end`.

    Interval merging, in three steps:
    1. clip every event to the window (drop those outside it, and empty/reversed ones);
    2. sort by start and merge overlapping or touching events into busy blocks
       (touching ones would leave a 0-minute gap, which min_minutes >= 1 drops anyway);
    3. the gaps between the blocks (and the window's edges) are the free slots.
    """
    _require_aware(start, end)
    if min_minutes < 1:
        raise ValueError("min_minutes must be at least 1 (a 0-minute slot is no slot)")
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    minimum = timedelta(minutes=min_minutes)

    # 1. clip (comparisons between aware datetimes use the real instants)
    clipped: list[tuple[datetime, datetime]] = []
    for event in events:
        _require_aware(event.start, event.end)
        busy_start = max(event.start.astimezone(UTC), start)
        busy_end = min(event.end.astimezone(UTC), end)
        if busy_end > busy_start:
            clipped.append((busy_start, busy_end))

    # 2. merge: extend the last block while the next event starts before (or as) it ends
    blocks: list[list[datetime]] = []
    for busy_start, busy_end in sorted(clipped):
        if blocks and busy_start <= blocks[-1][1]:
            blocks[-1][1] = max(blocks[-1][1], busy_end)
        else:
            blocks.append([busy_start, busy_end])

    # 3. the gaps
    slots: list[Slot] = []
    cursor = start
    for busy_start, busy_end in blocks:
        if busy_start - cursor >= minimum:
            slots.append(Slot(cursor, busy_start))
        cursor = busy_end
    if end - cursor >= minimum:
        slots.append(Slot(cursor, end))
    return slots


# --- step 2: placing the emails (story 4.4, issue #98) -------------------------------

# Brief §7 order: critical first (index 0) ... low last
RANK = {priority: rank for rank, priority in enumerate(PRIORITIES)}


@dataclass(frozen=True)
class PlannableEmail:
    """What the planner needs to know about one open, classified email."""

    id: int
    subject: str
    priority: Priority
    minutes: int  # time to reply
    received_at: datetime


@dataclass(frozen=True)
class Block:
    """Suggested time to answer one email (or the batch of low emails)."""

    start: datetime
    end: datetime
    priority: Priority
    emails: tuple[PlannableEmail, ...]


def reply_minutes(suggested: int | None, priority: Priority) -> int:
    """The email's own estimate, else the priority's default (15/15/10/5)."""
    return suggested if suggested is not None else default_minutes(priority)


def _urgency(email: PlannableEmail) -> tuple[int, datetime, int]:
    # Priority first, then oldest first (it has waited longest), then id (stable)
    return RANK[email.priority], email.received_at, email.id


def allocate(
    slots: list[Slot], emails: list[PlannableEmail]
) -> tuple[list[Block], list[PlannableEmail]]:
    """Suggest when to answer which email. Returns (blocks in time order, not_today).

    Greedy "first pick" (decision A, #98): in priority order, each critical, high and
    moderate email gets the EARLIEST free space where it fits whole; a gap too small
    for a big urgent email can still serve a smaller, less urgent one. Low emails are
    batched into ONE block at the end of the latest slot with room (small things
    last); oldest first, as many as fit. Nothing is split or squeezed in: what fits
    nowhere goes to not_today. Advice only: nothing is written anywhere.
    """
    free = [[s.start, s.end] for s in sorted(slots, key=lambda s: s.start)]
    blocks: list[Block] = []
    not_today: list[PlannableEmail] = []
    ordered = sorted(emails, key=_urgency)

    # 1. critical, high, moderate: one block each, first fit from the start of a gap
    for email in (e for e in ordered if e.priority != Priority.LOW):
        need = timedelta(minutes=email.minutes)
        gap = next((g for g in free if g[1] - g[0] >= need), None)
        if gap is None:
            not_today.append(email)
            continue
        blocks.append(Block(gap[0], gap[0] + need, email.priority, (email,)))
        gap[0] += need  # the rest of the gap stays free

    # 2. low: one batch, at the end of the latest gap that has room for the oldest one
    lows = [e for e in ordered if e.priority == Priority.LOW]
    if lows:
        first = timedelta(minutes=lows[0].minutes)
        gap = next((g for g in reversed(free) if g[1] - g[0] >= first), None)
        batch: list[PlannableEmail] = []
        if gap is not None:
            room, used = gap[1] - gap[0], timedelta()
            for email in lows:  # oldest first, stop at the first that doesn't fit
                if used + timedelta(minutes=email.minutes) > room:
                    break
                batch.append(email)
                used += timedelta(minutes=email.minutes)
            blocks.append(Block(gap[1] - used, gap[1], Priority.LOW, tuple(batch)))
            gap[1] -= used
        not_today.extend(lows[len(batch) :])

    blocks.sort(key=lambda b: b.start)
    not_today.sort(key=_urgency)
    return blocks, not_today
