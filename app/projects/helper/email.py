"""Outbound email sending for the Helper project."""

import html as html_module
import logging
import os
from datetime import datetime

from app.utils.email_service import send_email
from app.utils.user_time import format_user_local_datetime

logger = logging.getLogger(__name__)


def _fmt_date(d):
    """Format a date for email bodies (matches task-added style)."""
    return d.strftime("%B %-d, %Y")


def _fmt_datetime_recipient_local(dt, user):
    """
    Format a naive UTC datetime in the recipient's profile timezone.
    Includes abbreviation (e.g. EDT) and explicit IANA id (e.g. America/New_York).
    """
    if dt is None or not isinstance(dt, datetime):
        return ""
    iana = (getattr(user, "time_zone", None) or "UTC") if user is not None else "UTC"
    wall = format_user_local_datetime(
        dt, user, "%B %-d, %Y at %-I:%M %p %Z"
    )
    return f"{wall} ({iana})"


def _notes_block(task):
    notes_text = f"\n  Notes: {task.notes}" if task.notes else ""
    notes_html = (
        f'<p style="margin:10px 0 0 0; font-size:0.9rem; color:#4b5563;">'
        f"<strong>Notes:</strong> {task.notes}</p>"
    ) if task.notes else ""
    return notes_text, notes_html


def _reminder_scheduled_notice(task, recipient_user):
    """
    If an open task has a pending reminder, return extra plaintext + HTML
    stating when the reminder email will be sent and that it can be changed on the task page.
    """
    if not task.reminder_at or task.status != "open":
        return "", ""
    when = _fmt_datetime_recipient_local(task.reminder_at, recipient_user)
    text = (
        f"\n\nReminder email: we\u2019ll send one around {when}. "
        f"You can change the time or turn it off on the task page if you need to."
    )
    html = (
        f'<p style="margin:12px 0 0 0; font-size:0.9rem; color:#374151;">'
        f"<strong>Reminder email:</strong> we&rsquo;ll send one around {html_module.escape(when)}. "
        f"You can change the time or turn it off on the task page if you need to."
        f"</p>"
    )
    return text, html


def _due_assignee_lines(task, sender_user, *, unassigned_use_sender=True):
    """Build Due + Assigned lines (same semantics as task-added email when unassigned_use_sender)."""
    lines = []
    if task.due_date:
        lines.append(f"Due: {_fmt_date(task.due_date)}")
    if task.assignee:
        lines.append(f"Assigned to: {task.assignee.full_name}")
    else:
        if unassigned_use_sender:
            lines.append(f"Assigned to: {sender_user.full_name}")
        else:
            lines.append("Assigned to: Unassigned")
    return lines


def _lines_to_text_and_html(lines):
    details_text = "\n".join(f"  {d}" for d in lines) if lines else ""
    details_html = "".join(f"<li>{d}</li>" for d in lines) if lines else ""
    return details_text, details_html


def _completed_summary_lines(task, recipient_user):
    """Extra context after a task is marked complete (time, due, assignee)."""
    lines = []
    if task.completed_at:
        who = f" by {task.completer.full_name}" if task.completer else ""
        when = _fmt_datetime_recipient_local(task.completed_at, recipient_user)
        lines.append(f"Completed: {when}{who}")
    if task.due_date:
        lines.append(f"Due: {_fmt_date(task.due_date)}")
    if task.assignee:
        lines.append(f"Assigned to: {task.assignee.full_name}")
    else:
        lines.append("Assigned to: Unassigned")
    return lines


def _open_tasks_rich_list_for_failed(open_tasks, max_notes=100):
    """Plaintext + HTML lines listing open tasks with due, assignee, notes snippet."""
    text_lines = []
    html_items = []
    for t in open_tasks:
        bits = []
        if t.due_date:
            bits.append(f"Due {_fmt_date(t.due_date)}")
        if t.assignee:
            bits.append(f"Assigned: {t.assignee.full_name}")
        else:
            bits.append("Unassigned")
        if t.notes:
            n = " ".join(t.notes.split())
            if len(n) > max_notes:
                n = n[: max_notes - 1] + "…"
            bits.append(f"Notes: {n}")
        sub = " · ".join(bits)
        text_lines.append(f"  • {t.title}")
        text_lines.append(f"    {sub}")
        esc_title = html_module.escape(t.title)
        esc_sub = html_module.escape(sub)
        html_items.append(
            f'<li style="margin:8px 0;"><strong>{esc_title}</strong><br>'
            f'<span style="font-size:0.88rem;color:#4b5563;">{esc_sub}</span></li>'
        )
    return "\n".join(text_lines), "".join(html_items)


