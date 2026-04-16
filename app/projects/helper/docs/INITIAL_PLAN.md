# Helper — Email → Task Tracker (Project Spec)

## Overview

A **family / group** task tracker inside the existing Flask app. Authorized members email a **group-specific inbound address**; the app verifies Mailgun, resolves **which group** from the **recipient**, checks the **sender** is a member of that group, uses **Claude** to interpret the message, and creates tasks on the **shared list** for that group.

**v1 scope:** task creation + audit logging + logged-in UI to see groups and manage tasks.  
**Deferred past v1:** Google Calendar integration, confirmation emails, attachment processing.

---

## Core product decisions (agreed)

### Groups and membership

- Each **group** (family) has a **shared task list** in the database.
- **Site admin only** (existing app admin — same mechanism as other admin features) can:
  - **Create** a group
  - **Add members** to a group **by email**
- **Only users who already have accounts** can be added (email must match an existing `User`).
- **No group-level admin role for now** — only global site admin manages groups and membership.
- **Multiple memberships per user** are allowed in the schema (no “one group per user” constraint); in practice usage may be 0 or 1 group per person.
- Logged-in users see **groups they belong to** on the Helper project homepage (often 0 or 1).

**Group creation (resolved):**

- **At least one member** — a group cannot be created with zero members.
- **Admin must include themselves** — the creating admin’s email must appear in the member list (not auto-added silently). They are a member like anyone else.
- **Validation:** if **any** member email does not match an existing user, **the whole create fails** (no partial group, no DB row). Show which addresses failed. Simplest and avoids orphan or half-created state.

### Inbound email ↔ group (recipient-based routing)

- **Which group an email applies to is determined by the recipient address** (the inbound email), **not** by inferring from the sender alone.
- Each group stores its **inbound email** (or equivalent normalized form) in the database — **nothing hardcoded** in app code for a single global address.
- **Uniqueness:** two groups **cannot** share the same inbound address — enforce a **unique** constraint on the stored value (normalized for comparison).
- **Mailgun:** For each group address, an inbound route is configured in Mailgun so mail to that address is forwarded to the **same** shared webhook URL (see **Webhook URL** below). Adding a new group typically means a **new row in the DB** plus a **one-time Mailgun route** for that recipient.
- The webhook reads Mailgun’s **recipient** (and related fields) and looks up the matching **group**. The **sender** is then checked for **membership in that group** (not a flat global allowlist).

### Security (v1)

- **Mailgun signature verification** is **required in v1** — verify the webhook request before doing any work (not deferred to a later phase).
- Unauthorized or invalid requests: no task actions; still return **HTTP 200** where appropriate so Mailgun does not retry endlessly (see error handling).
- **Sender authorization:** Resolve Mailgun’s **sender** to a **`User`** by email. The sender must **exist as a user** and be a **member of that group**. If there is no matching user, or the user is not in the group, log and take no task action (and still 200 per policy below).

### Idempotency (resolved)

- Inbound mail may be **delivered or POSTed more than once** (retries, timeouts). To avoid duplicate tasks, persist a **dedupe key** per processed message and skip if seen again.
- **Primary key:** Parse **`Message-Id`** from Mailgun’s **`message-headers`** field (standard `Message-ID:` header). Normalize (e.g. strip angle brackets, consistent casing). This is the usual stable id across retries of the **same** message.
- **Fallback** (if `Message-Id` is missing or unparsable — uncommon): `sha256(f"{sender}|{recipient}|{timestamp}|{subject}")` using Mailgun’s `sender`, `recipient`, `timestamp`, and `subject` fields from the POST. Weaker than `Message-Id` but good enough for edge cases.
- Store the chosen key on the inbound log row; **unique constraint** on that key (**global** `message_id` is simplest when keys are universally unique).

### Timezone

