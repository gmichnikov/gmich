"""Email sending for the Reminders project."""

import logging
from zoneinfo import ZoneInfo
from flask import url_for
from app.utils.email_service import send_email

logger = logging.getLogger(__name__)


def _format_remind_at(reminder):
    """Format remind_at in the user's timezone for display in the email."""
    user = reminder.user
    user_tz = ZoneInfo(user.time_zone or "UTC")
    local_dt = reminder.remind_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(user_tz)
    tz_name = user.time_zone or "UTC"
    return local_dt.strftime(f"%b %-d, %Y %-I:%M %p") + f" ({tz_name})"


def send_reminder_email(reminder):
    """
    Send a reminder email to the reminder's owner.

    Args:
        reminder: Reminder model instance (with .user relationship loaded)

    Returns:
        True on success

    Raises:
        Exception if the email send fails
    """
    user = reminder.user
    manage_url = url_for("reminders.index", _external=True)
    scheduled_at_str = _format_remind_at(reminder)

    subject = f"Reminder: {reminder.title}"

    text_content = ""
    if reminder.body:
        text_content += f"{reminder.body}\n\n"
    text_content += f"You scheduled this reminder to be sent at {scheduled_at_str}.\n\n"
    text_content += f"Manage your reminders: {manage_url}"

    html_body = ""
    if reminder.body:
        html_body = f"<p>{reminder.body}</p>"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #999; border-top: 1px solid #eee; padding-top: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>{reminder.title}</h2>
        {html_body}
        <div class="footer">
            <p>You scheduled this reminder to be sent at {scheduled_at_str}.</p>
            <a href="{manage_url}">Manage your reminders</a>
        </div>
    </div>
</body>
</html>"""

    send_email(
        to_email=user.email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
    )
    return True
