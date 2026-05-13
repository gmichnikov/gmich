"""Derive typical Mon–Fri vs Mon–Thu style blocks from session date ranges."""
from __future__ import annotations

from collections import Counter
from typing import Iterable, Optional

__all__ = [
    "inclusive_calendar_days",
    "typical_inclusive_days",
    "typical_week_schedule_label",
]


def inclusive_calendar_days(session) -> int:
    """Inclusive days from session start_date through end_date (minimum 1)."""
    return max(1, (session.end_date - session.start_date).days + 1)


def typical_inclusive_days(sessions: Iterable) -> Optional[int]:
    """
    Most frequent inclusive day-count (mode); ties choose the smaller span (stable).
    None if there are no sessions.
    """
    sess_list = list(sessions)
    if not sess_list:
        return None
    lengths = [inclusive_calendar_days(s) for s in sess_list]
    counts = Counter(lengths)
    top = max(counts.values())
    winners = [d for d, n in counts.items() if n == top]
    return min(winners)


def typical_week_schedule_label(typical: Optional[int]) -> Optional[str]:
    if typical is None:
        return None
    if typical == 5:
        return "5-day weeks"
    if typical == 4:
        return "4-day weeks"
    return f"{typical}-day weeks"
