"""GET /api/calendar/events: the calendar of one day (story 4.2). Read-only."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.services.calendar import CalendarEvent, CalendarSource, get_calendar
from app.services.clock import get_now, local_today

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get(
    "/events",
    response_model=list[CalendarEvent],
    summary="Events of one day (mock calendar), UTC times, sorted by start",
)
def calendar_events(
    calendar: Annotated[CalendarSource, Depends(get_calendar)],
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime, Depends(get_now)],
    day: Annotated[
        date | None,
        Query(alias="date", description="YYYY-MM-DD; default: today in APP_TIMEZONE"),
    ] = None,
) -> list[CalendarEvent]:
    return calendar.events(day or local_today(settings, now))
