"""Format UTC datetimes for display in the viewer's profile timezone (User.time_zone)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask_login import current_user


def zone_for_user(user):
    """Resolve IANA zone from a User (or None), or UTC."""
    tz_name = "UTC"
    if user is not None:
        tz_name = getattr(user, "time_zone", None) or "UTC"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def utc_naive_to_user_local(dt, user=None):
    """
    Treat naive DB datetime as UTC and convert to the given user's timezone.
    If user is None, uses current_user when authenticated; otherwise UTC.
    """
    if dt is None:
        return None
    if not isinstance(dt, datetime):
        raise TypeError("expected datetime")
    u = user
    if u is None and getattr(current_user, "is_authenticated", False):
        u = current_user
    tz = zone_for_user(u)
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)


def format_user_local_datetime(dt, user=None, fmt="%b %-d, %Y %-I:%M %p %Z"):
    if dt is None:
        return ""
    local = utc_naive_to_user_local(dt, user)
    return local.strftime(fmt)


def format_user_local_date(value, user=None, fmt="%b %-d, %Y"):
    """
    For a datetime: convert to user's zone, then format (local calendar date).
    For a date: format in place (no timezone shift — plain calendar date).
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        local = utc_naive_to_user_local(value, user)
        return local.strftime(fmt)
    if isinstance(value, date):
        return value.strftime(fmt)
    return ""
