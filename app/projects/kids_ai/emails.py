"""Parent emails. Flag mail is immediate; daily digest is a later phase."""

import logging
import os
from html import escape

from flask import url_for

from app.utils.email_service import send_email

logger = logging.getLogger(__name__)

FLAG_MAIL_TIMEOUT_SECONDS = 10


def _base_url():
    return os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")


def send_flag_email(parent, child, conversation, concern, paused):
    """Tell the parent a thread was locked. Never include the child's words."""
    if not parent or not parent.email:
        logger.warning("Kids AI flag email skipped: parent has no email")
        return None

    try:
        thread_path = url_for("kids_ai.parent_conversation", conversation_id=conversation.id)
    except Exception:
        thread_path = f"/kids-ai/conversations/{conversation.id}"
    thread_url = f"{_base_url()}{thread_path}"

    name = child.display_name
    concern_line = (concern or "Something in this conversation looked concerning.").strip()
    pause_text = ""
    pause_html = ""
    if paused:
        pause_text = (
            f"\nKids AI chatting is paused for {name} until you review "
            "and tap “Allow chatting again” on the dashboard.\n"
        )
        pause_html = (
            f"<p><strong>Chatting is paused</strong> for {escape(name)} until you review "
            "and tap “Allow chatting again” on the dashboard.</p>"
        )

    subject = f"Kids AI: please review a conversation with {name}"
    text_content = f"""A Kids AI conversation with {name} was locked.

{concern_line}
{pause_text}
Sign in to read the thread:
{thread_url}

This email does not include the child's exact words.
"""
    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.5; color: #222;">
  <p>A Kids AI conversation with <strong>{escape(name)}</strong> was locked.</p>
  <p>{escape(concern_line)}</p>
  {pause_html}
  <p><a href="{thread_url}">Sign in to read the thread</a></p>
  <p style="color: #666; font-size: 13px;">This email does not include the child's exact words.</p>
</body>
</html>
"""
    try:
        return send_email(
            to_email=parent.email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            timeout=FLAG_MAIL_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception("Kids AI flag email failed for %s", parent.email)
        return None
