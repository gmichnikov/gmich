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

    reply_hint = (
        f"Reply to this email (or send a new message to {group_address}) "
        f"to add more tasks to {group.name}."
    )

    text_content = f"""Hi {sender_user.full_name},

Your task has been added to {group.name}:

  {task.title}
{details_text}

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
    </div>

    <p><a href="{group_url}">View the full task list &rarr;</a></p>

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
