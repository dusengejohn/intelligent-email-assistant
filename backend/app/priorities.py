"""Brief §7 as code: the single source of truth for what each priority means.

Used by the rule-based fallback (services/fallback.py), the AI prompt (story 2.2)
and mirrored by the frontend for colors (story 2.5). Change the definitions here,
not in several places.
"""

from dataclasses import dataclass

from app.models import Priority


@dataclass(frozen=True)
class PriorityInfo:
    label: str
    meaning: str  # typical signals, in plain words (also shown to the AI)
    respond_within: str
    default_minutes: int  # suggested effort to reply (brief Epic 4 defaults)
    color: str  # UI color (brief §7)


PRIORITIES: dict[Priority, PriorityInfo] = {
    Priority.CRITICAL: PriorityInfo(
        label="Critical",
        meaning="Outage, security incident, legal/compliance, executive escalation, deadline today",
        respond_within="about 2 hours",
        default_minutes=15,
        color="#DC2626",
    ),
    Priority.HIGH: PriorityInfo(
        label="High",
        meaning="Customer issue, manager request, deadline within 48 hours, blocked colleague",
        respond_within="the same day",
        default_minutes=15,
        color="#EA580C",
    ),
    Priority.MODERATE: PriorityInfo(
        label="Moderate",
        meaning="Normal work requests, meeting coordination, reviews",
        respond_within="2-3 days",
        default_minutes=10,
        color="#CA8A04",
    ),
    Priority.LOW: PriorityInfo(
        label="Low",
        meaning="FYI, newsletters, automated notifications, social",
        respond_within="whenever convenient",
        default_minutes=5,
        color="#16A34A",
    ),
}

# Sort order everywhere (brief §7): most urgent first
SORT_ORDER: tuple[Priority, ...] = (
    Priority.CRITICAL,
    Priority.HIGH,
    Priority.MODERATE,
    Priority.LOW,
)


def default_minutes(priority: Priority) -> int:
    return PRIORITIES[priority].default_minutes
