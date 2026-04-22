"""
Claude integration for the Helper project.

Three-stage pipeline:
  1. route_email()       — classifies intent: complete_task / add_task / unknown
  2. run_complete_task_specialist() — given route=complete_task, resolves which open task_id
  3. run_add_task_specialist()      — given route=add_task, extracts all new-task fields

Each function raises ClaudeResponseError on API error, timeout, or unparseable JSON.
"""
import json
import logging
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from anthropic import Anthropic

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-haiku-4-5"


class ClaudeResponseError(ValueError):
    """
    Claude returned text we could not parse into a valid response dict.

    ``raw_response`` is set when the API succeeded but JSON/validation failed,
    so operators can inspect what the model returned.
    """

    def __init__(self, message: str, *, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


# ---------------------------------------------------------------------------
# Shared parsing utilities
# ---------------------------------------------------------------------------

def _log_malformed_claude_response(reason: str, text: str) -> None:
    max_len = 8000
    if len(text) > max_len:
        snippet = text[:max_len] + "\n... [truncated]"
    else:
        snippet = text
    logger.error("Malformed Claude response (%s). Full raw:\n%s", reason, snippet)


def _parse_json_response(raw: str) -> dict:
    """
    Parse the first JSON object from Claude's reply.

    The model sometimes outputs valid JSON followed by extra text or a second
    object; json.loads then fails. We use raw_decode to grab just the first object.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()

    start = text.find("{")
    if start == -1:
        _log_malformed_claude_response("no JSON object (no '{' found)", text)
        raise ValueError("No JSON object found in Claude response")

    decoder = json.JSONDecoder()
    try:
        result, end = decoder.raw_decode(text, start)
    except json.JSONDecodeError as e:
        _log_malformed_claude_response(f"JSON decode error: {e}", text)
        raise ValueError(f"Invalid JSON in Claude response: {e}") from e

    trailing = text[end:].strip()
    if trailing:
        logger.warning(
            "Claude response had %d extra characters after JSON (ignored): %s",
            len(trailing),
            trailing[:400],
        )

    if not isinstance(result, dict):
        _log_malformed_claude_response(
            f"JSON root must be an object, got {type(result).__name__}", text
        )
        raise ValueError(f"Claude JSON root must be an object, got {type(result).__name__}")
    return result


def _call_claude(prompt: str, max_tokens: int = 512) -> str:
    """Make a single Claude API call and return the raw text response."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set")
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    logger.info("Claude raw response: %s", raw)
    return raw


def _today_for_tz(sender_tz: str) -> date:
    try:
        tz = ZoneInfo(sender_tz)
        return datetime.now(tz).date()
    except Exception:
        return date.today()


def _members_block(member_names_emails: list[tuple[str, str]]) -> str:
    return "\n".join(f"- {name} ({email})" for name, email in member_names_emails)


def _open_tasks_block(open_tasks: list[dict]) -> str:
    if not open_tasks:
        return "There are no open tasks in this group currently."
    lines = "\n".join(
        f"- [id={t['id']}] \"{t['title']}\""
        + (f" — {t['notes']}" if t.get("notes") else "")
        for t in open_tasks
    )
    return f"The following tasks are currently open in this group:\n{lines}"


# ---------------------------------------------------------------------------
# Stage 1: Router
# ---------------------------------------------------------------------------

def _build_router_prompt(
    subject: str,
    body: str,
    member_names_emails: list[tuple[str, str]],
    sender_tz: str,
    open_tasks: list[dict],
) -> str:
    today = _today_for_tz(sender_tz)
    members = _members_block(member_names_emails)
    tasks = _open_tasks_block(open_tasks)

    return f"""You are a routing assistant for a family task tracker. Your only job is to classify the intent of an inbound email into one of three categories. Do not extract fields — just classify.

Today's date is {today.isoformat()} (sender's local date).

The group members are:
{members}

{tasks}

---
Subject: {subject}
Body: {body or '(empty)'}
---

Classify this email into exactly one of:
- **complete_task** — The email is clearly about finishing a specific task that is already on the open list above.
- **add_task** — The email is adding something new to track, reporting something already done, or forwarding a reminder for a future to-do. Use this even if there's a possible duplicate.
- **unknown** — No actionable task content (questions, small talk, completely unclear).

Return only a JSON object:
{{"route": "complete_task"}}
or
{{"route": "add_task"}}
or
{{"route": "unknown"}}
"""


def route_email(
    subject: str,
    body: str,
    member_names_emails: list[tuple[str, str]],
    sender_tz: str = "UTC",
    open_tasks: list[dict] = None,
) -> dict:
    """
    Stage 1: Classify the email intent.
    Returns dict with key 'route': 'complete_task' | 'add_task' | 'unknown'.
    Raises ClaudeResponseError on API error or unparseable response.
    """
    prompt = _build_router_prompt(
        subject, body, member_names_emails, sender_tz, open_tasks or []
    )
    raw = _call_claude(prompt, max_tokens=64)
    try:
        result = _parse_json_response(raw)
    except ValueError as e:
        raise ClaudeResponseError(str(e), raw_response=raw) from e

    route = result.get("route", "")
    if route not in ("complete_task", "add_task", "unknown"):
        _log_malformed_claude_response(f"unexpected route value: {route!r}", raw)
        raise ClaudeResponseError(
            f"Router returned unexpected route: {route!r}", raw_response=raw
        )

    return result


# ---------------------------------------------------------------------------
# Stage 2a: Complete-task specialist
# ---------------------------------------------------------------------------

