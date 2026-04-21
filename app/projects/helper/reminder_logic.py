"""
Default reminder scheduling for Helper tasks.

PRD: calendar day before due at 10:00 in assignee-or-creator local time.
Storage: naive UTC datetimes (consistent with HelperTask.completed_at).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.models import User


def _zone_for_user(user: User | None) -> ZoneInfo:
    if user is None:
        return ZoneInfo("UTC")
    tz_name = getattr(user, "time_zone", None) or "UTC"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def tz_user_for_reminder_defaults(task) -> User:
    """Assignee if set, else creator (loaded or fetched)."""
    if task.assignee:
        return task.assignee
    if task.creator:
        return task.creator
    return User.query.get(task.created_by_user_id)


def compute_default_reminder_at(task) -> datetime | None:
    """
    Return naive UTC datetime for default reminder, or None if no default applies.

    Requires task.due_date; uses assignee-or-creator timezone for "today" and
    for placing 10:00 local on the calendar day before the due date.
    """
    if not task.due_date:
        return None

    user = tz_user_for_reminder_defaults(task)
    tz = _zone_for_user(user)
    today_local = datetime.now(tz).date()
    due = task.due_date
    if due <= today_local:
        return None

    reminder_local_date = due - timedelta(days=1)
    local_dt = datetime.combine(reminder_local_date, time(10, 0), tzinfo=tz)
    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
    return utc_dt.replace(tzinfo=None)


def sync_reminder_with_due_date(task) -> None:
    """Recompute default from due_date; clears reminder_sent_at (PRD: due change)."""
    task.reminder_at = compute_default_reminder_at(task)
    task.reminder_sent_at = None


def clear_task_reminders(task) -> None:
    """Clear pending reminder (e.g. on complete)."""
    task.reminder_at = None
    task.reminder_sent_at = None


def reminder_recipient_user(task) -> User | None:
    """Email recipient: assignee, else creator."""
    if task.assignee:
        return task.assignee
    if task.creator:
        return task.creator
    if task.created_by_user_id:
        return User.query.get(task.created_by_user_id)
    return None


def reminder_preview_for_viewer(task, viewer_user) -> str | None:
    """
    One-line preview: "Reminder: Mon Apr 18, 10:00 AM · email to Alex"
    Uses viewer's timezone for display (PRD).
    """
    from app.utils.user_time import format_user_local_datetime

    if task.status != "open" or not task.reminder_at:
        return None
    r = reminder_recipient_user(task)
    if not r:
        return None
    when = format_user_local_datetime(task.reminder_at, viewer_user, "%a %b %-d, %-I:%M %p")
    return f"Reminder: {when} · email to {r.full_name}"


def parse_reminder_at_iso(raw: str) -> datetime | None:
    """Parse client ISO string to naive UTC datetime."""
    raw = (raw or "").strip()
    if not raw:
        return None
    s = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    return dt
