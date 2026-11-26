"""GET /api/planning/suggestions: when to answer which email (story 4.4, issue #98).

Advice only. This router only READS (emails from SQLite, events from the calendar)
and hands the data to the pure functions in services/planner.py; it never writes,
and the calendar interface has no write method.
"""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Email, EmailStatus
from app.routers.emails import _active
from app.schemas import PlanBlock, PlanEmail, PlanningResult, PlanSlot, PlanWindow
from app.services.calendar import CalendarSource, get_calendar
from app.services.clock import get_now, local_today
from app.services.planner import (
    PlannableEmail,
    allocate,
    free_slots,
    planning_window,
    reply_minutes,
)

router = APIRouter(prefix="/planning", tags=["planning"])


def _open(classified: bool) -> tuple[ColumnElement[bool], ...]:
    """Active (not trashed), not handled, with or without a priority."""
    priority = col(Email.priority).is_not(None) if classified else col(Email.priority).is_(None)
    return _active(), Email.status == EmailStatus.NEW, priority


def _plan_email(email: PlannableEmail) -> PlanEmail:
    return PlanEmail(
        id=email.id, subject=email.subject, priority=email.priority, minutes=email.minutes
    )


@router.get(
    "/suggestions",
    response_model=PlanningResult,
    summary="Suggested times to answer the open emails (advice only)",
    responses={422: {"description": "Invalid or past date"}},
)
def planning_suggestions(
    session: Annotated[Session, Depends(get_session)],
    calendar: Annotated[CalendarSource, Depends(get_calendar)],
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime, Depends(get_now)],
    day: Annotated[
        date | None,
        Query(alias="date", description="YYYY-MM-DD; default: today in APP_TIMEZONE"),
    ] = None,
) -> PlanningResult:
    today = local_today(settings, now)
    day = day or today
    if day < today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Can't plan the past: {day} is before today ({today})",
        )

    # 1. Read: the day's meetings, the time still ahead, the free gaps
    events = calendar.events(day)
    window = planning_window(day, settings, now)
    slots = free_slots(*window, events) if window else []

    # 2. Read: the open, classified emails (and how many still need classifying)
    emails = [
        PlannableEmail(
            id=e.id,  # type: ignore[arg-type]
            subject=e.subject,
            priority=e.priority,  # type: ignore[arg-type]
            minutes=reply_minutes(e.suggested_response_minutes, e.priority),  # type: ignore[arg-type]
            received_at=e.received_at,
        )
        for e in session.exec(select(Email).where(*_open(classified=True)))
    ]
    unclassified = session.exec(
        select(func.count()).select_from(Email).where(*_open(classified=False))
    ).one()

    # 3. Decide (pure): who gets which time; nothing is written anywhere
    blocks, not_today = allocate(slots, emails)

    return PlanningResult(
        date=day,
        window=PlanWindow(start=window[0], end=window[1]) if window else None,
        events=events,
        free_slots=[PlanSlot(start=s.start, end=s.end, minutes=s.minutes) for s in slots],
        suggestions=[
            PlanBlock(
                start=b.start,
                end=b.end,
                priority=b.priority,
                emails=[_plan_email(e) for e in b.emails],
            )
            for b in blocks
        ],
        not_today=[_plan_email(e) for e in not_today],
        unclassified=unclassified,
    )
