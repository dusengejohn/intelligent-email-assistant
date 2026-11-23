"""Tests for the inbox order, view filters and summary counts (story 3.1, issue #62).

One fixed set of emails covers every priority, unclassified emails and handled
ones, so the expected order can be written out in full.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Email, EmailStatus, Priority

URL = "/api/emails"
NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)
C, H, M, L = Priority.CRITICAL, Priority.HIGH, Priority.MODERATE, Priority.LOW
NEW, HANDLED = EmailStatus.NEW, EmailStatus.HANDLED

# (subject, priority, status, hours ago) - no two emails share a received time
EMAILS: list[tuple[str, Priority | None, EmailStatus, float]] = [
    ("u-new-2h", None, NEW, 2),
    ("u-new-5h", None, NEW, 5),
    ("crit-1h", C, NEW, 1),
    ("crit-9h", C, NEW, 9),
    ("high-3h", H, NEW, 3),
    ("mod-4h", M, NEW, 4),
    ("low-0.5h", L, NEW, 0.5),
    ("h-unclass-1.5h", None, HANDLED, 1.5),
    ("h-crit-6h", C, HANDLED, 6),
    ("h-high-8h", H, HANDLED, 8),
    ("h-low-2.5h", L, HANDLED, 2.5),
]


@pytest.fixture
def inbox(session: Session) -> None:
    for subject, priority, status, hours in EMAILS:
        session.add(
            Email.model_validate(
                {
                    "sender_name": "Ada",
                    "sender_email": "ada@example.com",
                    "subject": subject,
                    "body": "Body",
                    "received_at": NOW - timedelta(hours=hours),
                    "priority": priority,
                    "classification_source": "ai" if priority else None,
                    "status": status,
                }
            )
        )
    session.commit()


def subjects(client: TestClient, **params: Any) -> list[str]:
    response = client.get(URL, params=params)
    assert response.status_code == 200
    return [email["subject"] for email in response.json()]


# --- sort order --------------------------------------------------------------------


def test_default_order_is_by_priority(client: TestClient, inbox: None) -> None:
    assert subjects(client) == [
        # new: unclassified first, then critical -> low, newest first within each
        "u-new-2h",
        "u-new-5h",
        "crit-1h",
        "crit-9h",
        "high-3h",
        "mod-4h",
        "low-0.5h",
        # handled: at the bottom, same order
        "h-unclass-1.5h",
        "h-crit-6h",
        "h-high-8h",
        "h-low-2.5h",
    ]


def test_sort_newest_ignores_priority(client: TestClient, inbox: None) -> None:
    assert subjects(client, sort="newest") == [
        "low-0.5h",
        "crit-1h",
        "h-unclass-1.5h",
        "u-new-2h",
        "h-low-2.5h",
        "high-3h",
        "mod-4h",
        "u-new-5h",
        "h-crit-6h",
        "h-high-8h",
        "crit-9h",
    ]


def test_ties_are_broken_by_id(client: TestClient, session: Session) -> None:
    for subject in ("first", "second"):
        session.add(
            Email.model_validate(
                {
                    "sender_name": "Ada",
                    "sender_email": "ada@example.com",
                    "subject": subject,
                    "body": "Body",
                    "received_at": NOW,
                    "priority": H,
                }
            )
        )
    session.commit()

    assert subjects(client) == ["second", "first"]  # same priority and time: higher id first


def test_unknown_sort_returns_422(client: TestClient) -> None:
    assert client.get(URL, params={"sort": "oldest"}).status_code == 422


# --- view filters -----------------------------------------------------------------


def test_classified_filter(client: TestClient, inbox: None) -> None:
    assert subjects(client, classified="false") == ["u-new-2h", "u-new-5h", "h-unclass-1.5h"]
    assert "u-new-2h" not in subjects(client, classified="true")
    assert len(subjects(client, classified="true")) == 8


def test_filters_combine(client: TestClient, inbox: None) -> None:
    assert subjects(client, classified="true", priority="high", status="new") == ["high-3h"]
    assert subjects(client, priority="critical") == ["crit-1h", "crit-9h", "h-crit-6h"]


# --- summary ----------------------------------------------------------------------


def test_summary_counts(client: TestClient, inbox: None) -> None:
    response = client.get(f"{URL}/summary")

    assert response.status_code == 200  # not mistaken for an email id
    assert response.json() == {
        "all": 11,
        "unclassified": 3,
        "classified": 8,
        "critical": 3,
        "high": 2,
        "moderate": 1,
        "low": 2,
        "handled": 4,
    }


@pytest.mark.parametrize(
    ("count", "params"),
    [
        ("all", {}),
        ("unclassified", {"classified": "false"}),
        ("classified", {"classified": "true"}),
        ("critical", {"priority": "critical"}),
        ("high", {"priority": "high"}),
        ("moderate", {"priority": "moderate"}),
        ("low", {"priority": "low"}),
        ("handled", {"status": "handled"}),
    ],
)
def test_each_count_matches_its_list(
    client: TestClient, inbox: None, count: str, params: dict[str, str]
) -> None:
    summary = client.get(f"{URL}/summary").json()

    assert summary[count] == len(subjects(client, **params))


def test_summary_of_empty_database(client: TestClient) -> None:
    assert set(client.get(f"{URL}/summary").json().values()) == {0}


# --- documentation ----------------------------------------------------------------


def test_sort_and_summary_are_documented(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()

    assert "get" in spec["paths"][f"{URL}/summary"]
    assert "EmailSummary" in spec["components"]["schemas"]
    assert set(spec["components"]["schemas"]["SortOrder"]["enum"]) == {"priority", "newest"}