def _build_complete_task_prompt(
    subject: str,
    body: str,
    member_names_emails: list[tuple[str, str]],
    sender_tz: str,
    open_tasks: list[dict],
) -> str:
    today = _today_for_tz(sender_tz)
    members = _members_block(member_names_emails)
    tasks = _open_tasks_block(open_tasks)

    return f"""You are a task-completion assistant for a family task tracker. An inbound email has already been classified as a request to complete an open task. Your job is to identify exactly which open task the email refers to.

Today's date is {today.isoformat()}.

The group members are:
{members}

{tasks}

---
Subject: {subject}
Body: {body or '(empty)'}
---

Identify which open task the sender is marking as done. Return the task_id of the matching task.

If you can confidently match the email to one specific open task, return:
{{"task_id": <integer id from the open task list>}}

If you cannot confidently identify which task is meant, return:
{{"task_id": null}}
"""


def run_complete_task_specialist(
    subject: str,
    body: str,
    member_names_emails: list[tuple[str, str]],
    sender_tz: str = "UTC",
    open_tasks: list[dict] = None,
) -> dict:
    """
    Stage 2a: Given route=complete_task, resolve which open task to complete.
    Returns dict with key 'task_id': int or None.
    Raises ClaudeResponseError on API error or unparseable response.
    """
    prompt = _build_complete_task_prompt(
        subject, body, member_names_emails, sender_tz, open_tasks or []
    )
    raw = _call_claude(prompt, max_tokens=64)
    try:
        result = _parse_json_response(raw)
    except ValueError as e:
        raise ClaudeResponseError(str(e), raw_response=raw) from e

    if "task_id" not in result:
        _log_malformed_claude_response("missing 'task_id' key", raw)
        raise ClaudeResponseError(
            "Complete-task specialist response missing 'task_id'", raw_response=raw
        )

    return result


# ---------------------------------------------------------------------------
# Stage 2b: Add-task specialist
# ---------------------------------------------------------------------------

def _build_add_task_prompt(
    subject: str,
    body: str,
    member_names_emails: list[tuple[str, str]],
    sender_tz: str,
    open_tasks: list[dict],
) -> str:
    today = _today_for_tz(sender_tz)
    members = _members_block(member_names_emails)
    tasks = _open_tasks_block(open_tasks)

    return f"""You are a task-extraction assistant for a family task tracker. An inbound email has already been classified as adding a task (new, forwarded, or reporting something already done). Your job is to extract all relevant fields.

Today's date is {today.isoformat()} (use this to resolve relative dates like "tomorrow" or "Friday").
The sender's timezone is {sender_tz} (use this to interpret relative reminder times like "Thursday at 3pm").

The group members are:
{members}

{tasks}

---
Subject: {subject}
Body: {body or '(empty)'}
---

Emails often have a footer after the real message: unsubscribe links, privacy policy, "powered by" branding, or a physical address belonging to the email vendor — not the school, venue, or place the user must go. The important details are almost always in the main body. Do not treat footer-only addresses or boilerplate as the task location.

Determine:
1. **already_completed**: true if the email describes work already done (receipt, past-tense confirmation, "I signed up yesterday"). False if it's something to track for the future.
2. **duplicate_of_task_id**: If already_completed is false and the email is clearly redundant with an existing open task (same real errand), set this to that task's id. Otherwise null. If already_completed is true, always null.
3. All task fields below.

Return a JSON object with all of these keys:

{{
  "already_completed": true or false,
  "duplicate_of_task_id": null or <integer id from open task list>,
  "title": "concise task title or label for what was done",
  "due_date": "YYYY-MM-DD or null",
  "assignee_email": "exact email from the member list, or null if unclear/unspecified",
  "notes": "supplementary context from the main body, or null",
  "reminder_at": "ISO-8601 datetime string with timezone offset (e.g. 2026-04-25T15:00:00-04:00) if the sender explicitly requests a reminder at a specific time, otherwise null"
}}

Field rules:
- **already_completed**: boolean, required.
- **duplicate_of_task_id**: null unless clearly redundant with an open task and already_completed is false.
- **title**: short and action-oriented for to-dos; for already_completed, label what was accomplished.
- **due_date**: YYYY-MM-DD or null. Date only, no times.
- **assignee_email**: must exactly match a member email, or null. If the sender says "me" or "I", use null (the system defaults to the sender).
- **notes**: extra detail from the substantive body only. Null if nothing useful.
- **reminder_at**: only set if the sender explicitly asks to be reminded at a specific time (e.g. "remind me Thursday at 3pm", "ping me next Friday morning"). Use the sender's timezone ({sender_tz}) to interpret relative times, and include the timezone offset in the ISO string. Null if no explicit reminder time is mentioned.
"""


def run_add_task_specialist(
    subject: str,
    body: str,
    member_names_emails: list[tuple[str, str]],
    sender_tz: str = "UTC",
    open_tasks: list[dict] = None,
) -> dict:
    """
    Stage 2b: Given route=add_task, extract all new-task fields.
    Returns dict with keys: already_completed, duplicate_of_task_id, title,
    due_date, assignee_email, notes, reminder_at.
    Raises ClaudeResponseError on API error or unparseable response.
    """
    prompt = _build_add_task_prompt(
        subject, body, member_names_emails, sender_tz, open_tasks or []
    )
    raw = _call_claude(prompt, max_tokens=512)
    try:
        result = _parse_json_response(raw)
    except ValueError as e:
        raise ClaudeResponseError(str(e), raw_response=raw) from e

    if "title" not in result:
        _log_malformed_claude_response("missing 'title' key", raw)
        raise ClaudeResponseError(
            "Add-task specialist response missing 'title'", raw_response=raw
        )

    return result
