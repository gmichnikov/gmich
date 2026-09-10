"""Parent emails: immediate flag mail and the daily digest."""

import logging
import os
from html import escape

from flask import url_for

from app.utils.email_service import send_email

logger = logging.getLogger(__name__)

FLAG_MAIL_TIMEOUT_SECONDS = 10
DIGEST_MAIL_TIMEOUT_SECONDS = 15
SNIPPET_CHARS = 220


def snippet(text):
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= SNIPPET_CHARS:
        return cleaned
    return cleaned[: SNIPPET_CHARS - 3].rstrip() + "..."


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


def send_digest_email(parent, child_blocks):
    """One daily digest. ``child_blocks`` from ``jobs.run_daily_digest``."""
    if not parent or not parent.email:
        raise ValueError("parent has no email")

    try:
        dashboard_path = url_for("kids_ai.dashboard")
    except Exception:
        dashboard_path = "/kids-ai/dashboard"
    dashboard_url = f"{_base_url()}{dashboard_path}"

    text_sections = []
    html_sections = []
    child_count = len(child_blocks)
    conversation_count = sum(len(block["conversations"]) for block in child_blocks)

    for block in child_blocks:
        child = block["child"]
        lines = block["lines"]
        text_sections.append("\n".join(lines))
        items = []
        for conversation in block["conversations"]:
            title = escape(conversation.title or "Untitled conversation")
            locked = " <em>(locked)</em>" if conversation.locked else ""
            body = escape(
                snippet(conversation.running_summary) or "No summary stored yet."
            )
            items.append(f"<li><strong>{title}</strong>{locked} — {body}</li>")
        html_sections.append(
            f"<h3 style=\"margin: 1.25rem 0 0.4rem;\">{escape(child.display_name)}</h3>"
            f"<p style=\"margin: 0 0 0.4rem; color: #555;\">{len(block['conversations'])} "
            f"conversation{'s' if len(block['conversations']) != 1 else ''}</p>"
            f"<ul style=\"margin: 0; padding-left: 1.2rem;\">{''.join(items)}</ul>"
        )

    subject = "Kids AI: yesterday’s conversations"
    if child_count == 1:
        subject = f"Kids AI: {child_blocks[0]['child'].display_name} yesterday"

    text_content = f"""Kids AI summary for the last 24 hours.

{chr(10).join(text_sections)}

Sign in to read the full threads:
{dashboard_url}

This email uses stored summaries. It does not include the child's exact words.
"""
    html_content = f"""<!DOCTYPE html>
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.5; color: #222;">
  <p>Kids AI summary for the last 24 hours ({conversation_count} conversation{'s' if conversation_count != 1 else ''} across {child_count} {'child' if child_count == 1 else 'children'}).</p>
  {''.join(html_sections)}
  <p style="margin-top: 1.5rem;"><a href="{dashboard_url}">Sign in to the parent dashboard</a></p>
  <p style="color: #666; font-size: 13px;">This email uses stored summaries. It does not include the child's exact words.</p>
</body>
</html>
"""
    return send_email(
        to_email=parent.email,
        subject=subject,
        text_content=text_content,
        html_content=html_content,
        timeout=DIGEST_MAIL_TIMEOUT_SECONDS,
    )