- App users already have **time zones** on their profile.
- For parsing relative dates in natural language (e.g. “tomorrow”, “Friday”), use the **sending user’s** timezone (`User.time_zone`) when resolving the sender to a `User`.
- Optionally store **received** timestamps in UTC plus a **display-friendly local time** for the sender for audit logs (exact fields in migrations).

### Logging (first-class)

Logging is **important** and **project-specific** (Helper), not only generic hosting/platform logs.

- **Every inbound webhook POST gets a row** in the **inbound email log** — including failures (bad signature, unknown recipient, sender not allowed, duplicate idempotency, Claude errors, etc.). Use a **status** (and optional notes) on that row so support and debugging always have a record, not only “happy path” mail.
- **Spam / junk / forged POSTs:** For now, **still log them** (same table) so you can see what’s hitting the endpoint. Optional noise is acceptable; you can tighten retention or filtering later.
- **Separate tables** (recommended):
  - **Inbound email log** — one row per received POST: from, to/recipient, subject, body text, timestamps, processing status, idempotency key (no full raw POST in v1).
  - **Action / decision log** — rows for what the app **decided** and **did** (e.g. “created task X”, “rejected: not a member”, “unknown intent”, API errors). Linked to the inbound row.
  - **Tasks** — actual task tracker entities for the group.
- Rationale: one email can yield multiple structured actions or errors; mixing everything into one table makes queries and retention harder.

### Privacy (stored email content)

The audit log **stores the content of emails** (at least subject + body text you process) in your database. That is intentional for debugging and accountability. Treat it like other sensitive app data: **same access controls** as the rest of the site; **retention policy** can be decided later. This is not “extra tracking” — it’s the product’s **audit trail**.

### UX / operations

- **Fire and forget:** no confirmation emails to the sender in v1.
- **Attachments / images:** ignored in v1.

---

## Email entry point

- **Provider:** Mailgun (existing account).
- **Mechanism:** Mailgun Inbound Routes forward parsed payloads to the Flask app via **HTTP POST** to the shared webhook.
- **Per-group addresses** are configured in Mailgun **and** stored on the group record in the app (see above).

### Webhook URL and CSRF (resolved)

- **Path:** `POST /hooks/helper/mailgun` — **namespace under `helper`**, single shared URL for all group addresses.
- **CSRF:** Mailgun cannot send a Flask-WTF CSRF token. Register this route with **`@csrf.exempt`** (or equivalent), same pattern as other inbound webhooks.

### Configuration / secrets (resolved)

- Do **not** commit secrets. Use **environment variables** (or your existing app config pattern), e.g. **Mailgun** credentials used for **webhook signature verification**, and **Anthropic** API key for **Claude**. Exact names are an implementation detail.

---

## System components (v1)

### 1. Mailgun

- One **route per group inbound address** (or equivalent matching rule), all forwarding to the **same** webhook URL.
- Each new group with a new address requires **Mailgun configuration** in addition to the database row.

### 2. Flask webhook (`POST /hooks/helper/mailgun`)

**Suggested handler order** (avoids acting on bad input and makes logs consistent):

1. **Create inbound log row early** from the POST (so *every* request is recorded — you can update status as you go).
2. **Verify Mailgun signature** — if invalid, mark inbound row failed, return **200**, stop.
3. Compute **idempotency key** — if duplicate, mark skipped, return **200**, stop.
4. Parse **recipient** → load **group** (if none, log, return **200**, stop).
5. Parse **sender** → load **`User`**; check **group membership** (if no user or not a member, log, return **200**, stop).
6. Extract **subject** + **plain-text body** for Claude (see **Email text for Claude** below); attachments ignored.
7. Call **Claude**; on success parse JSON; create **task** when appropriate; append **action** log rows; return **200**.

- **Always return HTTP 200** for these “handled” outcomes so Mailgun does not retry (see error table).

#### Which Mailgun field to use as the “email body” for Claude

Mailgun’s inbound POST includes **several** body-related fields. In short:

- **`body-plain`** — full plain-text body (often includes quoted reply text below the new message).
- **`stripped-text`** (when present) — Mailgun’s version with much of the **quoted thread** removed, usually better for “what did the user just type?”

