"""
Claude integration for the Helper project.

Calls Claude with the email subject + body, group member names, and currently
open tasks, then returns a structured intent dict:

  {"intent": "add_task", "title": "...", "due_date": "YYYY-MM-DD" or null,
   "assignee_email": "..." or null, "notes": "..." or null}
  {"intent": "complete_task", "task_id": <int>}
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


def _build_prompt(
    subject: str,
    body: str,
    member_names_emails: list[tuple[str, str]],
    sender_tz: str,
    open_tasks: list[dict],
) -> str:
    """
    Build the Claude prompt.
    member_names_emails: list of (full_name, email) tuples for all group members.
    sender_tz: IANA timezone string for the sender (e.g. 'America/New_York').
    open_tasks: list of dicts with keys id, title, notes (may be empty list).
    """
    today = date.today()
    try:
        tz = ZoneInfo(sender_tz)
        from datetime import datetime
        today = datetime.now(tz).date()
    except Exception:
        pass

    members_list = "\n".join(f"- {name} ({email})" for name, email in member_names_emails)

    if open_tasks:
        tasks_lines = "\n".join(
            f"- [id={t['id']}] \"{t['title']}\""
            + (f" — {t['notes']}" if t.get("notes") else "")
            for t in open_tasks
        )
        open_tasks_section = f"""The following tasks are currently open in this group:
{tasks_lines}
"""
    else:
        open_tasks_section = "There are no open tasks in this group currently.\n"

    return f"""You are a task-parsing assistant for a family task tracker.

Today's date is {today.isoformat()} (use this to resolve relative dates like "tomorrow" or "Friday").

The group members are:
{members_list}

{open_tasks_section}
An authorized group member sent the following email. They use this address for two purposes:
1. To add a new task — including by forwarding emails (e.g. a sign-up link, a bill, an event announcement).
2. To indicate that one of the open tasks listed above has been completed.

---
Subject: {subject}
Body: {body or '(empty)'}
---

Respond with ONLY a valid JSON object (no explanation, no markdown) in one of these formats:

If you can extract a new task:
{{
  "intent": "add_task",
  "title": "concise task title",
  "due_date": "YYYY-MM-DD or null",
  "assignee_email": "exact email from the member list above, or null if unclear/unspecified",
  "notes": "supplementary context or null"
}}

If the email indicates an open task is done (match by content to the open task list above):
{{
  "intent": "complete_task",
  "task_id": <id integer from the open task list>
}}

If the intent is unclear or the message is purely conversational:
{{
  "intent": "unknown"
}}

Rules:
- For add_task: title should be short and action-oriented (e.g. "Register for lacrosse clinic").
- due_date must be a calendar date string (YYYY-MM-DD) or null. No times.
- assignee_email must exactly match one of the emails in the member list, or be null.
- If the sender says "me" or "I", they are the assignee — return null for assignee_email (the caller defaults to the sender).
- notes should capture supplementary detail not in the title: location, price, registration links, event times, deadlines. Keep concise. Null if nothing useful to add.
- For complete_task: only use this if you are confident the email refers to one of the open tasks. task_id must be an id from the open task list above. If you cannot confidently match, return unknown.
- If the email could create a new task AND complete an existing one, prefer add_task.
- Do not invent tasks. If the message is a question, conversational reply, or contains no actionable content, return unknown.
"""


def parse_email_for_task(
    subject: str,
    body: str,
    member_names_emails: list[tuple[str, str]],
    sender_tz: str = "UTC",
    open_tasks: list[dict] = None,
) -> dict:
    """
    Call Claude and return a parsed intent dict.
    open_tasks: list of dicts with keys id, title, notes — the group's current open tasks.
    Raises on API error, timeout, or unparseable JSON.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set")

    client = Anthropic(api_key=api_key)
    prompt = _build_prompt(subject, body, member_names_emails, sender_tz, open_tasks or [])

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