def send_task_confirmation(task, sender_user, group):
    """
    Send a confirmation email to the sender after a task is created via inbound email.

    From:     Helper (Group Name) <group-inbound@helper.gregmichnikov.com>
    Reply-To: group-inbound@helper.gregmichnikov.com
              (so the sender can reply to add more tasks seamlessly)
    To:       sender_user.email

    Args:
        task: HelperTask instance (freshly committed, has .id)
        sender_user: User instance (the person who sent the original email)
        group: HelperGroup instance

    Returns:
        True on success, None on failure (error is logged, never raised)
    """
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    group_url = f"{base_url}/helper/group/{group.id}"
    task_url = f"{base_url}/helper/task/{task.id}"
    group_address = group.inbound_email

    subject = f"\u2713 Task added: {task.title}"

    detail_lines = _due_assignee_lines(task, sender_user, unassigned_use_sender=True)
    details_text, details_html = _lines_to_text_and_html(detail_lines)
    notes_text, notes_html = _notes_block(task)
    reminder_notice_text, reminder_notice_html = _reminder_scheduled_notice(
        task, sender_user
    )

    reply_hint = (
        f"Reply to this email (or send a new message to {group_address}) "
        f"to add more tasks to {group.name}, or reply \u201cDone\u201d to mark this task complete."
    )

    text_content = f"""Hi {sender_user.full_name},

Your task has been added to {group.name}:

  {task.title}
{details_text}{notes_text}{reminder_notice_text}

View this task: {task_url}
View the full task list: {group_url}

{reply_hint}
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 24px; }}
    .task-box {{ background: #f0fdf4; border-left: 4px solid #22c55e; border-radius: 4px; padding: 16px 20px; margin: 20px 0; }}
    .task-title {{ font-size: 1.1rem; font-weight: bold; color: #15803d; margin: 0 0 8px 0; }}
    .task-details {{ list-style: none; margin: 0; padding: 0; color: #374151; font-size: 0.95rem; }}
    .task-details li {{ margin: 4px 0; }}
    .footer {{ margin-top: 28px; font-size: 0.82rem; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 14px; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <div class="container">
    <p>Hi {sender_user.full_name},</p>
    <p>Your task has been added to <strong>{group.name}</strong>:</p>

    <div class="task-box">
      <p class="task-title">{task.title}</p>
      <ul class="task-details">
        {details_html}
      </ul>
      {notes_html}
      {reminder_notice_html}
    </div>

    <p>
      <a href="{task_url}">View this task &rarr;</a><br>
      <a href="{group_url}">View the full task list &rarr;</a>
    </p>

    <div class="footer">
      <p>{reply_hint}</p>
    </div>
  </div>
</body>
</html>"""

    try:
        send_email(
            to_email=sender_user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            from_name=f"Helper ({group.name})",
            from_email=group_address,
            reply_to=group_address,
        )
        logger.info(
            f"Task confirmation sent to {sender_user.email} "
            f"for task id={task.id} group={group.id}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to send task confirmation to {sender_user.email} "
            f"for task id={task.id}: {e}"
        )
        return None


