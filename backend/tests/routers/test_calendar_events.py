"""Tests for GET /api/calendar/events (story 4.2, issue #96).

The calendar source and the clock are FastAPI dependencies, so tests swap them:
a fixed "now" for "today", and a fake source to prove the source is replaceable.
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.calendar import CalendarEvent, get_calendar
from app.services.clock import get_now

URL = "/api/calendar/events"


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def fix_now(moment: datetime) -> None:
    app.dependency_overrides[get_now] = lambda: moment


def test_events_of_a_given_day_in_utc_sorted(client: TestClient) -> None:
    response = client.get(URL, params={"date": "2026-11-26"})  # a Thursday

    assert response.status_code == 200
    events = response.json()
    assert events, "Thursday has events in the mock template"
    starts = [e["start"] for e in events]
    assert starts == sorted(starts)
    assert all(e["start"].endswith("Z") and e["end"].endswith("Z") for e in events)
    assert set(events[0]) == {"id", "title", "start", "end"}
    assert {"title": "Stand-up", "start": "2026-11-26T14:30:00Z"}.items() <= next(
        e for e in events if e["title"] == "Stand-up"
    ).items()


def test_a_weekend_day_has_no_events(client: TestClient) -> None:
    assert client.get(URL, params={"date": "2026-11-28"}).json() == []


def test_without_a_date_it_is_today_in_the_app_time_zone(client: TestClient) -> None:
    # 02:00 UTC on Friday the 27th is still Thursday the 26th, 21:00, in Toronto
    fix_now(datetime(2026, 11, 27, 2, 0, tzinfo=UTC))

    today = client.get(URL).json()

    assert today == client.get(URL, params={"date": "2026-11-26"}).json()
    assert all(e["id"].startswith("2026-11-26-") for e in today)


@pytest.mark.parametrize("bad", ["2026-13-01", "tomorrow", "26.11.2026", ""])
def test_an_invalid_date_is_422(client: TestClient, bad: str) -> None:
    assert client.get(URL, params={"date": bad}).status_code == 422


def test_the_calendar_is_read_only(client: TestClient) -> None:
    assert client.post(URL, json={}).status_code == 405
    paths = client.get("/openapi.json").json()["paths"]
    calendar_methods = {
        method for path, ops in paths.items() if path.startswith("/api/calendar") for method in ops
    }
    assert calendar_methods == {"get"}


def test_the_source_is_swappable(client: TestClient) -> None:
    # A stand-in for a future Google/Outlook source: anything with events(day)
    class FakeSource:
        def events(self, day: date) -> list[CalendarEvent]:
            start = datetime(2026, 11, 26, 15, 0, tzinfo=UTC)
            return [
                CalendarEvent(
                    id="fake-1", title=f"Fake on {day}", start=start, end=start.replace(hour=16)
                )
            ]

    app.dependency_overrides[get_calendar] = FakeSource

    events = client.get(URL, params={"date": "2026-11-26"}).json()

    assert events == [
        {
            "id": "fake-1",
            "title": "Fake on 2026-11-26",
            "start": "2026-11-26T15:00:00Z",
            "end": "2026-11-26T16:00:00Z",
        }
    ]
