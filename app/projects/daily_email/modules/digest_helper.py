"""Helper project tasks assigned to the user: due soon + no due date."""

import os
from html import escape

from sqlalchemy.orm import joinedload


def query_helper_tasks_for_digest(user) -> tuple[list, list]:
    """
    Return (tasks_with_due_soon, tasks_no_due).

    Open tasks where ``assignee_user_id`` is this user only (not unassigned
    "creator" tasks without an assignee).

    *Due soon:* ``due_date`` on or after *today* and on or before *today + 2*
    in the user’s local date (3 calendar days including today).

    *No due date:* ``due_date`` is NULL.
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from app.projects.helper.models import HelperTask

    tz = ZoneInfo(user.time_zone or "UTC")
    today = datetime.now(tz).date()
    end = today + timedelta(days=2)

    with_due = (
        HelperTask.query.options(joinedload(HelperTask.group))
        .filter(
            HelperTask.assignee_user_id == user.id,
            HelperTask.status == "open",
            HelperTask.due_date.isnot(None),
            HelperTask.due_date >= today,
            HelperTask.due_date <= end,
        )
        .order_by(HelperTask.due_date.asc(), HelperTask.id.asc())
        .limit(35)
        .all()
    )
    no_due = (
        HelperTask.query.options(joinedload(HelperTask.group))
        .filter(
            HelperTask.assignee_user_id == user.id,
            HelperTask.status == "open",
            HelperTask.due_date.is_(None),
        )
        .order_by(HelperTask.created_at.desc())
        .limit(25)
        .all()
    )
    return with_due, no_due


def _task_block(t, base: str) -> str:
    gname = escape((t.group.name if t.group else "") or "Group")
    title = escape(t.title or "(no title)")
    url = f"{base}/helper/task/{t.id}"
    h = f'<a href="{escape(url)}" style="color:#1a1a2e;font-weight:600;">{title}</a>'
    s = f'<div style="font-size:12px;color:#666;margin-top:2px;">{gname}</div>'
    if t.due_date:
        d = t.due_date
        ds = f"{d.strftime('%a, %b')} {d.day}, {d.strftime('%Y')}"
        s += f'<div style="font-size:12px;color:#2563eb;margin-top:2px;">Due {escape(ds)}</div>'
    if (t.notes or "").strip():
        n = escape((t.notes or "")[:150])
        if len(t.notes or "") > 150:
            n += "…"
        s += f'<div style="font-size:12px;color:#888;margin-top:3px;">{n}</div>'
    return f'<div style="margin:10px 0 0;padding:10px 0 0;border-top:1px solid #f0f0f0;">{h}{s}</div>'


def render_helper_section(user, tasks_dated: list, tasks_no_due: list) -> str:
    """Build HTML, or "" if there is nothing to show."""
    a = list(tasks_dated or [])
    b = list(tasks_no_due or [])
    if not a and not b:
        return ""

    base = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")

    parts: list[str] = []
    if a:
        parts.append(
            '<div style="font-size:12px;font-weight:700;color:#555;margin:0 0 6px;">'
            "Due in the next 3 days</div>"
        )
        for i, t in enumerate(a):
            blk = _task_block(t, base)
            if i == 0:
                blk = blk.replace(
                    "margin:10px 0 0;padding:10px 0 0;border-top:1px solid #f0f0f0",
                    "margin:0",
                    1,
                )
            parts.append(blk)
    if b:
        head = (
            '<div style="font-size:12px;font-weight:700;color:#555;margin:14px 0 6px;'
            'padding-top:8px;border-top:1px solid #eee;">No due date</div>'
        )
        if not a:
            head = (
                '<div style="font-size:12px;font-weight:700;color:#555;margin:0 0 6px;">'
                "No due date</div>"
            )
        parts.append(head)
        for i, t in enumerate(b):
            blk = _task_block(t, base)
            if i == 0 and not a:
                blk = blk.replace(
                    "margin:10px 0 0;padding:10px 0 0;border-top:1px solid #f0f0f0",
                    "margin:0",
                    1,
                )
            parts.append(blk)

    body = "".join(parts)
    return (
        '<div class="de-module de-module-helper">'
        '<div class="de-module-header">&#x1F9F0; Helper (assigned to you)</div>'
        '<div style="padding:8px 14px 12px;">' + body + f'<p style="margin:12px 0 0;font-size:12px;">'
        f'<a href="{escape(base + "/helper/")}" style="color:#2563eb;">Open Helper</a>. '
        f"Only open tasks with you as assignee."
        f"</p></div></div>"
    )