def send_task_logged_completed_confirmation(task, sender_user, group):
    """
    Confirm that a task was recorded as already done (created in completed state).

    Args:
        task: HelperTask (status complete, source + completed_via set to same inbound)
        sender_user: User who sent the email
        group: HelperGroup
    """
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    group_url = f"{base_url}/helper/group/{group.id}"
    task_url = f"{base_url}/helper/task/{task.id}"
    group_address = group.inbound_email

    subject = f"\u2713 Logged: {task.title}"

    summary_lines = _completed_summary_lines(task, sender_user)
    details_text, details_html = _lines_to_text_and_html(summary_lines)
    notes_text, notes_html = _notes_block(task)

    text_content = f"""Hi {sender_user.full_name},

Recorded in {group.name} as done:

  {task.title}
{details_text}{notes_text}

(This was not matched to an open task — it is saved to your history as completed.)

View this entry: {task_url}
Full task list: {group_url}

Reply to this email (or send to {group_address}) to add tasks or report more completed work.
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 24px; }}
    .task-box {{ background: #f0fdf4; border-left: 4px solid #22c55e; border-radius: 4px; padding: 16px 20px; margin: 20px 0; }}
    .task-title {{ font-size: 1.1rem; font-weight: bold; color: #15803d; margin: 0 0 8px 0; }}
    .task-details {{ list-style: none; margin: 0; padding: 0; color: #374151; font-size: 0.95rem; }}
    .task-details li {{ margin: 4px 0; }}
    .hint {{ font-size: 0.9rem; color: #4b5563; margin: 0.75rem 0 0 0; }}
    .footer {{ margin-top: 28px; font-size: 0.82rem; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 14px; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <div class="container">
    <p>Hi {sender_user.full_name},</p>
    <p>Recorded in <strong>{group.name}</strong> as done:</p>

    <div class="task-box">
      <p class="task-title">{task.title}</p>
      <ul class="task-details">
        {details_html}
      </ul>
      {notes_html}
      <p class="hint">Not matched to an open task — saved to your history as completed.</p>
    </div>

    <p>
      <a href="{task_url}">View this entry &rarr;</a><br>
      <a href="{group_url}">View the full task list &rarr;</a>
    </p>

    <div class="footer">
      <p>Reply to this email (or send to {group_address}) to add tasks or report more completed work.</p>
    </div>
  </div>
</body>
</html>"""

    try:
        send_email(
            to_email=sender_user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            from_name=f"Helper ({group.name})",
            from_email=group_address,
            reply_to=group_address,
        )
        logger.info(
            f"Logged-completed confirmation sent to {sender_user.email} "
            f"for task id={task.id} group={group.id}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to send logged-completed confirmation to {sender_user.email} "
            f"for task id={task.id}: {e}"
        )
        return None


def send_duplicate_task_skipped(existing_task, sender_user, group):
    """
    Tell the sender we did not add a new task because it matches an open task already.

    Args:
        existing_task: HelperTask (open, same group)
        sender_user: User who sent the inbound email
        group: HelperGroup

    Returns:
        True on success, None on failure (error is logged)
    """
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    group_url = f"{base_url}/helper/group/{group.id}"
    task_url = f"{base_url}/helper/task/{existing_task.id}"
    group_address = group.inbound_email

    subject = f"Already on your list: {existing_task.title}"

    detail_lines = _due_assignee_lines(
        existing_task, sender_user, unassigned_use_sender=False
    )
    details_text, details_html = _lines_to_text_and_html(detail_lines)
    notes_text, notes_html = _notes_block(existing_task)
    reminder_notice_text, reminder_notice_html = _reminder_scheduled_notice(
        existing_task, sender_user
    )

    text_content = f"""Hi {sender_user.full_name},

This sounds like a task you already have open in {group.name}:

  {existing_task.title}
{details_text}{notes_text}{reminder_notice_text}

We did not create a duplicate. View or edit it here:

  {task_url}

Full task list: {group_url}

Reply to this email (or send to {group_address}) to add something else or reply \"Done\" to complete a task.
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 24px; }}
    .task-box {{ background: #eff6ff; border-left: 4px solid #3b82f6; border-radius: 4px; padding: 16px 20px; margin: 20px 0; }}
    .task-title {{ font-size: 1.1rem; font-weight: bold; color: #1e40af; margin: 0 0 8px 0; }}
    .task-details {{ list-style: none; margin: 0; padding: 0; color: #374151; font-size: 0.95rem; }}
    .task-details li {{ margin: 4px 0; }}
    .footer {{ margin-top: 28px; font-size: 0.82rem; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 14px; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <div class="container">
    <p>Hi {sender_user.full_name},</p>
    <p>This sounds like a task you <strong>already have open</strong> in <strong>{group.name}</strong>:</p>

    <div class="task-box">
      <p class="task-title">{existing_task.title}</p>
      <ul class="task-details">
        {details_html}
      </ul>
      {notes_html}
      {reminder_notice_html}
      <p style="margin:0.75rem 0 0 0; font-size:0.9rem; color:#4b5563;">No duplicate was added.</p>
    </div>

    <p>
      <a href="{task_url}">View this task &rarr;</a><br>
      <a href="{group_url}">View the full task list &rarr;</a>
    </p>

    <div class="footer">
      <p>Reply to this email (or send to {group_address}) to add something else or mark a task complete.</p>
    </div>
  </div>
</body>
</html>"""

    try:
        send_email(
            to_email=sender_user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            from_name=f"Helper ({group.name})",
            from_email=group_address,
            reply_to=group_address,
        )
        logger.info(
            f"Duplicate task notice sent to {sender_user.email} "
            f"for existing task id={existing_task.id} group={group.id}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to send duplicate task notice to {sender_user.email} "
            f"for task id={existing_task.id}: {e}"
        )
        return None