**Recommendation:** prefer **`stripped-text`** when it is non-empty; otherwise fall back to **`body-plain`**. Combine with **Subject** as you do today. (Exact field names are in Mailgun’s inbound parse documentation if they rename minor fields.)

### 3. Claude (Anthropic API)

- Input: subject + body (+ context such as group member names / allowed assignees so Claude can stay in bounds).
- Output: structured JSON, e.g. v1 intents such as **`add_task`** (or `add_todo`) and **`unknown`**.
- For **`add_task`:** task title, optional **due date** (stored as a **calendar date** — no time-of-day), optional assignee (name within family); if assignee omitted, default assignee = **sender** as already agreed. Parsing from natural language resolves relative phrases using the sender’s timezone into a **date**.
- **Assignee mismatch (resolved):** If Claude returns an assignee that **does not** match any member (after passing options in the prompt), **leave assignee unset** on the task (`NULL`) rather than guessing. We expect this to be rare if member options are passed to Claude clearly.
- **Claude / transport failures (resolved):** On **malformed JSON**, **API error**, or **timeout**, log to action log (and inbound status as needed), **no task created**, return **200**.
- Model: Claude Sonnet (latest) unless you standardize elsewhere.
- **`unknown`:** log and stop; no task.

### 4. Task tracker (shared per group)

- Backed by the **app database**, scoped to **group**.
- Fields (conceptual): title, optional **due date** (date only), **notes** (optional freeform text — users edit in the UI for discussion / extra detail), assignee, created by, created at, status, completed by, completed at — exact schema in migrations.
- **UI** for listing and managing tasks: part of Helper project; **layout and filters can evolve later** — no spec lock-in for v1.

### 5. Admin UI (site admin only)

- Create group: name, **inbound email** for that group, **member emails** (see **Group creation** above — ≥1 member, admin’s email listed, all must be existing users, atomic failure if any email invalid).
- Add members by email later (same rules: existing users only; admin-only).

---

## Supported actions (v1)

Examples (natural language → task on the group list):

| Example                                      | Intent     | Action                                      |
| -------------------------------------------- | ---------- | ------------------------------------------- |
| “Buy milk”                                   | `add_task` | Task assigned to sender                     |
| “Remind me to call John tomorrow”            | `add_task` | Task with due date; assignee = sender       |
| “Assign Sarah to pick up dry cleaning”       | `add_task` | Task with assignee if name matches; else assignee unset |

Calendar-related rows are **out of v1** (see deferred).

---

## Deferred (after v1)

- **Google Calendar** — OAuth, calendars table, `add_calendar_event` intent, etc.
- Mailgun-only improvements beyond agreed v1 signature verification (if any).
- Confirmation emails back to senders.
- Attachment / image processing.
- Extra action types (notes, reminders, etc.) as needed.
- **Group lifecycle & membership UX** — remove member, leave group, delete group, rename inbound address, etc. (not required for first ship.)

---

## Error handling (target behavior)

| Scenario                          | Behavior                                      |
| --------------------------------- | --------------------------------------------- |
| Invalid Mailgun signature         | Inbound log row (every POST), return 200 (no task) |
| Cannot resolve recipient to group | Inbound log row, return 200                               |
| Sender not a user or not in group | Inbound log row, return 200                               |
| Duplicate idempotency key         | Inbound log + skip, return 200                          |
| Claude returns `unknown`          | Log, return 200                  |
| Claude API error / timeout / bad JSON | Action log (+ inbound status), return 200, no task |
| Task insert fails                 | Log error, return 200                           |
| Attachments                       | Ignored in v1                                 |

Also log to **Helper’s tables** as above; hosting / platform logs remain useful for ops.

---

## Database tables (v1 sketch)

**Yes, it’s worth thinking this through before the first migration** — mostly so **unique keys**, **foreign keys**, and **nullable vs required** fields match the behaviors above (logging everything, recipient → group, idempotency, tasks linked to group + optional inbound).

