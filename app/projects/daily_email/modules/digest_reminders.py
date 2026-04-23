"""Reminders (from the Reminders project) in the next 24 hours for the daily digest."""

import os
from datetime import datetime, timedelta
from html import escape

from zoneinfo import ZoneInfo


def query_upcoming_reminders_for_digest(user) -> list:
    """Unsent reminders with ``remind_at`` in (now, now+24h], ordered ascending."""
    from app.projects.reminders.models import Reminder

    now_utc = datetime.utcnow()
    end_utc = now_utc + timedelta(hours=24)
    return (
        Reminder.query.filter_by(user_id=user.id)
        .filter(Reminder.sent_at.is_(None))
        .filter(Reminder.remind_at > now_utc)
        .filter(Reminder.remind_at <= end_utc)
        .order_by(Reminder.remind_at.asc())
        .all()
    )


def render_reminders_section(user, reminders: list) -> str:
    """
    Build HTML for upcoming reminders, or "" if none.

    Callers pre-query ``Reminder`` rows: unsent, ``remind_at`` strictly after *now* (UTC)
    and on or before *now* + 24h, ordered by ``remind_at``.
    """
    rlist = list(reminders or [])
    if not rlist:
        return ""

    user_tz = ZoneInfo(user.time_zone or "UTC")
    base = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    reminders_url = f"{base}/reminders/"

    parts = []
    for i, r in enumerate(rlist):
        local = r.remind_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(user_tz)
        tstr = local.strftime("%a, %b %-d %-I:%M %p %Z")
        title = escape(r.title or "(no title)")
        top = "" if i == 0 else "border-top:1px solid #f0f0f0;padding-top:10px;margin-top:10px;"
        sub = f'<div style="font-size:12px;color:#666;margin-top:2px;">{escape(tstr)}</div>'
        if (r.body or "").strip():
            b = escape((r.body or "")[:200])
            if len(r.body or "") > 200:
                b += "…"
            sub += f'<div style="font-size:12px;color:#888;margin-top:4px;">{b}</div>'
        parts.append(
            f'<div style="{top}">'
            f'<div style="font-weight:600;color:#1a1a2e;">{title}</div>{sub}</div>'
        )

    return (
        '<div class="de-module de-module-reminders">'
        '<div class="de-module-header">&#9200; Reminders (next 24h)</div>'
        '<div style="padding:8px 14px 12px;">'
        + "".join(parts)
        + f'<p style="margin:12px 0 0;font-size:12px;">'
        f'<a href="{escape(reminders_url)}" style="color:#2563eb;">'
        f"Open Reminders</a> to add or change alerts."
        f"</p></div></div>"
    )