def send_task_completed_confirmation(task, sender_user, group):
    """
    Notify the sender that their email marked a task as complete.

    Args:
        task: HelperTask instance (already marked complete)
        sender_user: User who completed it
        group: HelperGroup
    """
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    group_url = f"{base_url}/helper/group/{group.id}"
    task_url = f"{base_url}/helper/task/{task.id}"
    group_address = group.inbound_email

    subject = f"\u2713 Marked complete: {task.title}"

    summary_lines = _completed_summary_lines(task, sender_user)
    details_text, details_html = _lines_to_text_and_html(summary_lines)
    notes_text, notes_html = _notes_block(task)

    text_content = f"""Hi {sender_user.full_name},

Got it — marked as complete:

  {task.title}
{details_text}{notes_text}

View this task: {task_url}
View the full task list: {group_url}

Reply to this email (or send to {group_address}) to add more tasks or complete others.
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 24px; }}
    .task-box {{ background: #f0fdf4; border-left: 4px solid #22c55e; border-radius: 4px; padding: 16px 20px; margin: 20px 0; }}
    .task-title {{ font-size: 1.1rem; font-weight: bold; color: #15803d; margin: 0 0 8px 0; }}
    .task-details {{ list-style: none; margin: 0; padding: 0; color: #374151; font-size: 0.95rem; }}
    .task-details li {{ margin: 4px 0; }}
    .footer {{ margin-top: 28px; font-size: 0.82rem; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 14px; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <div class="container">
    <p>Hi {sender_user.full_name},</p>
    <p>Got it — marked as complete:</p>

    <div class="task-box">
      <p class="task-title">{task.title}</p>
      <ul class="task-details">
        {details_html}
      </ul>
      {notes_html}
    </div>

    <p>
      <a href="{task_url}">View this task &rarr;</a><br>
      <a href="{group_url}">View the full task list &rarr;</a>
    </p>

    <div class="footer">
      <p>Reply to this email (or send to {group_address}) to add more tasks or complete others.</p>
    </div>
  </div>
</body>
</html>"""

    try:
        send_email(
            to_email=sender_user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            from_name=f"Helper ({group.name})",
            from_email=group_address,
            reply_to=group_address,
        )
        logger.info(
            f"Task completed confirmation sent to {sender_user.email} "
            f"for task id={task.id} group={group.id}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to send task completed confirmation to {sender_user.email} "
            f"for task id={task.id}: {e}"
        )
        return None


def send_complete_task_failed(open_tasks, sender_user, group):
    """
    Tell the sender we couldn't identify which task they meant, and list open tasks.

    Args:
        open_tasks: list of HelperTask instances currently open in the group
        sender_user: User who sent the email
        group: HelperGroup
    """
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    group_url = f"{base_url}/helper/group/{group.id}"
    group_address = group.inbound_email

    subject = f"Couldn\u2019t identify which task to complete \u2014 {group.name}"

    if open_tasks:
        tasks_text, tasks_html = _open_tasks_rich_list_for_failed(open_tasks)
        list_section_text = f"Here are the currently open tasks:\n\n{tasks_text}"
        list_section_html = f"""<p>Here are the currently open tasks:</p>
    <ul style="padding-left:1.2rem; color:#374151; list-style:none;">{tasks_html}</ul>"""
    else:
        list_section_text = "There are no open tasks in this group right now."
        list_section_html = "<p>There are no open tasks in this group right now.</p>"

    text_content = f"""Hi {sender_user.full_name},

We received your email but couldn't figure out which task you meant to complete.

{list_section_text}

To complete a task, reply with something like "Done with [task name]" or mark it complete on the task list: {group_url}

You can also reply to this email to add a new task.
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 24px; }}
    .notice-box {{ background: #fef9c3; border-left: 4px solid #eab308; border-radius: 4px; padding: 14px 18px; margin: 20px 0; color: #713f12; font-size: 0.9rem; }}
    .footer {{ margin-top: 28px; font-size: 0.82rem; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 14px; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <div class="container">
    <p>Hi {sender_user.full_name},</p>

    <div class="notice-box">
      We received your email but couldn&rsquo;t figure out which task you meant to complete.
    </div>

    {list_section_html}

    <p>To complete a task, reply with something like <em>&ldquo;Done with [task name]&rdquo;</em> or <a href="{group_url}">mark it complete on the task list</a>.</p>

    <div class="footer">
      <p>You can also reply to this email to add a new task.</p>
    </div>
  </div>
</body>
</html>"""

    try:
        send_email(
            to_email=sender_user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            from_name=f"Helper ({group.name})",
            from_email=group_address,
            reply_to=group_address,
        )
        logger.info(
            f"Complete-task-failed email sent to {sender_user.email} group={group.id}"
        )
        return True
    except Exception as e:
        logger.error(
            f"Failed to send complete-task-failed email to {sender_user.email}: {e}"
        )
        return None