This is a **starting point**; exact column types and enum strings get finalized when you write models/migrations. Table names follow a **`helper_`–style prefix** (same idea as other projects in this app).

### 1. `helper_group`

| Field | Notes |
| --- | --- |
| `id` | PK |
| `name` | Display name (e.g. family name) |
| `inbound_email` | **Unique.** Normalized form used to match Mailgun `recipient` |
| `created_at` | |
| `created_by_user_id` | Optional FK → `user` (admin who created the row) |

### 2. `helper_group_member`

| Field | Notes |
| --- | --- |
| `id` | PK |
| `group_id` | FK → `helper_group` |
| `user_id` | FK → `user` |
| `created_at` | |
| **Constraint** | **Unique (`group_id`, `user_id`)** |

### 3. `helper_inbound_email` (one row per webhook POST)

| Field | Notes |
| --- | --- |
| `id` | PK |
| `idempotency_key` | **Unique** (Message-Id or fallback hash). Computed as soon as the POST can be parsed so every row has a key |
| `recipient`, `sender_raw` | From Mailgun (as strings) |
| `sender_user_id` | Nullable FK → `user` if resolvable |
| `group_id` | Nullable FK → `helper_group` if `recipient` matched a group |
| `subject`, `body_text` | Text used for audit + Claude (per **stripped-text** / **body-plain** rule) |
| `status` | String/enum: e.g. `received` → `signature_invalid` \| `unknown_recipient` \| `duplicate` \| `sender_not_allowed` \| `processed` \| `error` … (exact set in code) |
| `signature_valid` | Optional boolean if useful for filtering |
| `mailgun_timestamp` | From Mailgun field if present |
| `created_at` / `updated_at` | So rows can be updated as the pipeline advances |

**Index ideas:** `group_id`, `status`, `created_at` (for admin/debug UIs).

### 4. `helper_action_log` (0+ rows per inbound email)

| Field | Notes |
| --- | --- |
| `id` | PK |
| `inbound_email_id` | FK → `helper_inbound_email` (required) |
| `action_type` | Short string, e.g. `task_created`, `duplicate_skipped`, `claude_error`, `unknown_intent`, `not_member` |
| `detail` | JSON or text — structured payload (task id created, error body, etc.) |
| `error_message` | Nullable |
| `created_at` | |

### 5. `helper_task`

| Field | Notes |
| --- | --- |
| `id` | PK |
| `group_id` | FK → `helper_group` |
| `title` | |
| `due_date` | Nullable **date** (no time component) |
| `notes` | Nullable **text** — freeform; **any group member** can view/edit in v1 for discussion or extra context (not threaded comments; a single shared field) |
| `assignee_user_id` | Nullable FK → `user` (unset if Claude assignee didn’t match) |
| `created_by_user_id` | FK → `user` (sender) |
| `status` | e.g. `open` / `complete` |
| `completed_by_user_id`, `completed_at` | Nullable |
| `source_inbound_email_id` | Nullable FK → `helper_inbound_email` (which email created this task) |
| `created_at` / `updated_at` | |

**Index ideas:** `group_id` + `status`, `created_at`.

### What you don’t need to lock now

- Exact **enum** spellings for `status` fields (as long as they’re consistent in code).
- **Threaded comments** vs one **`notes`** field — v1 is a **single editable text** column per task; a full comment history table can come later if needed.
- **Raw POST payload:** omitted in v1 (use `subject` / `body_text` / `sender` / `recipient` for audit). Add later only if debugging needs it.

When you run migrations, use **`flask db migrate` / `upgrade` yourself** per your project convention.

---

## Historical note

An earlier draft described a **single fixed inbound address**, calendar actions in v1, OAuth env vars per user, and signature verification as “future.” Those have been **superseded** by the decisions above (recipient-based groups, tasks-only v1, signature in v1, logging tables).
