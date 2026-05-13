"""Parse camp session time strings and support directory time filters."""
from __future__ import annotations

from datetime import datetime, time
from typing import Optional, Union

# Thresholds: minutes from midnight (filter URL param value -> minutes)
START_BEFORE_OPTIONS = {
    "8": 8 * 60,
    "830": 8 * 60 + 30,
    "9": 9 * 60,
}

END_AFTER_OPTIONS = {
    "2": 14 * 60,
    "230": 14 * 60 + 30,
    "3": 15 * 60,
    "330": 15 * 60 + 30,
    "4": 16 * 60,
    "430": 16 * 60 + 30,
    "5": 17 * 60,
}


def parse_time_string(time_str: Optional[str]) -> Optional[time]:
    """
    Parse admin/UI time strings into a time object.
    Matches how times are saved (e.g. 9:00am, 3:30pm) plus 24h %H:%M.
    """
    if not time_str:
        return None
    try:
        s = time_str.strip().upper()
        for fmt in ("%I:%M%p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(s, fmt).time()
            except ValueError:
                continue
    except Exception:
        pass
    return None


def parse_time_from_import(value) -> Optional[time]:
    """
    JSON import: ISO HH:MM / HH:MM:SS (preferred), or legacy am/pm strings.
    """
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return parse_time_string(s)


def parse_camp_time_to_minutes(value: Union[str, time, None]) -> Optional[int]:
    """Comparable minutes from midnight; accepts DB Time or string."""
    if value is None:
        return None
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    if isinstance(value, str):
        t = parse_time_string(value)
        if t is None:
            return None
        return t.hour * 60 + t.minute
    return None


def session_matches_time_filters(
    session,
    start_before_mins: Optional[int],
    end_after_mins: Optional[int],
) -> bool:
    """
    When both bounds are set, the same session must satisfy both.
    Missing start_time or end_time fails the corresponding check.
    """
    if start_before_mins is not None:
        sm = parse_camp_time_to_minutes(session.start_time)
        if sm is None or sm > start_before_mins:
            return False
    if end_after_mins is not None:
        em = parse_camp_time_to_minutes(session.end_time)
        if em is None or em < end_after_mins:
            return False
    return True