def send_task_reminder_email(task, recipient_user, group):
    """
    Scheduled reminder for an open task (assignee or creator).

    Subject includes due date + short title for inbox triage (PRD).
    """
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    group_url = f"{base_url}/helper/group/{group.id}"
    task_url = f"{base_url}/helper/task/{task.id}"
    group_address = group.inbound_email

    due_part = _fmt_date(task.due_date) if task.due_date else "no date"
    title_short = task.title if len(task.title) <= 70 else task.title[:67] + "…"
    subject = f"Reminder: Due {due_part} — {title_short}"

    notes_line = f"\n\nNotes: {task.notes}" if task.notes else ""
    title_esc = html_module.escape(task.title)
    notes_html = (
        f'<p style="margin:12px 0 0 0; font-size:0.9rem; color:#4b5563;"><strong>Notes:</strong> '
        f"{html_module.escape(task.notes)}</p>"
    ) if task.notes else ""

    reminder_when = ""
    reminder_html_fragment = ""
    if task.reminder_at:
        rw = _fmt_datetime_recipient_local(task.reminder_at, recipient_user)
        reminder_when = f"\n  This reminder was scheduled for: {rw}"
        reminder_html_fragment = (
            f'<p class="reminder-line"><strong>Scheduled for:</strong> '
            f"{html_module.escape(rw)}</p>"
        )

    change_reminder_text = (
        f"\nTo change or clear reminder emails for this task, open the task page:\n  {task_url}\n"
    )
    change_reminder_html = (
        f'<p style="margin:14px 0 0 0; font-size:0.9rem; color:#4b5563;">'
        f"To change or clear reminder emails for this task, "
        f'<a href="{task_url}">open the task page</a>.</p>'
    )

    text_content = f"""Hi {recipient_user.full_name},

Reminder — this task is coming due for {group.name}:

  {task.title}
  Due: {_fmt_date(task.due_date) if task.due_date else "(no due date)"}{reminder_when}{notes_line}

Open task: {task_url}
Group list: {group_url}
{change_reminder_text}
Reply to {group_address} to add tasks or send updates.
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
    .container {{ max-width: 560px; margin: 0 auto; padding: 24px; }}
    .task-box {{ background: #eff6ff; border-left: 4px solid #3b82f6; border-radius: 4px; padding: 16px 20px; margin: 20px 0; }}
    .task-title {{ font-size: 1.1rem; font-weight: bold; color: #1e3a8a; margin: 0 0 8px 0; }}
    .due-line {{ font-size: 0.95rem; color: #374151; margin: 0; }}
    .reminder-line {{ font-size: 0.92rem; color: #4b5563; margin: 8px 0 0 0; }}
    .footer {{ margin-top: 28px; font-size: 0.82rem; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 14px; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <div class="container">
    <p>Hi {recipient_user.full_name},</p>
    <p>Reminder — <strong>{html_module.escape(group.name)}</strong>:</p>

    <div class="task-box">
      <p class="task-title">{title_esc}</p>
      <p class="due-line">Due: {_fmt_date(task.due_date) if task.due_date else "(no due date)"}</p>
      {reminder_html_fragment}
      {notes_html}
    </div>

    <p>
      <a href="{task_url}">Open this task &rarr;</a><br>
      <a href="{group_url}">View the group task list &rarr;</a>
    </p>

    {change_reminder_html}

    <div class="footer">
      <p>Reply to {group_address} to add tasks or send updates.</p>
    </div>
  </div>
</body>
</html>"""

    try:
        send_email(
            to_email=recipient_user.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            from_name=f"Helper ({group.name})",
            from_email=group_address,
            reply_to=group_address,
        )
        logger.info(
            "Task reminder sent to %s for task id=%s group=%s",
            recipient_user.email,
            task.id,
            group.id,
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to send task reminder to %s for task id=%s: %s",
            recipient_user.email,
            task.id,
            e,
        )
        return None


