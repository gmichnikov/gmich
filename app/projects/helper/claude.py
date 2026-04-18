"""
Claude integration for the Helper project.

Calls Claude with the email subject + body and a list of group member names,
and returns a structured intent dict:

  {"intent": "add_task", "title": "...", "due_date": "YYYY-MM-DD" or null, "assignee_email": "..." or null}
  {"intent": "unknown"}

On any error (API, timeout, bad JSON), raises an exception so the caller can log it.
"""
import json
import logging
import os
from datetime import date
from zoneinfo import ZoneInfo

from anthropic import Anthropic

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5"


def _build_prompt(subject: str, body: str, member_names_emails: list[tuple[str, str]], sender_tz: str) -> str:
    """
    Build the Claude prompt.
    member_names_emails: list of (full_name, email) tuples for all group members.
    sender_tz: IANA timezone string for the sender (e.g. 'America/New_York').
    """
    today = date.today()
    try:
        tz = ZoneInfo(sender_tz)
        from datetime import datetime
        today = datetime.now(tz).date()
    except Exception:
        pass

    members_list = "\n".join(f"- {name} ({email})" for name, email in member_names_emails)

    return f"""You are a task-parsing assistant for a family task tracker.

Today's date is {today.isoformat()} (use this to resolve relative dates like "tomorrow" or "Friday").

The group members are:
{members_list}

An authorized group member sent the following email. Extract a task from it if possible.

---
Subject: {subject}
Body: {body or '(empty)'}
---

Respond with ONLY a valid JSON object (no explanation, no markdown) in one of these two formats:

If you can extract a task:
{{
  "intent": "add_task",
  "title": "concise task title",
  "due_date": "YYYY-MM-DD or null",
  "assignee_email": "exact email from the member list above, or null if unclear/unspecified"
}}

If the message is not a task request:
{{
  "intent": "unknown"
}}

Rules:
- Title should be short and action-oriented.
- due_date must be a calendar date string (YYYY-MM-DD) or null. No times.
- assignee_email must exactly match one of the emails in the member list, or be null.
- If the sender says "me" or "I", they are the assignee — but you don't know their email, so return null for assignee_email (the caller will default to the sender).
- Do not invent tasks. If the message is a question, reply, or chat, return unknown.
"""


def parse_email_for_task(
    subject: str,
    body: str,
    member_names_emails: list[tuple[str, str]],
    sender_tz: str = "UTC",
) -> dict:
    """
    Call Claude and return a parsed intent dict.
    Raises on API error, timeout, or unparseable JSON.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set")

    client = Anthropic(api_key=api_key)
    prompt = _build_prompt(subject, body, member_names_emails, sender_tz)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    logger.info(f"Claude raw response: {raw}")

    # Strip markdown code fences if present (some models wrap JSON despite instructions)
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()

    result = json.loads(raw)

    if "intent" not in result:
        raise ValueError(f"Claude response missing 'intent' key: {raw}")

    return result
