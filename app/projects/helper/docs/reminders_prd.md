# Helper — Task reminders (PRD)

## Goal

Send **one email reminder per open task** at a scheduled time so assignees (or the creator when unassigned) don’t miss due dates. Reminders are **Helper-only** — no coupling to the separate Reminders project in this repo; this may be split out later.

## Non-goals (v1)

- Digest emails, unsubscribe flows, or preference centers
- Push / SMS / in-app notifications
- Reminders without a **due date**

---

## Time & timezone rules

**Who defines “local”?** Use this order:

1. **Assignee** (if `assignee_user_id` is set — use that user’s profile timezone).
2. Otherwise **creator** (`created_by_user_id`).

**Default reminder instant (stored as UTC):**

- **Calendar day before** the task’s **due date**, at **10:00** in that user’s timezone.
- Example: due date `2026-04-20` → reminder fires on **2026-04-19 at 10:00** local, not “24 hours before midnight.”

**Edge cases:**

- If **due date is today** (in assignee-or-creator local calendar terms when evaluating at save time): **do not set** a default `reminder_at` — it stays empty / cleared by the default rule. No special UI copy is required; it’s simply “no scheduled reminder.” The user may still **manually** set `reminder_at` to any **future** time if they want a reminder anyway.
- If **due date is in the past**: treat as invalid for default reminders — **no default** (clear or leave `reminder_at` null per the same rules as other invalid defaults).

**Display (Helper UI):** All datetimes shown to users use the **current viewer’s** timezone (same as the rest of Helper). Users should **never** need to think about UTC in the UI. Storage remains **UTC** under the hood.

**After saving a reminder**, show a single readable preview line, e.g.  
`Reminder: Mon Apr 18, 10:00 AM · email to Alex`  
so people see **when** and **who** at a glance (recipient name = assignee if set, else creator).

---

## Data model

| Field | Type | Purpose |
|--------|------|--------|
| `reminder_at` | UTC datetime, nullable | When the reminder should be sent. `NULL` = no reminder scheduled. |
| `reminder_sent_at` | UTC datetime, nullable | When the reminder email was successfully sent. `NULL` = not sent yet. |

**Scheduler query (conceptual):** open tasks where `reminder_at <= now()`, `reminder_sent_at IS NULL`, `status = open`, and still eligible (assignee/creator resolvable, etc.).

**After a reminder is sent:** set `reminder_sent_at` (and optionally log an action — see below).

**If the user edits `reminder_at` to a new future time *after* a reminder was already sent:**  
Clear **`reminder_sent_at`** (unset) so the new scheduled time can fire once. Do **not** add a separate “customized” boolean; behavior is fully determined by due date changes (see Defaults) and explicit edits to `reminder_at`.

---

## Defaults when due date changes

- **No extra boolean** (“user customized”) in v1.
- Whenever **`due_date`** changes, **recompute `reminder_at`** from the rules above (calendar day before at 10:00 local for assignee-or-creator timezone).
- The **local time of day** for the default stays **10:00**; only the **date** shifts with the new due date.
- If the new due date implies **no reminder** (e.g. due today / no due date), set `reminder_at` to `NULL` and clear `reminder_sent_at` if appropriate.

**Assignee changes:** Do **not** recompute `reminder_at` when only `assignee_user_id` changes — too easy to confuse users. Timezone for defaults remains defined by assignee-or-creator order at the time the **default** is computed (e.g. on due date change or task create); changing who is assigned does not shift an existing scheduled instant.

---

## Editing `reminder_at`

- User may set/adjust the reminder **only to a time in the future** (validation on save).
- Clearing the reminder = set `reminder_at` to `NULL` (and clear `reminder_sent_at` if we want a clean slate — product decision: clearing should remove pending send state).

---

## When the task is completed

Do **not** send a reminder for a completed task.

- **Primary:** When `status` becomes **complete**, clear **`reminder_at`** and **`reminder_sent_at`** so nothing pending remains.
- **Safety net:** The reminder sender / job should still only process tasks with **`status = open`** (so a race or missed update cannot email after completion).

Either layer alone could work; doing **both** is simple and robust.

---

## Delivery

- **Channel:** Email only (existing Mailgun path).
- **Recipient:** **Assignee** if set; otherwise **creator** (evaluated at **send time**, so if assignee changed after the reminder was scheduled, the current assignee or creator receives it).
- **Subject:** Include **due date** + **short task title** so inbox triage works without opening the mail (same spirit as other Helper notification subjects).
- **Body:** Include due date, title, and link(s) to task / group — enough to act from the message alone.

---

## Job / infrastructure

- **Heroku Scheduler** (or equivalent) for v1 — **no HTTP endpoint required** for sending reminders; the scheduler invokes a **one-shot CLI command** that runs inside the same dyno environment as the web app (DB, env vars, Mailgun).

### Heroku Scheduler + Flask CLI

- Implement a **single Flask CLI subcommand** on the existing Helper group (e.g. `flask helper send-reminders` — exact name chosen at implementation time in `app/projects/helper/commands.py`).
- The command should: load app context, query due rows, send emails, update `reminder_sent_at` / logs, exit **0** on success (non-zero optional on fatal errors for Scheduler visibility).
- In **Heroku Dashboard → Scheduler**, add a job that runs that command on the desired interval, for example:
  - **Run command:** `flask helper send-reminders` (or the final command name)
  - **Dyno size:** same as web or a **one-off** / **scheduler** dyno type per your setup
- **Frequency:** Hourly vs every 10 minutes **does not materially change the implementation** — only how tight the delivery window is around `reminder_at`. Start with whatever Heroku allows; tune later.

### Reliability

- **Idempotency:** Use `reminder_sent_at` + transactional update so the same task isn’t emailed twice under concurrent workers.
- **Retries:** If send fails, leave `reminder_sent_at` null so a later run retries; optional cap on attempts can be a follow-up.
- **Optional later:** Batch or rate-limit sends per run if Mailgun limits become an issue (not required for v1).

---

## Logging

- Log reminder lifecycle as **actions on the task** (e.g. `reminder_sent`, `reminder_failed` with detail), analogous to existing Helper action logging patterns — so admins and debugging can see what happened per task.

---

## Explicit exclusions

- **No due date** → `reminder_at` stays `NULL`; no reminder.
- **No digest** and **no unsubscribe** in v1.
- **No integration** with the separate **Reminders** app/project — separate codepaths and tables within Helper unless/until you intentionally merge or extract.

---

## Migration / existing data

- Add the new columns via migration as usual.
- **No backfill** of `reminder_at` for old rows; leave null unless updated manually or when the user next touches due date / flows that apply defaults.

---

## Feature backlog (not v1)

- **Default reminder time** (currently fixed at **10:00** local) as a **user** or **group** preference.

---

## Summary

Single scheduled instant per task (`reminder_at`), send tracking (`reminder_sent_at`), default = **day before due at 10:00** in assignee-or-creator TZ, **no reminder if due today or no due date**, assignee-or-creator email only, **UI preview line** after save, **email subject includes due date + short title**, **clear reminder fields on complete** + **open-only** in the job, **Heroku Scheduler → `flask helper send-reminders`** (exact CLI name TBD), idempotent sends + actions logged on the task, **decoupled from the Reminders project**.