def notify_eval_summary_to_admin(
    run_id: int,
    model: str,
    total: int,
    passed: int,
    failed: int,
    errored: int,
    failed_fixtures: list[dict],
):
    """
    Email ADMIN_EMAIL a summary of a router eval run.

    Always sent (pass or fail) so the daily run acts as a heartbeat.
    Skips quietly if ADMIN_EMAIL is unset. Logs failures; does not raise.

    failed_fixtures: list of dicts with keys fixture_id, expected_route, actual_route, error_message.
    """
    admin = os.getenv("ADMIN_EMAIL", "").strip()
    if not admin:
        logger.warning("ADMIN_EMAIL not set; skipping eval summary notification")
        return None

    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    run_url = f"{base_url}/admin/helper/evals/{run_id}"
    pct = int(100 * passed / total) if total else 0

    if failed or errored:
        subject = f"[Helper Eval] {passed}/{total} passed ({pct}%) — {failed + errored} failure{'s' if failed + errored != 1 else ''}"
    else:
        subject = f"[Helper Eval] All {total} passed ✓"

    failures_block = ""
    if failed_fixtures:
        lines = []
        for fx in failed_fixtures:
            actual = fx.get("actual_route") or fx.get("error_message") or "—"
            lines.append(f"  • {fx['fixture_id']}: expected {fx['expected_route']}, got {actual}")
        failures_block = "\nFailed:\n" + "\n".join(lines) + "\n"

    text_content = f"""Router eval run complete.

Run #{run_id} · {model}
Total: {total}  Passed: {passed}  Failed: {failed}  Errored: {errored}  ({pct}%)
{failures_block}
View results: {run_url}
"""

    try:
        send_email(
            to_email=admin,
            subject=subject,
            text_content=text_content,
            from_name="Helper",
        )
        logger.info("Eval summary sent to admin for run_id=%s", run_id)
        return True
    except Exception as e:
        logger.error("Failed to send eval summary for run_id=%s: %s", run_id, e)
        return None


def notify_helper_claude_error_to_admin(
    inbound_id: int,
    group_name: str,
    sender_email: str,
    error_message: str,
    raw_response: str | None = None,
):
    """
    Email ADMIN_EMAIL when Helper inbound processing fails (Claude/parse/API).

    Skips quietly if ADMIN_EMAIL is unset. Logs failures; does not raise.
    """
    admin = os.getenv("ADMIN_EMAIL", "").strip()
    if not admin:
        logger.warning("ADMIN_EMAIL not set; skipping Helper Claude error notification")
        return None

    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    admin_inbound = f"{base_url}/admin/helper/email-detail"
    admin_log = f"{base_url}/admin/helper/action-log"

    subject = f"[Helper] Claude error — inbound #{inbound_id}"

    raw_block = ""
    if raw_response:
        cap = 6000
        body = raw_response if len(raw_response) <= cap else raw_response[:cap] + "\n... [truncated]"
        raw_block = f"\n--- Claude raw response ---\n{body}\n"

    text_content = f"""Helper inbound email processing failed.

Inbound id: {inbound_id}
Group: {group_name}
Sender: {sender_email}

Error:
{error_message}
{raw_block}
Admin: {admin_inbound} (find this id in the list)
Action log: {admin_log}
"""

    try:
        send_email(
            to_email=admin,
            subject=subject,
            text_content=text_content,
            from_name="Helper",
        )
        logger.info(
            "Helper Claude error alert sent to admin for inbound_id=%s", inbound_id
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to send Helper Claude error alert for inbound_id=%s: %s",
            inbound_id,
            e,
        )
        return None
