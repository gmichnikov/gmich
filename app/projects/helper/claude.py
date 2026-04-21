"""
Claude integration for the Helper project.

Calls Claude with the email subject + body, group member names, and currently
open tasks, then returns a structured intent dict:

  add_task: title, due_date, assignee_email, notes, duplicate_of_task_id,
            already_completed (bool; true = record as done in one step, no duplicate check)
  complete_task: task_id (must match an open task)
  unknown

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
An authorized group member sent the email below. They may want to: (1) add something to track, (2) mark an **open** task above as done, or (3) **record something already finished** even when it was never on the open list (e.g. "I registered yesterday").

---
Subject: {subject}
Body: {body or '(empty)'}
---

Emails often have a **footer** after the real message: unsubscribe links, privacy policy, "powered by" branding, or a **physical address belonging to the email vendor** (e.g. SendGrid, Mailgun) for legal/compliance — not the school, venue, or place the user must go. The important details (event location, gym name, school name, times) are almost always in the **main body above that**. Do **not** treat footer-only addresses or boilerplate as the task location unless the main text clearly says to go there.

**How to pick an intent** (stop at the first that fits):
1. **complete_task** — The email clearly refers to finishing **one specific** task from the open list above. You are confident which `task_id` it is.
2. **add_task with already_completed: true** — The email describes work **already done** (receipt, past-tense confirmation, "I signed up") and you are **not** using step 1 because nothing on the open list matches, or the open list is empty.
3. **add_task with already_completed: false** — The user wants something **tracked for later** (reminder, forward, "don't forget") or a **new** item that is not yet done. Use this for duplicate detection (next section).
4. **unknown** — No actionable task content (questions, small talk, unclear).

If step 2 and 3 both seem possible, prefer **already_completed: true** when the main point is reporting past completed action; prefer **false** when the main point is a future to-do or forward.

**add_task JSON shape** (always include every key; `already_completed` is required):

Normal new or future task (`duplicate_of_task_id` only applies when `already_completed` is false):
{{
  "intent": "add_task",
  "already_completed": false,
  "duplicate_of_task_id": null,
  "title": "concise task title",
  "due_date": "YYYY-MM-DD or null",
  "assignee_email": "exact email from the member list above, or null if unclear/unspecified",
  "notes": "supplementary context or null"
}}

Same real item as an open task (only when `already_completed` is false — message is redundant with an open task):
{{
  "intent": "add_task",
  "already_completed": false,
  "duplicate_of_task_id": <integer id from the open task list>,
  "title": "short label or echo of existing task",
  "due_date": null,
  "assignee_email": null,
  "notes": null
}}

Record something already done when it was not matched as **complete_task** (step 1):
{{
  "intent": "add_task",
  "already_completed": true,
  "duplicate_of_task_id": null,
  "title": "short label for what was done",
  "due_date": "YYYY-MM-DD or null",
  "assignee_email": "exact email from the member list above, or null",
  "notes": "supplementary context or null"
}}

**complete_task** (only from step 1):
{{
  "intent": "complete_task",
  "task_id": <integer id from the open task list>
}}

**unknown**:
{{
  "intent": "unknown"
}}

Field rules:
- **already_completed**: boolean. If true, **duplicate_of_task_id must be null** (retrospective entries are never de-duplicated against open tasks).
- **duplicate_of_task_id** (when already_completed is false): null for a genuinely new task. Set to an open task's id only when the message is clearly **redundant** with that task (same real errand, bill, signup). If unsure, use null. If there are no open tasks, always null.
- **title**: Short and action-oriented for to-dos; for already_completed, label what was accomplished.
- **due_date**: YYYY-MM-DD or null. No times.
- **assignee_email**: Must exactly match a member email, or null. If the sender says "me" or "I", use null (the system defaults to the sender).
- **notes**: Extra detail from the **substantive** body (not vendor/footer). Null if nothing useful.

Other:
- If one email both finishes an open task **and** adds a distinct new item, prefer **add_task** (we only return one JSON object).
- Do not invent tasks. If the message is purely conversational, return unknown.
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
        max_tokens=448,
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
