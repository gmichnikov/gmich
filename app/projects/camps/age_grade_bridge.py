"""
Approximate age ↔ grade bridging for directory filters.

Camp sessions often list ages OR grades, not both. When the user filters by one,
we infer a loose band for the other so grade-only sessions can match age filters
and vice versa.

This is heuristic (cutoff rules vary). Tuned for typical NJ summer-camp listings.
"""
from __future__ import annotations

from typing import Optional, Tuple


def _grade_to_age_band(g: int) -> Tuple[int, int]:
    """Inclusive ages often associated with a single grade level for camp matching."""
    if g <= -1:
        return (3, 5)
    if g == 0:
        return (5, 6)
    return (g + 5, g + 6)


def inferred_age_span_from_grade_range(g_min: int, g_max: int) -> Tuple[int, int]:
    """Hull of age bands across grades g_min..g_max inclusive."""
    ages_lo = min(_grade_to_age_band(g)[0] for g in range(g_min, g_max + 1))
    ages_hi = max(_grade_to_age_band(g)[1] for g in range(g_min, g_max + 1))
    return ages_lo, ages_hi


def _age_to_grade_band(a: int) -> Tuple[int, int]:
    """Inclusive grades that might include a child of age `a` (loose)."""
    if a <= 4:
        return (-1, 0)
    g_lo = max(-1, min(12, a - 6))
    g_hi = max(-1, min(12, a - 4))
    if g_lo > g_hi:
        g_lo, g_hi = g_hi, g_lo
    return (g_lo, g_hi)


def inferred_grade_span_from_age_range(a_min: int, a_max: int) -> Tuple[int, int]:
    """Hull of grade bands across ages a_min..a_max inclusive."""
    glo = 12
    ghi = -1
    for a in range(a_min, a_max + 1):
        lo, hi = _age_to_grade_band(a)
        glo = min(glo, lo)
        ghi = max(ghi, hi)
    return (glo, ghi)


def _intervals_overlap(
    lo1: int, hi1: int, lo2: int, hi2: int
) -> bool:
    return max(lo1, lo2) <= min(hi1, hi2)


def session_matches_age_filter(
    session,
    age_min: Optional[int],
    age_max: Optional[int],
) -> bool:
    """Session matches user age bounds via direct ages and/or inferred from grades."""
    if age_min is None and age_max is None:
        return True
    f_lo = age_min if age_min is not None else 0
    f_hi = age_max if age_max is not None else 100

    if session.age_min is not None and session.age_max is not None:
        if _intervals_overlap(session.age_min, session.age_max, f_lo, f_hi):
            return True

    if session.grade_min is not None and session.grade_max is not None:
        alo, ahi = inferred_age_span_from_grade_range(
            session.grade_min, session.grade_max
        )
        if _intervals_overlap(alo, ahi, f_lo, f_hi):
            return True

    return False


def session_matches_grade_filter(
    session,
    grade_min: Optional[int],
    grade_max: Optional[int],
) -> bool:
    """Session matches user grade bounds via direct grades and/or inferred from ages."""
    if grade_min is None and grade_max is None:
        return True
    f_lo = grade_min if grade_min is not None else -1
    f_hi = grade_max if grade_max is not None else 12

    if session.grade_min is not None and session.grade_max is not None:
        if _intervals_overlap(session.grade_min, session.grade_max, f_lo, f_hi):
            return True

    if session.age_min is not None and session.age_max is not None:
        glo, ghi = inferred_grade_span_from_age_range(
            session.age_min, session.age_max
        )
        if _intervals_overlap(glo, ghi, f_lo, f_hi):
            return True

    return False
