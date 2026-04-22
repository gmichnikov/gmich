# Helper — Split LLM calls (router + specialists) PRD

Draft design checklist for moving from **one Claude call per inbound email** to a **multi-stage** pipeline (classify → optional follow-up extraction), while preserving behavior and making room for **reminder-by-email** and **future domains** (e.g. meeting scheduling).

This document lists **requirements**, **interfaces**, **coverage vs today**, and **open decisions**. It is not an implementation ticket list.

---

## TL;DR

- **Today:** one Claude call returns `add_task` / `complete_task` / `unknown` (+ fields); webhook applies side effects.
- **Target:** a **router** call chooses a path; **task specialist** (and later others) return validated JSON → **code tools** (DB, email, logs).
- **Explicit reminder time on new tasks:** add optional **`reminder_at`** on the **task specialist** output (same route as `add_task`); server **precedence** = explicit reminder wins over `sync_reminder_with_due_date` (see [§13](#13-explicit-reminder_at-on-task-create-email--decided-approach)).
- **“Reminder-only” or update-existing-task reminders:** can stay **future** (`reminder_or_followup` specialist) if product wants a separate flow; not required for “new task + ping me then.”
- **Meetings:** separate specialist later; do not overload task JSON forever.

---

## Table of contents

1. [Why split](#1-why-split)  
2. [Key requirements](#2-key-requirements-must-haves-for-any-multi-call-design)  
3. [Router purpose](#3-first-call-router--purpose)  
4. [Router inputs](#4-first-call--inputs-baseline)  
5. [Router outputs](#5-first-call--outputs-what-the-router-may-emit)  
6. [Tools vs LLM calls](#6-second-stage--tools-vs-llm-calls)  
7. [Specialists / tools catalog](#7-second-level-specialists--tools--catalog-design-space)  
8. [Coverage matrix](#8-coverage-matrix--does-this-design-cover-everything-we-have-today)  
9. [Email goal = reminder](#9-email-whose-goal-is-scheduling-a-reminder)  
10. [Open questions](#10-open-questions-to-resolve-before--during-implementation)  
11. [Implementation phases](#11-suggested-implementation-phases)  
12. [Related docs](#12-related-docs)  
13. [**Explicit `reminder_at` on task create (email) — decided**](#13-explicit-reminder_at-on-task-create-email--decided-approach)  
14. [Glossary](#14-glossary)  
15. [Non-goals](#15-non-goals)  
16. [Decision log](#16-decision-log)  
17. [How to evolve this doc](#17-how-to-evolve-this-doc)

---

## Current state (snapshot)

| Piece | Location |
|--------|----------|
| Single-call prompt + parse | `app/projects/helper/claude.py` |
| Inbound pipeline + side effects | `app/projects/helper/webhook.py` |
| Task reminder fields + defaults | `app/projects/helper/reminder_logic.py`, `reminders_prd.md` |

---

## 1. Why split

- **Single prompt** mixes routing, duplicate detection, date resolution, assignee resolution, and JSON shape — it grows with every new “thing users can ask.”
- **New goals** (e.g. “remind me Thursday to …”, “schedule a meeting with …”) need **different structured outputs** and often **different side effects** than `HelperTask` CRUD.
- A **small router** can short-circuit (`unknown`) and reduce average latency/cost; **specialists** get smaller, testable prompts.

---

## 2. Key requirements (must-haves for any multi-call design)

| Area | Requirement |
|------|-------------|
| **Webhook contract** | Mailgun still gets **200** quickly; failures logged; no unbounded retries that double-charge. |
| **Idempotency** | Same `inbound.id` / idempotency key must not create duplicate tasks or duplicate side effects if Mailgun retries. |
| **Audit** | Every model call (or aggregated step) loggable on `helper_action_log` (or agreed extension): router output, specialist name, raw JSON, errors, **prompt/schema version**. |
| **Latency budget** | Define p50/p95 targets; serial calls add wall time — document acceptable tradeoffs (e.g. Haiku for both, or router only Haiku). |
| **Cost budget** | Router token cap + specialist caps; count tokens per inbound in logs/metrics. |
| **Failure modes** | Router fails → safe fallback (unknown + log). Specialist fails → do not partially apply side effects without a clear policy (transaction boundaries). |
| **Mis-routing** | Wrong router label should not corrupt DB: validation layer rejects impossible payloads; optional “second opinion” or human-safe default. |
| **Backward compatibility** | Existing intents and action types (`task_created`, `task_completed`, `unknown_intent`, …) either unchanged or explicitly migrated with a **feature flag** / rollout plan. |
| **Security / privacy** | Same rules as today: member-only actions, no cross-group leakage; prompts only include data the sender is allowed to see (open tasks for that group, member list). |
| **Testing** | Golden fixtures per route: JSON samples + expected DB + expected emails; contract tests on schemas per specialist. |
| **Versioning** | `prompt_version` / `schema_version` in logs for debugging “what did we ask in prod last week?” |

---

## 3. First call (“router”) — purpose

Decide **which specialist path** (if any) should run, with enough signal to choose **without** fully extracting task/meeting/reminder fields unless the design chooses a **fat router** (discouraged for v1).

---

## 4. First call — inputs (baseline)

Everything the **current** single prompt already receives (or should receive) for parity:

| Input | Notes |
|-------|--------|
| **Subject** | As today. |
| **Body** (stripped / plain) | As today; policy on HTML-only emails unchanged. |
| **Today’s date** | In **sender’s** (or group-default) timezone for “tomorrow / Friday.” |
| **Group member list** | `(full_name, email)` as today — needed for any path that resolves people. |
| **Open tasks summary** | At minimum: `id`, `title`, `notes` (as today) for **complete_task** and duplicate detection; router might get a **shortened** list if token pressure (tradeoff: mis-complete risk). |
| **Inbound metadata (optional for router)** | e.g. `group.name`, `sender email` — only if it improves routing without leaking other groups. |

**Explicitly not required for router v1:** full email headers, raw MIME (unless debugging separate admin path).

---

## 5. First call — outputs (what the router may emit)

These are **labels**, not final DB writes. Exact enum is a product decision; below is a **complete superset** to design against.

### 5.1 Routing labels (recommended minimal set for parity + growth)

| Router output | Meaning | Second stage? |
|---------------|---------|----------------|
| `task_operations` | User is primarily doing **Helper task list** work (add / complete / log-done / duplicate-ish). | **Yes** — task specialist (replaces current monolith for this path). |
| `unknown` | No safe actionable Helper automation (chat, ambiguous, off-topic). | **No** — same as today’s `unknown_intent`. |
| `needs_clarification` *(optional)* | Could act but missing critical slot (which task? which day?). | **Optional** — either no second call and send templated reply, or tiny “clarify” specialist. |

### 5.2 Future labels (not implemented until product agrees)

| Router output | Meaning | Second stage |
|---------------|---------|----------------|
| `reminder_or_followup` | **Primary** ask is a nudge / follow-up that does not map cleanly to “new task + optional fields” (e.g. reminder-only, or “bump task #7”). | **Yes** — reminder specialist (or narrow prompt). **Optional** if §13 covers most email cases via task specialist. |
| `meeting_scheduling` | User wants to **coordinate a meeting** (attendees, windows, conferencing). | **Yes** — meeting specialist; likely **different** side effects than `HelperTask` only. |
| `multi_intent` *(optional)* | Email clearly does two things (e.g. complete A + add B). | **Policy:** today we prefer **one** JSON; router could force **primary** only, or allow **ordered list** of operations (bigger change). |

**Note:** Router can also output **confidence** / **reason_codes** (strings for logs only) to help debugging and future gating.

---

## 6. Second stage — “tools” vs “LLM calls”

### 6.1 Conceptual model

- **Tool** = a **named operation** with a **typed input/output contract** that **application code** executes (DB, Mailgun, Google Calendar, etc.).
- **LLM call** = model produces JSON (or structured output) that **maps to** one or more tools after validation.

They are not mutually exclusive:

- **Recommended:** each **specialist** is an **LLM call** whose output is validated against a **JSON schema** and then translated into **zero or more tool invocations** (`create_task`, `complete_task`, `set_reminder`, …).
- **Deterministic tools** without LLM: e.g. `complete_task` could be **pure code** if router passes `task_id` with high confidence — usually **not** worth it for natural language; keep LLM for extraction.

### 6.2 Naming

Avoid overloading “intent” for both router and specialist. Suggested:

- **Router:** `route` or `domain` + optional `subkind`.
- **Specialist:** `operation` + payload (e.g. `task.add`, `task.complete`).

---

## 7. Second-level specialists / tools — catalog (design space)

### 7.1 Specialist: **Task operations** (replaces current extraction for Helper tasks)

**Purpose:** Cover everything the **current single prompt** does for `add_task` / `complete_task` (including `already_completed`, duplicate detection, assignee, due date, notes), **plus** optional explicit **`reminder_at`** for new/updated open tasks per [§13](#13-explicit-reminder_at-on-task-create-email--decided-approach).

| Aspect | Detail |
|--------|--------|
| **Inputs** | Subject, body, members, open tasks, sender TZ date — same as today’s specialist context. Optional **router summary** (1–2 sentences) only if validated safe; beware hallucination. |
| **Output (shape)** | Same as today: `intent` ∈ `add_task` \| `complete_task`; fields `title`, `due_date`, `assignee_email`, `notes`, `already_completed`, `duplicate_of_task_id`, or `task_id` for complete. **Add:** optional `reminder_at` (ISO-8601 string or `null`) on `add_task` when `already_completed` is false (and optionally when true if product allows). |
| **Maps to tools** | Insert/update `HelperTask`, apply **reminder precedence** from §13, confirmation emails, `HelperActionLog` rows. |

**Coverage:** Must subsume **all** current model-driven behavior on the happy path and error paths (missing title, bad duplicate id, etc.).

---

### 7.2 Specialist: **Reminder-only / update-existing** (optional later)

**Purpose:** When the email is **not** well modeled as “add_task with optional `reminder_at`” — e.g. “remind me again about #12 Friday 5pm” with no new title, or policy forbids reminder-only on task path.

| Aspect | Detail |
|--------|--------|
| **Inputs** | Subject, body, members, sender TZ, open tasks (for `task_id` resolution). |
| **Output** | TBD: e.g. `{ "mode": "update_task", "task_id", "reminder_at_iso" }` or `new_task` + fields. |
| **Maps to tools** | `task.update_reminder`, `task.create`, etc. |

**Relationship to §13:** Prefer **task specialist + optional `reminder_at`** first; introduce this specialist only if routing/UX still misfires.

---

### 7.3 Specialist: **Meeting scheduling** (future)

| Aspect | Detail |
|--------|--------|
| **Inputs** | Same baseline + later **calendar context** (OAuth, free/busy — separate work). |
| **Output (example)** | Draft meeting proposal: attendees (emails), duration, preferred windows, title, notes — **not** necessarily a `HelperTask`. |
| **Maps to tools** | `create_calendar_hold`, `send_draft_to_group`, or MVP `create_task_stub` — product decision. |

---

### 7.4 Tool layer (implementation-facing list)

| Tool / operation | When | Notes |
|------------------|------|--------|
| `task.create` | Specialist supplies new open or completed task row fields. | Insert + emails; apply §13 for `reminder_at` / `sync_reminder_with_due_date`. |
| `task.complete` | Specialist supplies `task_id`. | Today’s complete path + `clear_task_reminders`. |
| `task.duplicate_skip` | Specialist marks duplicate of open task. | Today’s branch + `send_duplicate_task_skipped`. |
| `reminder.set` | Explicit `reminder_at` on create/update (validated). | Shares rules with UI / `parse_reminder_at_iso`. |
| `noop.unknown` | Router or specialist says unknown. | Log + 200. |
| `meeting.*` *(future)* | Meeting specialist. | TBD. |

---

## 8. Coverage matrix — “does this design cover everything we have today?”

| Current behavior | Today | After split (target) |
|------------------|-------|----------------------|
| `unknown` | Single call | Router → `unknown`, **no** second call (or specialist returns unknown). |
| `add_task` / `already_completed: false` | Single call | Router → `task_operations` → task specialist → webhook tools. |
| `add_task` / `already_completed: true` | Single call | Same specialist path. |
| `duplicate_of_task_id` | Single call | Task specialist only (needs open list). |
| `complete_task` | Single call | Task specialist only. |
| Default `reminder_at` from `due_date` on create | **Server** `sync_reminder_with_due_date` | **Unchanged** when specialist omits `reminder_at`. |
| Explicit `reminder_at` from email | **Not supported** today | **§13** — specialist supplies field; server validates and sets. |
| `clear_task_reminders` on complete | Server | Unchanged. |
| Claude / JSON errors | Logged, admin email | Same; log **which stage** failed. |

---

## 9. Email whose goal is “scheduling a reminder”

| Scenario | Router | Specialist / notes |
|----------|--------|---------------------|
| **New task + “remind me at X”** | `task_operations` | Task specialist outputs `title`, optional `due_date`, optional **`reminder_at`** → §13. **Preferred default.** |
| **New task + due only** | `task_operations` | No `reminder_at` → server `sync_reminder_with_due_date` as today. |
| **Reminder-only or “bump task #7”** | `reminder_or_followup` *(optional later)* | Separate flow if §13 is insufficient. |
| **Same email, complete + add** | Policy unchanged | Still “one primary operation” until multi-intent is designed. |

---

## 10. Open questions (to resolve before / during implementation)

1. **Router output contract:** flat enum vs `{ domain, action }` vs nested.
2. **Open tasks in router:** full list vs summary vs omitted (latency vs mis-route risk).
3. **Multi-intent email:** continue “pick one primary” vs allow **multiple operations** in one inbound (ordering, atomicity).
4. **Model choice:** same model both stages vs cheaper router.
5. **Logging shape:** one `action_log` row per stage vs child rows linked to `inbound_email_id`.
6. **Reminder-from-email:** allow **`due_date` null + `reminder_at` set**? (Align `reminders_prd.md` exclusions vs UI behavior.)
7. **Meetings:** separate product vs task stub MVP; confirmation before external invites.

---

## 11. Suggested implementation phases

1. **Phase A — Instrumentation:** log token counts, latency, prompt version; no behavior change.
2. **Phase B — Router + task specialist behind flag:** duplicate current behavior; compare outputs in shadow mode or sample.
3. **Phase C — Cutover:** single call deprecated for inbound path.
4. **Phase D — Optional `reminder_at` in task JSON + webhook** (can ship **before** or **with** Phase B/C; does not require router split).
5. **Phase E — Reminder-only specialist** (only if product needs it after §13).
6. **Phase F — Meeting domain** (separate PRD).

---

## 12. Related docs

- `reminders_prd.md` — task reminder semantics (defaults, `reminder_at` / `reminder_sent_at`, logs).
- `claude.py` / `webhook.py` — current single-call contract and side effects.

---

## 13. Explicit `reminder_at` on task create (email) — decided approach

**Goal:** Support “add this task and **ping me at a specific time**” from natural language in one email, without forcing that instant to be derived only from **due date** (day-before-at-10am default).

**Where it lives:** **Task specialist** (same JSON as `add_task` today), **not** a separate router label for the common case. Router stays `task_operations`.

**New field (model output):**

- **`reminder_at`**: optional. ISO-8601 string (with `Z` or offset) or **`null`** / omitted.
- Interpret relative times using **sender timezone** (and document in prompt); normalize to **naive UTC** in storage using the same parsing rules as the app (`parse_reminder_at_iso` or equivalent).

**Server precedence (after task row exists, open path only):**

1. If payload includes a **valid** `reminder_at` (parse ok, strictly **in the future** at commit time): set `task.reminder_at`, clear `task.reminder_sent_at`, and **do not** call `sync_reminder_with_due_date` (would overwrite the explicit time).
2. If `reminder_at` is **absent** or invalid: if `due_date` is set, call **`sync_reminder_with_due_date`** as today; if no due date, leave reminder fields as today’s rules allow.

**`complete_task`:** unchanged; completion still clears reminders.

**Product alignment:** Update `reminders_prd.md` if email path allows **reminder without due date** when `reminder_at` is explicit; otherwise validate and reject with log + optional user-visible path later.

**Split-LLM:** No extra LLM call for this feature alone — only schema + webhook + prompt edits.

---

## 14. Glossary

| Term | Meaning |
|------|--------|
| **Router** | First LLM call (or rules + LLM): chooses path, minimal extraction. |
| **Specialist** | Second LLM call: full structured extraction for one domain (tasks, meetings, …). |
| **Tool** | Deterministic code that applies validated JSON (DB, Mailgun, etc.). |
| **Monolith** | Current single `parse_email_for_task` + one prompt. |
| **Inbound** | `HelperInboundEmail` row from Mailgun webhook. |

---

## 15. Non-goals

- This PRD does **not** specify exact token limits, model names, or pricing.
- It does **not** define Mailgun or Heroku runbooks.
- It does **not** replace `reminders_prd.md` for end-user reminder semantics — it **references** and should stay consistent.

---

## 16. Decision log

| Date | Decision | Where |
|------|----------|--------|
| *(add rows as you lock choices)* | | |
| — | **Optional `reminder_at` on task specialist / `add_task` path** with server precedence in §13 | §7.1, §13 |

---

## 17. How to evolve this doc

- When a **decision** is made, add a row to **§16** and tighten **§10** (remove or strike resolved questions).
- When **shipping** a phase, update **§8** and **TL;DR**.
- Prefer **short tables** over long prose for interfaces readers jump to often.
- If the doc grows past ~400 lines, split **meeting scheduling** into its own PRD and link it here.

---

*Document status: draft for discussion. Update as decisions land.*
