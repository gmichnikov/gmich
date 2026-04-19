# Helper — Detailed Implementation Plan

## How to use this document

- **[INITIAL_PLAN.md](./INITIAL_PLAN.md)** defines **what** we’re building (behavior, security, schema). This file defines **how to build it in order** and **what to verify** at each step.
- **Phases 1–6** are **delivery Milestones:** complete one phase, run its checks, then move on.
- The section **[Canonical webhook pipeline](#canonical-webhook-pipeline-initial_plan-aligned)** is the **detailed handler recipe** (especially for Mailgun). **Phase numbers inside that section** (Phase 2 vs Phase 5) match this doc’s milestones—they are **not** a second numbering scheme inside a single release.

**Build priority:** **Email → verified webhook → persisted inbound rows** first; **Claude → tasks → UI** once that’s trustworthy.

**Migrations:** You run `flask db migrate` and `flask db upgrade` yourself.

---

## At a glance: milestones

| Phase | Deliverable | Depends on |
| --- | --- | --- |
| **1** | SQLAlchemy models + migration for all five `helper_*` tables | — |
| **2** | `POST /hooks/...` webhook: Mailgun verify, idempotency, inbound + action logging, **no** Claude/tasks | Phase 1 |
| **3** | **Site-admin** UI: create group + members (atomic rules from INITIAL_PLAN) | Phase 1 |
| **4** | **Member** Helper UI: list groups you’re in, empty state | Phase 1, 3 (or seed data) |
| **5** | Claude → `helper_task` + action log on **authorized** inbound mail | Phase 1–3, 2 |
| **6** | Task list, complete, edit **notes** (group-scoped) | Phase 5 |

**Typical path:** **1 → 2** proves the pipe; **3** lets you configure groups without SQL; **3 + 2** enables realistic Mailgun tests; **5–6** finish the product loop.

---

## Traceability: INITIAL_PLAN → milestones

| Topic in INITIAL_PLAN | Where it is built |
| --- | --- |
| Groups, shared list, admin-only create/add | Phase **3** (models in **1**) |
| Recipient → group, unique `inbound_email` | **1**, **2**, **3** |
| Mailgun signature verification | **2**, env vars |
| Sender → `User` + membership; “wrong person” visible | **2** |
| Idempotency key | Column in **1**, logic in **2** |
| Inbound + action logging | **2**, **5** |
| Body: `stripped-text` / `body-plain` | Store in **2**; Claude input in **5** |
| Timezone → `due_date` as **date** only | **5** |
| Claude intents + assignee rules | **5** |
| Tasks + **notes** | **1**, **5**, **6** |
| Fire-and-forget; no attachments | **2**, **5**; defer [below](#explicitly-deferred-from-initial_plan) |
| Webhook URL + `@csrf.exempt` | **2**, [App integration](#app-integration-registry-blueprints) |
| Error table (HTTP **200** + log) | [Webhook pipeline](#canonical-webhook-pipeline-initial_plan-aligned), **2** & **5** |
| Privacy (email content in DB) | [Privacy and access control](#privacy-and-access-control) |
| All DB tables | **1** |
| Deferred (Calendar, …) | [Explicitly deferred](#explicitly-deferred-from-initial_plan) |

---

## Prerequisites (before Phase 1)

- [x] **Public HTTPS URL** (prod or **ngrok** for dev) — Mailgun must reach your webhook.
- [x] **Mailgun** account; domain/receiving setup when you send real mail ([INITIAL_PLAN — system components](./INITIAL_PLAN.md#system-components-v1)).
- [x] **Anthropic API key** — only when you start **Phase 5**.
- [x] App already has **`DATABASE_URL`**, **Flask-Login**, **`User.time_zone`**, **`User.is_admin`**.

---

## Environment variables

| When | Variable purpose |
| --- | --- |
| Before / during **Phase 2** | **Mailgun** — secrets used to **verify webhook signatures** (see Mailgun docs for the exact signing algorithm and env names). |
| **Phase 5** | **Anthropic** — API key for Claude. |

Load via **`config.py` / `.env`**; never commit secrets.

---

## App integration (registry, blueprints)

Do this as you touch each area (mostly **Phases 1–4**):

| Area | Action |
| --- | --- |
| **`app/__init__.py`** | Import Helper models; register **Helper** blueprint with `url_prefix='/helper'` if not already. |
| **`app/projects/registry.py`** | **helper** entry: `auth_required: True`, URL `/helper`, etc. |
| **Member routes** | `@login_required`; optional **`log_project_visit('helper', …)`**. |
| **Webhook** | Register **`POST /hooks/helper/mailgun`** (or the path in INITIAL_PLAN) **outside** the member-only prefix if needed. Use **`@csrf.exempt`** on that view only. |

The webhook URL must be the **same** one configured in Mailgun Inbound Routes.

---

## High-level dependency graph

```mermaid
flowchart LR
  P1[Phase 1 DB models]
  P2[Phase 2 Webhook plus inbound log]
  P3[Phase 3 Admin group]
  P4[Phase 4 Member Helper UI shell]
  P5[Phase 5 Claude and tasks]
  P6[Phase 6 Task UI]
  P1 --> P2
  P1 --> P3
  P2 --> P5
  P3 --> P4
  P3 --> P5
  P5 --> P6
```

- **Phase 2** can be tested **before** Phase 3 (e.g. bad signature, unknown `recipient`).
- For **real** “this inbox + I’m a member” tests, finish **Phase 3** or **seed** `helper_group` / `helper_group_member` in SQL.

---

## Canonical webhook pipeline (INITIAL_PLAN-aligned)

INITIAL_PLAN describes one linear story including Claude. Here we split that story into:

- **Pipeline A — inbound only** (implemented in **Milestone Phase 2** below): persistence and rules **without** LLM or tasks.
- **Pipeline B — Claude + tasks** (implemented in **Milestone Phase 5** below): runs only after inbound pipeline says the sender is an allowed member.

**Important — subject/body on failure paths:** For **`unknown_recipient`**, **`sender_not_allowed`**, etc., the inbound row must still store **subject** and **body_text** for audit (INITIAL_PLAN “wrong person” visibility). Parse **subject** and body (`stripped-text`, else `body-plain`) **from the POST early** and save them on the row **before** you return on those branches—not only on the happy path.

### Pipeline A — inbound only (Milestone Phase 2)

1. **Parse** Mailgun **form** fields: `recipient`, `sender`, `subject`, `stripped-text`, `body-plain`, `message-headers`, `timestamp`, …
2. **Compute `idempotency_key`:** `Message-Id` from `message-headers` (normalized), or **SHA256** of `sender|recipient|timestamp|subject` per INITIAL_PLAN.
3. **Duplicate:** If a row with this key **already exists** → set/update status **`duplicate`**, write **`helper_action_log`**, return **200**, **stop** (Phase 5 must not create a second task either).
4. **Insert** a new **`helper_inbound_email`** row with parsed fields, **`idempotency_key`**, initial **`status`** (e.g. `received`), **`mailgun_timestamp`** if present, and **subject/body_text** as parsed (see note above).
5. **Verify Mailgun signature.** Invalid → **`signature_invalid`**, **`helper_action_log`**, **200**, **stop**.
6. **Resolve `recipient`** (normalized) → **`helper_group`**. None → **`unknown_recipient`**, action log, **200**, **stop** (row already has subject/body).
7. **Resolve `sender`** → **`User`**; check **`helper_group_member`**. Not a user or not in group → **`sender_not_allowed`** (optionally two statuses: unknown user vs not member), action log, **200**, **stop** (row still has audit text).
8. **Check for empty content:** If both `subject` and `body_text` are empty (or only whitespace), set status **`empty_content`**, write **`helper_action_log`**, return **200**, **stop** (saves Claude costs and prevents hallucinations).
9. If you reached here, **member is OK** and content exists for Pipeline A: ensure **`group_id`**, **`sender_user_id`**, **subject**, **`body_text`** are set; status e.g. **`pending_llm`** — **still no Claude call** until Milestone Phase 5.

### Pipeline B — Claude + tasks (Milestone Phase 5)

10. Build the **Claude** prompt: subject + body + **member names / assignee options** ([INITIAL_PLAN — Claude](./INITIAL_PLAN.md#3-claude-anthropic-api)).
11. Call Claude → expect **JSON**; intents **`add_task`** / **`unknown`**.
12. **`add_task`:** title; optional **due_date** as **date** using **`User.time_zone`**; assignee or default to sender; mismatch → **`assignee_user_id` NULL**.
13. Insert **`helper_task`** (`source_inbound_email_id`, **`notes`** NULL unless you copy from email later).
14. **`helper_action_log`** for success or for **`unknown_intent`**, **`claude_error`**, etc. Failures → **no task**, **200**.

For every handled outcome above, return **HTTP 200** when appropriate so Mailgun does not hammer retries ([error table](./INITIAL_PLAN.md#error-handling-target-behavior)).

---

## Phase 1 — Database models and first migration ✅

**Covers:** [Database tables](./INITIAL_PLAN.md#database-tables-v1-sketch).

**Goal:** All five tables in SQLAlchemy + one Alembic migration.

**Work**

- [x] Add **`app/projects/helper/models.py`** with models mapping to **`helper_group`**, **`helper_group_member`**, **`helper_inbound_email`**, **`helper_action_log`**, **`helper_task`**.
- [x] **Uniques:** `inbound_email` on group; **`(group_id, user_id)`** on membership; **`idempotency_key`** on inbound.
- [x] **Types:** **`due_date`** = **Date** (not datetime); **`notes`** = Text on task; optional **`created_by_user_id`** on group; **`signature_valid`**, **`mailgun_timestamp`**, timestamps per INITIAL_PLAN.
- [x] **Indexes** on inbound (`group_id`, `status`, `created_at`) and tasks as in INITIAL_PLAN.
- [x] Import models in **`app/__init__.py`**.

**Manual Testing 1.1:**
- [x] Run `flask db migrate -m "helper tables"`
- [x] Review migration file — check columns, nullability, uniques, indexes
- [x] Run `flask db upgrade`
- [x] Verify all five tables exist in database with correct schema

---

## Phase 2 — Mailgun webhook + inbound audit ✅

**Covers:** [Email entry](./INITIAL_PLAN.md#email-entry-point), [webhook §2](./INITIAL_PLAN.md#system-components-v1), [Security](./INITIAL_PLAN.md#security-v1), [Logging](./INITIAL_PLAN.md#logging-first-class), [Idempotency](./INITIAL_PLAN.md#idempotency-resolved).

**Goal:** Implement **[Pipeline A — inbound only](#pipeline-a--inbound-only-milestone-phase-2)**: verify signature, log everything, **no** Claude and **no** `helper_task` rows.

**Work:**
- [x] Add **Mailgun** secrets to env for **webhook signature verification**.
- [x] Implement `POST /hooks/helper/mailgun` with `@csrf.exempt`.
- [x] Parse Mailgun form fields.
- [x] Compute `idempotency_key`.
- [x] Check for duplicate key -> 200.
- [x] Insert `helper_inbound_email`.
- [x] Verify signature. Invalid -> 200.
- [x] Resolve `recipient` to `helper_group`. None -> 200.
- [x] Resolve `sender` to `User` and check `helper_group_member`. Invalid -> 200.
- [x] Check for empty subject and body -> 200.
- [x] Update `helper_inbound_email` status and insert `helper_action_log` along the way.

**Ops:** Mailgun Inbound Route → `https://<your-host>/hooks/helper/mailgun` (or tunnel).

**Manual Testing 2.1:**
- [x] Send POST with bad signature → verify row + status `signature_invalid`, **200**.
- [x] Send POST with unknown `recipient` → verify row + status `unknown_recipient`, **200**.
- [x] Send POST to known group, sender **not** allowed → verify row **with** subject/body visible, status `sender_not_allowed`, **200**.
- [x] Send POST with duplicate idempotency key → verify **200**, no duplicate processing, status `duplicate`.
- [x] Send POST with empty subject and body -> verify **200**, status `empty_content`.
- [x] Send POST for normal handled case -> verify **200**, status e.g. `pending_llm`.

---

## Phase 3 — Admin UI: create group + members ✅

**Covers:** [Admin UI](./INITIAL_PLAN.md#5-admin-ui-site-admin-only), [Group creation](./INITIAL_PLAN.md#group-creation-resolved).

**Goal:** **`admin_required`** only. One transaction: **name**, **unique inbound_email**, **≥1 member**, **every email = existing User** — else rollback and show which emails failed.

**Work:**
- [x] Add admin route `GET /admin/helper/groups/new` and `POST /admin/helper/groups/create`.
- [x] Create template for group creation.
- [x] Implement validation: ≥1 member, all emails match existing `User`.
- [x] Set **`created_by_user_id`** on the group.
- [x] Add admin route for adding members to existing groups.

**Ops reminder:** New `inbound_email` usually needs a **new Mailgun route** to the same webhook URL.

**Manual Testing 3.1:**
- [x] Try creating group with invalid email → verify transaction rolls back, **no** partial rows, error shown.
- [x] Create group successfully → verify stored `inbound_email` is normalized correctly.

---

## Phase 4 — Member Helper UI (shell) ✅

**Covers:** [Overview / groups](./INITIAL_PLAN.md#overview).

**Goal:** **`@login_required`**. Show groups where **`current_user`** is a **member**. Empty state: explain an **admin** must add them.

**Work:**
- [x] Add `GET /helper/` route.
- [x] Create `templates/helper/index.html`.
- [x] Templates use **`helper-` CSS prefix** (avoid collisions with other projects).
- [x] Add to `app/projects/registry.py`.

**Manual Testing 4.1:**
- [x] Log in as member of a group → verify group(s) listed.
- [x] Log in as non-member → verify empty state explaining admin must add them.

---

## Phase 5 — Claude + tasks (email path) ✅

**Covers:** [Claude](./INITIAL_PLAN.md#3-claude-anthropic-api), [Tasks](./INITIAL_PLAN.md#4-task-tracker-shared-per-group), [Supported actions](./INITIAL_PLAN.md#supported-actions-v1), [Timezone](./INITIAL_PLAN.md#timezone).

**Goal:** Implement **[Pipeline B — Claude + tasks](#pipeline-b--claude--tasks-milestone-phase-5)** only when inbound mail has passed Pipeline A as an **authorized member**.

**Work:**
- [x] Add Anthropic API key to env.
- [x] Build Claude prompt with subject + body + member names / assignee options.
- [x] Parse Claude JSON response for intents `add_task` / `unknown`.
- [x] Handle `add_task`: title, `due_date` (convert using `User.time_zone`), assignee matching.
- [x] Insert `helper_task` and `helper_action_log`.
- [x] Handle errors (API, bad JSON, `unknown` intent) gracefully -> log, **no** task, return 200.
- [x] Strip markdown code fences from Claude response before JSON parsing (Claude sometimes wraps output in ```json blocks).

**Manual Testing 5.1:**
- [x] Send valid "Buy milk" email -> verify task created, assigned to sender.
- [x] Send valid email with due date -> verify task created, due date calculated correctly based on sender timezone.
- [x] Send email with `unknown` intent -> verify action logged, no task created, **200**.

---

## Phase 6 — Task UI ✅

**Covers:** [Task tracker](./INITIAL_PLAN.md#4-task-tracker-shared-per-group), [`helper_task`](./INITIAL_PLAN.md#5-helper_task).

**Goal:** Members **list**, **complete**, and **delete** tasks (soft or hard delete) and edit **`notes`**; **authorize** by **`group_id`** membership.

**Work:**
- [x] Add route to view tasks for a group `GET /helper/group/<id>`.
- [x] Add route to toggle task completion `POST /helper/task/<id>/complete`.
- [x] Add route to reopen a completed task `POST /helper/task/<id>/reopen`.
- [x] Add route to delete task `POST /helper/task/<id>/delete`.
- [x] Add route to edit notes `POST /helper/task/<id>/notes`.
- [x] Update templates to display and interact with tasks.
- [x] Index page shows open tasks inline per group.

**Manual Testing 6.1:**
- [x] Two members in one group -> verify both see that group's tasks.
- [x] Complete a task -> verify `completed_by_user_id` and `completed_at` updated.
- [x] Delete a task -> verify task removed from list.
- [x] Edit notes -> verify notes updated.

---

## Admin log viewers ✅

**Site-admin-only** read-only views supporting [logging](./INITIAL_PLAN.md#logging-first-class) and [privacy](./INITIAL_PLAN.md#privacy-stored-email-content) expectations.

- [x] `/admin/helper` — hub page linking to all Helper admin areas; linked from Helper homepage (admins only) and the Admin nav dropdown.
- [x] `/admin/helper/inbound-log` — paginated table of all `helper_inbound_email` rows with color-coded status, sender, recipient, subject, signature validity.
- [x] `/admin/helper/action-log` — paginated table of all `helper_action_log` rows with color-coded action type, detail JSON, error message.

---

## Privacy and access control

See [INITIAL_PLAN — Privacy](./INITIAL_PLAN.md#privacy-stored-email-content). **Inbound subject/body** are sensitive: restrict who can query them (e.g. admin-only global list; members never see other groups’ mail unless you explicitly allow).

---

## Explicitly deferred (from INITIAL_PLAN)

Per [Deferred](./INITIAL_PLAN.md#deferred-after-v1) and [not locked](./INITIAL_PLAN.md#what-you-dont-need-to-lock-now):

- Google Calendar, confirmation email, attachment processing, group delete/rename/remove member, threaded comments, **`raw_payload`**, rate limits / job queues — unless you pull a item forward.

**Future attachments:** separate attachment table + object storage (not v1).

---

## Testing and operations

- Compare **Mailgun** dashboard logs with **`helper_inbound_email`** (recipient, time). Mismatch → DNS, route pattern, or webhook URL.
- Signature failures → verify signing secret and Mailgun’s verification steps (including **timestamp** skew).
- **Idempotency:** same message retried → **one** task (duplicate handled in Phase 2).

---

## Document maintenance

1. Update **[INITIAL_PLAN.md](./INITIAL_PLAN.md)** when behavior changes.
2. Update **this file** so phases and checklists stay accurate.
