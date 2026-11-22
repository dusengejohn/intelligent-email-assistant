"""Tests for the shared priority definitions (brief §7; story 2.1, issue #46)."""

from app.models import Priority
from app.priorities import PRIORITIES, SORT_ORDER, default_minutes


def test_every_priority_is_defined_completely() -> None:
    assert set(PRIORITIES) == set(Priority)
    for info in PRIORITIES.values():
        assert info.label
        assert info.meaning
        assert info.respond_within
        assert info.color.startswith("#")
        assert info.default_minutes > 0


def test_default_minutes_match_the_brief() -> None:
    # Brief Epic 4: critical 15, high 15, moderate 10, low 5
    assert {p: default_minutes(p) for p in Priority} == {
        Priority.CRITICAL: 15,
        Priority.HIGH: 15,
        Priority.MODERATE: 10,
        Priority.LOW: 5,
    }


def test_colors_match_the_brief() -> None:
    assert {p: PRIORITIES[p].color for p in Priority} == {
        Priority.CRITICAL: "#DC2626",
        Priority.HIGH: "#EA580C",
        Priority.MODERATE: "#CA8A04",
        Priority.LOW: "#16A34A",
    }


def test_sort_order_is_most_urgent_first() -> None:
    assert SORT_ORDER == (Priority.CRITICAL, Priority.HIGH, Priority.MODERATE, Priority.LOW)
