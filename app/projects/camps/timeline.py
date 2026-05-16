"""Schedule grid: camps × weeks (Monday columns) for public timeline view."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, List, Optional, Tuple

from app.projects.camps.models import Camp, CampSession

# Daily schedule length (start→end), not “clock position”.
HALF_DAY_MAX_HOURS = 4.5

_DAY_SHORT = ("M", "T", "W", "Th", "F")


def _fmt_clock_12h(t: Optional[time]) -> Optional[str]:
    if t is None:
        return None
    hour = t.hour
    minute = t.minute
    h12 = hour % 12 or 12
    suffix = "am" if hour < 12 else "pm"
    if minute:
        return f"{h12}:{minute:02d}{suffix}"
    return f"{h12}{suffix}"


def compact_weekdays_from_dates(dates: set[date]) -> str:
    """e.g. M-Th, M, W, F from Mon–Fri dates in that week."""
    idxs = sorted({d.weekday() for d in dates if d.weekday() < 5})
    if not idxs:
        return ""
    groups: List[Tuple[int, int]] = []
    lo = hi = idxs[0]
    for x in idxs[1:]:
        if x == hi + 1:
            hi = x
        else:
            groups.append((lo, hi))
            lo = hi = x
    groups.append((lo, hi))
    parts: List[str] = []
    for a, b in groups:
        if a == b:
            parts.append(_DAY_SHORT[a])
        else:
            parts.append(f"{_DAY_SHORT[a]}-{_DAY_SHORT[b]}")
    return ", ".join(parts)


def session_time_range_label(session: CampSession) -> Optional[str]:
    """Single session daily window, e.g. 8:30am–12pm; None if no times."""
    a = _fmt_clock_12h(session.start_time)
    b = _fmt_clock_12h(session.end_time)
    if a and b:
        return f"{a}–{b}"
    if a:
        return f"{a}–?"
    if b:
        return f"?–{b}"
    return None


def cell_hover_title(camp: Camp, week_monday: date, days: set[date]) -> str:
    """Days + times for tooltip (sessions overlapping this week)."""
    day_part = compact_weekdays_from_dates(days)
    if not day_part:
        return ""

    time_labels: List[str] = []
    seen: set[str] = set()
    for s in camp.sessions:
        ws = weekdays_in_session_for_week(s, week_monday)
        if not ws or not ws.intersection(days):
            continue
        label = session_time_range_label(s)
        if label and label not in seen:
            seen.add(label)
            time_labels.append(label)

    if time_labels:
        times = " · ".join(time_labels)
        return f"{day_part} {times}"
    return f"{day_part} (times not listed)"


def monday_on_or_before(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_mondays_spanning(global_min: date, global_max: date) -> List[date]:
    """Mondays whose Mon–Fri range intersects [global_min, global_max]."""
    if global_min > global_max:
        return []
    first = monday_on_or_before(global_min)
    last = monday_on_or_before(global_max)
    out: List[date] = []
    m = first
    while m <= last:
        week_fri = m + timedelta(days=4)
        if week_fri >= global_min and m <= global_max:
            out.append(m)
        m += timedelta(days=7)
    return out


def session_intersects_week(session: CampSession, week_monday: date) -> bool:
    week_fri = week_monday + timedelta(days=4)
    return max(session.start_date, week_monday) <= min(session.end_date, week_fri)


def weekdays_in_session_for_week(session: CampSession, week_monday: date) -> set:
    if not session_intersects_week(session, week_monday):
        return set()
    week_fri = week_monday + timedelta(days=4)
    i0 = max(session.start_date, week_monday)
    i1 = min(session.end_date, week_fri)
    if i0 > i1:
        return set()
    out = set()
    d = i0
    while d <= i1:
        if d.weekday() < 5:
            out.add(d)
        d += timedelta(days=1)
    return out


def session_daily_duration_hours(session: CampSession) -> Optional[float]:
    """Hours per day from start_time → end_time; None if times incomplete."""
    if session.start_time is None or session.end_time is None:
        return None
    d = date(2000, 1, 1)
    start = datetime.combine(d, session.start_time)
    end = datetime.combine(d, session.end_time)
    if end <= start:
        end += timedelta(days=1)
    return (end - start).total_seconds() / 3600.0


def session_is_half_day(session: CampSession) -> bool:
    """Half-day = scheduled day is 4.5 hours or less (e.g. noon–3pm). Missing times → full day."""
    hours = session_daily_duration_hours(session)
    if hours is None:
        return False
    return hours <= HALF_DAY_MAX_HOURS


def format_week_column_label(week_monday: date) -> str:
    """Monday only, e.g. Jun 16 (cross-platform, no %-d)."""
    return f"{week_monday.strftime('%b')} {week_monday.day}"


@dataclass
class TimelineCell:
    active: bool
    days: int
    half: bool
    hover_title: str


def cell_for_camp_week(camp: Camp, week_monday: date) -> TimelineCell:
    days: set = set()
    any_full_session = False
    for s in camp.sessions:
        ws = weekdays_in_session_for_week(s, week_monday)
        if not ws:
            continue
        days |= ws
        if not session_is_half_day(s):
            any_full_session = True
    if not days:
        return TimelineCell(active=False, days=0, half=False, hover_title="")
    hover = cell_hover_title(camp, week_monday, days)
    return TimelineCell(active=True, days=len(days), half=not any_full_session, hover_title=hover)


def global_session_date_bounds(camps: List[Camp]) -> Tuple[Optional[date], Optional[date]]:
    dates: List[date] = []
    for c in camps:
        for s in c.sessions:
            dates.extend([s.start_date, s.end_date])
    if not dates:
        return None, None
    return min(dates), max(dates)


def build_timeline_grid(
    camps: List[Camp],
) -> Tuple[List[dict], List[dict]]:
    """
    Returns (week_columns, rows).
    week_columns: [{ "monday", "label" }, ...]
    rows: [{ "camp", "cells": [TimelineCell-like dicts] }, ...]
    """
    gmin, gmax = global_session_date_bounds(camps)
    if gmin is None or gmax is None:
        return [], []
    mondays = week_mondays_spanning(gmin, gmax)
    week_columns = [{"monday": m, "label": format_week_column_label(m)} for m in mondays]
    rows: List[dict] = []
    for camp in camps:
        cells: List[dict[str, Any]] = []
        for m in mondays:
            cell = cell_for_camp_week(camp, m)
            cells.append(
                {
                    "active": cell.active,
                    "days": cell.days,
                    "half": cell.half,
                    "hover_title": cell.hover_title,
                }
            )
        rows.append({"camp": camp, "cells": cells})
    return week_columns, rows
