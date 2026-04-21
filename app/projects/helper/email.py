"""Outbound email sending for the Helper project."""

import logging
import os

from app.utils.email_service import send_email

logger = logging.getLogger(__name__)


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

    # Build detail lines for the body
    details = []
    if task.due_date:
        details.append(f"Due: {task.due_date.strftime('%B %-d, %Y')}")
    if task.assignee:
        details.append(f"Assigned to: {task.assignee.full_name}")
    else:
        details.append(f"Assigned to: {sender_user.full_name}")

    details_text = "\n".join(f"  {d}" for d in details)
    details_html = "".join(f"<li>{d}</li>" for d in details)

    notes_text = f"\n  Notes: {task.notes}" if task.notes else ""
    notes_html = (
        f'<p style="margin:10px 0 0 0; font-size:0.9rem; color:#4b5563;">'
        f'<strong>Notes:</strong> {task.notes}</p>'
    ) if task.notes else ""

    reply_hint = (
        f"Reply to this email (or send a new message to {group_address}) "
        f"to add more tasks to {group.name}, or reply \u201cDone\u201d to mark this task complete."
    )

    text_content = f"""Hi {sender_user.full_name},

Your task has been added to {group.name}:

  {task.title}
{details_text}{notes_text}

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

    text_content = f"""Hi {sender_user.full_name},

Recorded in {group.name} as done:

  {task.title}

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
    .hint {{ font-size: 0.9rem; color: #4b5563; margin: 0; }}
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

    text_content = f"""Hi {sender_user.full_name},

This sounds like a task you already have open in {group.name}:

  {existing_task.title}

We did not create a duplicate. You can view or edit it here:

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
      <p style="margin:0; font-size:0.9rem; color:#4b5563;">No duplicate was added.</p>
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

    text_content = f"""Hi {sender_user.full_name},

Got it — marked as complete:

  {task.title}

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
    .task-title {{ font-size: 1.1rem; font-weight: bold; color: #15803d; margin: 0; }}
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
        tasks_text = "\n".join(f"  \u2022 {t.title}" for t in open_tasks)
        tasks_html = "".join(
            f'<li style="margin:4px 0;">{t.title}</li>' for t in open_tasks
        )
        list_section_text = f"Here are the currently open tasks:\n\n{tasks_text}"
        list_section_html = f"""<p>Here are the currently open tasks:</p>
    <ul style="padding-left:1.2rem; color:#374151;">{tasks_html}</ul>"""
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
