# PRD: Kids AI — Supervised AI Assistant

**Status:** Draft  
**Last Updated:** September 2026

Kids AI currently exists in the hub as a login-required shell at `/kids-ai` (no models, chat, or jobs yet). This document is the product source of truth.

---

## Overview

Kids AI is a supervised AI assistant for children, living as a project inside the hub web app. Parents (regular hub users) get visibility into their kids’ conversations and automated alerts when something looks concerning. Children chat with an age-appropriate assistant under dual-model moderation.

**Children are not hub users.** A Kids AI child is a separate identity: username + password, no email, no hub login, no access to any other project. There is no relationship between a child record and a `User` row.

v1 is **child chat + parent dashboard / summaries / alerts only.** Parents do not get a Kids AI chatbot. There is no standalone “adult user” path.

---

## Problem Statement

Parents want to give their children access to AI assistants for homework help, curiosity-driven learning, and creative play — but general-purpose AI tools are not designed with children as the primary user. The core risks are:

- Children steering conversations toward inappropriate topics
- No parental visibility into what their child is discussing
- No age-appropriate tone or content calibration

Kids AI solves all three.

---

## Goals

- Provide a safe, age-appropriate AI chat experience for children
- Give parents meaningful visibility without requiring them to read every message
- Let platform admins control which hub users can act as parents
- Flag concerning conversation patterns to parents proactively
- Keep child identity and data out of the rest of the hub
- Support multiple AI model providers without tight coupling to any one

---

## Non-Goals (v1)

- Image upload, image generation, or any non-text chat
- A chatbot for parents or other adults inside Kids AI
- Children using any other hub project, or later “promote this kid to a hub account”
- Real-time interruption of the model mid-token (Pass 2 may redirect after a reply is already on screen)
- Protection against sophisticated adversarial attacks (the target user is a child, not a bad actor)
- Replacing parental judgment — the system surfaces signal, parents decide what to do with it
- Per-child or per-parent model selection
- Parent unlock of locked conversations
- Admin-editable prompts

---

## User Roles

| Role               | Identity                         | What they do |
| ------------------ | -------------------------------- | ------------ |
| **Platform Admin** | Existing hub admin (`is_admin`)  | Allowlists which hub users may use Kids AI as parents. Cannot view conversations. |
| **Parent**         | Regular hub `User` (email login) | Once allowlisted, creates child accounts, uses the parent dashboard, receives summary and flag emails. Does **not** chat in Kids AI. |
| **Child**          | Kids AI-only record              | Username + password. Moderated chat only. Cannot change settings, reset their own password, or delete conversations. |

A child is never a hub user. A parent is never a child. Admin allowlisting does not make the admin a parent unless they allowlist themselves.

---

## Identity & Access

### Parents (hub)

1. An admin allowlists a hub user as a Kids AI parent (existing `/admin` UI).
2. Kids AI then appears as a normal project on that user’s hub homepage. They sign in with the existing hub login.
3. The parent opens `/kids-ai` and sees the **parent dashboard**, not a chat.

No pairing of two hub accounts. No “child loses hub access” step — children never had hub access.

### How people get there

- **Logged out** on the hub homepage: the Kids AI card goes to `/kids-ai/login` (child username + password). That page has a small **Parent? Sign in** link to the hub login (`next=/kids-ai`).
- **Hub-logged-in allowlisted parent:** the same card goes to `/kids-ai` (dashboard).
- **Child after login:** chat only. They cannot use other hub projects.

### Children (Kids AI only)

1. The parent creates each child from the dashboard: **username**, **password**, **age tier** (required), and a **display name** for emails/dashboard (e.g. “Maya”). Username is globally unique, case-insensitive, letters / numbers / underscore, 3–20 characters.
2. Creating the child is the COPPA consent moment and must be logged (which parent `User`, timestamp, child id, username, age tier).
3. The child signs in at `/kids-ai/login` (username + password), not the hub login. They can reach that page from the logged-out homepage. No email, no Google login, no password-reset email.
4. After login they only see Kids AI chat. They cannot reach other hub routes as a signed-in user because they are not a `User`.
5. The parent can disable a child (cannot log in) or reset the child’s password from the dashboard. Disabling does not delete conversations; the 30-day retention window still applies.

A parent may create as many children as they want. In v1 each child belongs to exactly one parent (the hub user who created them).

### Sessions

Child and parent sessions are **different cookies**. Child routes never treat a hub login as a child; parent dashboard routes never treat a child session as a parent. On a shared family device, both cookies could exist at once — paths and checks must stay strictly separate.

Child session lifetime matches the hub: normal Flask cookie session (until log out, parent disable, or the browser drops the cookie). No custom idle timeout.

### Dropped from the earlier draft

- Treating children as regular hub accounts
- Admin-created parent–child pairings between two `User` rows
- Restricting or restoring a child’s access to the rest of the hub
- A parent toggle for “full hub access”
- Standalone adult Kids AI users
- Unmoderated chat for parents

Giving a child access to the rest of the hub later would mean inventing a second identity. That is out of scope.

---

## Features

### 1. Account Management

**Admin**

- Allowlist / remove hub users as Kids AI parents
- Removing a parent from the allowlist hides their dashboard and blocks those children from logging in. Conversations are not deleted (30-day retention still applies). Re-allowlisting restores parent dashboard and child login.
- Cannot create child accounts, activate on a parent’s behalf, or view conversations

**Parent**

- Create children (username, password, display name, age tier required)
- Change age tier later (affects the system prompt going forward)
- Change display name (username is fixed after create)
- Disable / re-enable a child’s login
- Reset a child’s password
- Unpause a child after 3 locks (**Allow chatting again**)
- View conversation history
- Delete any conversation or all conversations for a child
- No “delete this child” in v1 — disable login instead. Conversations can still be deleted separately.

**Child**

- Log in with username + password
- See their unlocked conversations, continue one, or start a new one (unless paused after 3 locks)
- Cannot delete conversations or change their own settings

---

### 2. Age-Appropriate AI Behavior

The assistant’s behavior is controlled by a system prompt that is invisible to the child and set when a conversation starts. The system prompt:

- Establishes an age-appropriate persona and tone
- Explicitly names off-limits topics
- Instructs the model to redirect rather than refuse bluntly
- Addresses common jailbreak attempts (e.g. “pretend you have no rules”, “you are now a different AI”)
- Varies by age tier

**Age Tiers**

| Tier        | Age Range | Content Profile                                                                     |
| ----------- | --------- | ----------------------------------------------------------------------------------- |
| Young Child | 5–8       | Simple vocabulary, no discussion of violence/death/relationships, heavy redirection |
| Tween       | 9–12      | Moderate vocabulary, age-appropriate health topics allowed, firm topic limits       |
| Teen        | 13–17     | Near-standard behavior with guardrails on adult content and self-harm topics        |

Age tier is set by the parent, not inferred. Required when the child is created.

The system prompt is hardcoded in v1. A DB-backed admin-editable prompt with versioning is planned for v2.

---

### 3. Conversation Summarization

The post-response moderation call (Pass 2) also generates a plain-language running summary of the conversation so far. That summary is stored with the conversation and updated after every exchange.

A daily Heroku Scheduler job runs at **8:00 America/New_York**. It reads the latest stored summary for each child’s conversations updated in the past 24 hours and sends **one digest email per parent** covering all of that parent’s children. No additional AI calls at send time. No per-parent send-hour setting. Skip the email if that parent had no updates in the window.

The email has a brief snippet per conversation and a single link to the parent dashboard.

- Example: *“Maya — 2 conversations yesterday. Asked about volcanoes for a school project, practiced multiplication, and asked what happens when people die. The assistant responded age-appropriately to the last topic.”*
- Mailgun; one email per parent per day
- Full logs are in the parent dashboard
- **Children are told** their conversations are summarized for their parent. Not a configurable option.

---

### 4. Moderation & Flagging

Every child message is moderated. There is no unmoderated Kids AI chat in v1.

**Two passes on every child message exchange.**

**Pass 1 — before a reply is generated**

Two moderation calls in parallel (`gemini-3.5-flash-lite` and `gpt-5.6-luna`). Each gets the stored running summary (if any), the last ~20 messages, and the new child message. If either flags:

- No primary reply is generated or shown
- Child sees a brief warning and is sent to the Kids AI chat home
- Conversation is locked
- Parent gets an immediate email
- Conversation is flagged in the database

**Pass 2 — immediately after the reply is shown**

Same two models, in parallel, on the stored running summary (if any), the last ~20 messages, and the new exchange. Also writes an updated running summary of the whole conversation. If either flags:

- Child is warned and sent to chat home (may happen after they already saw the reply — acceptable in v1)
- Conversation is locked
- Parent gets an immediate email
- Conversation is flagged

Mechanism: after showing the reply, send is disabled. The child UI polls a lightweight status endpoint (about 1–2 seconds). Stop polling once a non-locked status is confirmed (re-enable send) or a lock is detected (warn and redirect). The child cannot send the next message until Pass 2 finishes.

**Dual-model rule:** union, not intersection. Same prompt to both models. Either flag is enough.

**Pass 1 prompt returns:** (1) binary flag, (2) brief plain-English concern if flagged (for the parent email). No summary — there is no new assistant reply yet.

**Pass 2 prompt returns:** (1) flag, (2) concern if flagged, (3) running summary of the full conversation including the latest exchange.

Explanations are free-form. Both prompts use the same risk dimensions:

- Self-harm or mental health crisis signals
- Bullying or aggression (incoming or expressed)
- Sexual or adult content attempts
- Requests for personally identifying information
- Repeated probing of off-limits topics

| Trigger                    | Child experience                          | Parent notification | DB      |
| -------------------------- | ----------------------------------------- | ------------------- | ------- |
| Either model, Pass 1 or 2  | Warning, redirect to chat home, locked. After 3 locks, chatting paused. | Immediate email (3rd notes pause) | Flagged; lock count +1 |
| Neither flags              | No interruption                           | Daily digest        | Normal  |

**Flag email (Mailgun, immediate):** which child (display name), model-generated concern, link to sign in and view the thread. No verbatim quote of the child’s message. No rate limit in v1. On the 3rd lock, the email also says Kids AI chatting is paused until the parent reviews.

**Locking**

- Child cannot reopen or see a locked conversation
- Parent can read it in full
- Individual conversation locks are permanent in v1 (unlock a specific thread is v2)
- No cooldown after lock 1 or 2 — the child may start a new conversation. No context carries over.
- **3-lock pause:** a lock is one flagged conversation. After the 3rd lock, the child can still log in but cannot send or start a new conversation until the parent taps **Allow chatting again**. The counter then resets to 0. Locked threads stay locked. Count is all-time until that reset (not a rolling window).
- Parent **disable** (cannot log in) is separate from this pause.

---

### 5. Parent Dashboard

- Hub-login only; allowlisted parents
- Lives at `/kids-ai/` (dashboard is the parent home; children never see this)
- Lists each child (display name, username, age tier, enabled/disabled, paused-after-3-locks or not)
- Per child: conversations with date, opening message, flagged or not, latest summary snippet
- Flagged threads visually distinguished
- Full transcript of a selected conversation
- Create children, disable/enable login, reset password, change age tier, delete conversations, **Allow chatting again** after a 3-lock pause
- Shows the parent’s remaining hub credits (no add/request-credits UI; that stays admin-only)

---

### 6. Model Selection

Hardcoded in v1. No per-child or per-parent choice. Configurability is v2.

| Role                               | Model                   | Provider   |
| ---------------------------------- | ----------------------- | ---------- |
| Primary conversation               | `claude-sonnet-5`       | Anthropic  |
| Moderation — Model A (both passes) | `gemini-3.5-flash-lite` | Google     |
| Moderation — Model B (both passes) | `gpt-5.6-luna`          | OpenAI     |
| Conversation title (once)          | `gemini-3.5-flash-lite` | Google     |

Moderation models: fast and cheap. Primary: safety behavior and conversational quality. Titles reuse Model A.

---

### 7. Credits

Sending a message costs **1 credit from the parent’s hub `User.credits`**, deducted after Pass 1 clears. No credit is charged if Pass 1 blocks the message. Moderation and summarization are platform cost.

If the parent has no credits, none of that parent’s children can send. The balance is checked **before** Pass 1 so a zero-credit send does not call any models. The kid sees a simple “can’t send right now” message.

Deducting from `User.credits` uses the existing hub listener: when the parent’s balance crosses from positive to zero, the admin already gets the “out of credits” email (source will show Kids AI). No extra Kids AI-specific alert. Attempts to send while already at zero do not email again.

No credit refunds in v1 (including if Claude fails after Pass 1 already charged).

Admin tops up the parent the same way as any other hub account. Parents do not transfer credits to children; children have no balance of their own.

---

### 8. Conversations

A conversation is a unit of chat history. After login, the child sees a list of their **unlocked** conversations and can continue one or start a new one — same as a normal chatbot. No idle timeout or auto-split. Multiple conversations per day are allowed; each is stored and summarized independently.

Locked conversations are hidden from the child (parent can still read them). A locked thread cannot be continued; the child must start or open a different one.

**Title:** Neither parent nor child names it. After the first completed exchange, `gemini-3.5-flash-lite` generates a short label. If Pass 1 locks before any reply, the title is a truncated copy of that first child message (~60 characters). Stored; not edited in v1. Separate from the Pass 2 running summary used in the daily digest.

---

## Technical Architecture

```
[Child login — username/password, Kids AI session cookie]
    |
    v
[Child chat UI]
    |
    v
[Pass 1: Pre-response moderation]
  - gemini-3.5-flash-lite ]
  - gpt-5.6-luna          ] in parallel; running summary + last ~20 messages + new message
  - Each returns: flag, concern if flagged
  - If either flags → lock, increment lock count, warn, redirect, email parent; pause if count is 3; stop
    |
    v (only if Pass 1 clear — deduct 1 credit from parent User.credits)
[Primary AI — claude-sonnet-5]
  - System prompt from child's age tier
  - Full reply shown to child (no streaming)
    |
    v
[Pass 2: Post-response moderation] (immediately; send stays disabled until it finishes)
  - same two models in parallel; running summary + last ~20 messages + new exchange
  - Each returns: flag, concern if flagged, running summary
  - Store summary (prefer unflagged model's summary if one flags; either if both flag)
  - If either flags → lock, increment lock count, warn via poll, redirect, email parent; pause if count is 3

[Parent — hub login, allowlisted]
  - Dashboard, consent log, password reset, deletes
  - Mailgun: flag emails + daily digest

[Daily Summary Job] (Heroku Scheduler, 8:00 America/New_York)
  - Latest stored summary per conversation updated in the last 24 hours
  - Skip parent if no updates
  - One digest email per parent via Mailgun

[Retention Scheduler] (Heroku Scheduler, daily)
  - Hard-deletes conversations where modified_at is older than 30 days
```

Child auth is a Kids AI-specific session, not Flask-Login `User`. Parent auth is the existing hub session.

Pass 2 is specified as “right after the reply,” not a daily batch job. How that runs on Heroku (request thread vs worker) is an implementation choice. Send stays disabled until Pass 2 returns clear or locked.

---

## Decisions

1. **v1 scope:** Child chat, moderation, parent dashboard, summaries, and alerts only. No parent chat. No standalone adult users.
2. **Identity:** Children are Kids AI-only (username + password, no email). Parents are hub `User`s. No link between a child and a hub account. Kids cannot use the rest of the site.
3. **Admin:** Allowlists parent hub users only. Does not create children or read conversations.
4. **Child creation:** Parent creates children from the dashboard. Age tier is required. That create event is COPPA consent and is logged.
5. **Child login:** `/kids-ai/login`; separate session cookie from the hub. Logged-out homepage card goes here. Parent reaches the dashboard via hub login (homepage card if already signed in, or **Parent? Sign in** on the kid login page).
6. **Passwords:** Parent sets and resets child passwords. Minimum 4 characters (same as hub signup). No email-based reset for children.
7. **One parent per child** in v1. A parent may have many children.
8. **Data retention:** 30 days from last modification, daily scheduler hard-delete. Parent delete is immediate. Child cannot delete. Disabling a child does not delete conversations.
9. **Child awareness:** Children are told conversations are summarized for their parent. Not configurable.
10. **False positive handling:** No in-product feedback mechanism in v1. Revisit post-launch.
11. **Prompts:** System and moderation prompts hardcoded in v1. Admin-editable versioned prompts in v2.
12. **Minimum age / COPPA:** No hard minimum age. Consent is required for every child, via parent-created accounts (see Legal).
13. **Locking:** Each flagged conversation stays locked (no per-thread unlock in v1). No cooldown after lock 1 or 2. After 3 locks, chatting is paused until the parent taps **Allow chatting again**; the counter resets to 0. No context carried into the next conversation.
14. **Admin vs parent UI:** Admin = membership. Parent = children, transcripts, deletes, disable/reset, unpause after 3 locks.
15. **Flag email:** Free-form model concern + link. No verbatim child message. No rate limit in v1.
16. **Moderation:** Two models, both passes, same prompt, union of flags. Context is the stored running summary plus the last ~20 messages (not the full thread). The primary chat model still gets the full conversation.
17. **Summaries:** Written by Pass 2, stored, daily one-email-per-parent digest at 8:00 America/New_York (last 24 hours, skip if quiet). No extra AI calls. No per-parent send hour.
18. **Models:** Primary `claude-sonnet-5`. Moderation A (and titles) `gemini-3.5-flash-lite`. Moderation B `gpt-5.6-luna`.
19. **Conversations:** Child can continue unlocked threads or start a new one (list after login). Locked threads are hidden from the child. Title from `gemini-3.5-flash-lite` after the first exchange; if Pass 1 locks first, title is a truncated first message.
20. **Hub access for children:** Not offered. Out of scope rather than a parent toggle.
21. **Credits:** 1 credit per child message, deducted from the **parent’s** hub `User.credits` after Pass 1 clears. Balance is checked before Pass 1; at 0, no model calls. No charge if Pass 1 blocks. Moderation is free. Crossing to zero uses the existing admin credits-exhausted email. Admin tops up the parent. Children have no credit balance.
22. **Pass 2 vs next send:** Send stays disabled until Pass 2 finishes. Then either re-enable send or lock / redirect.
23. **Long threads:** Moderation sees the Pass 2 running summary plus the last ~20 messages. Primary `claude-sonnet-5` still sees the full conversation.
24. **Provider calls:** Direct Anthropic, Google, and OpenAI APIs. No LiteLLM.
25. **Homepage routing:** Logged out → `/kids-ai/login`. Allowlisted parent already on the hub → `/kids-ai` dashboard.
26. **Child session:** Same as the hub cookie session — until log out, parent disable, or the browser drops the cookie. No custom idle timeout.
27. **Streaming:** No. Wait for the full `claude-sonnet-5` reply, show it, then run Pass 2.
28. **Allowlist removed:** Parent dashboard is unavailable and that parent’s children cannot log in. Conversations are kept. Re-allowlisting restores both.
29. **Zero credits:** Check parent balance before Pass 1. Existing hub admin alert fires when the last credit is spent; no extra email if a kid tries again at zero.
30. **Username:** Globally unique, case-insensitive, `[a-zA-Z0-9_]`, 3–20 characters. Display name is required, 1–50 characters, not unique.
31. **Daily digest time:** One job at 8:00 America/New_York; window is the previous 24 hours. Skip parents with no updates.
32. **Credits on dashboard:** Show the parent’s remaining hub credits. No request/add-credits control for parents.
33. **Modality:** Text only. No uploads, no generated images.
34. **Child record lifetime:** Parents can disable login and delete conversations. They cannot delete the child identity in v1.
35. **Editable child fields:** Display name, age tier, password, enabled/paused. Username is immutable after create.
36. **Message length:** Child messages capped at 2,000 characters.
37. **Child password:** Minimum 4 characters, same as hub signup. Parent-chosen.
38. **Display name:** Required, 1–50 characters, not unique. Shown in emails and the parent dashboard.
39. **Title fallback:** Truncated first child message if the thread is locked before any assistant reply.
40. **Reply rendering:** Basic markdown for assistant messages (no raw HTML). Child messages as plain text.
41. **Pass 1 outage:** Fail closed — no reply, no charge, no lock. Kid can retry.
42. **Credits on Claude failure:** No refunds in v1.
43. **Pass 2 outage:** Log, do not lock, re-enable send.

---

## Open questions

v1 product questions above are settled. Further items below are implementation/UX gaps as they come up.

---

## Legal & Compliance

### COPPA (US)

COPPA triggers on “actual knowledge” that a user is under 13. Knowledge is established when a **parent creates a child account** and chooses an age tier — not at hub signup (hub signup still does not collect age).

Because the child is not a hub `User`, that knowledge does **not** extend to chatbot, games, or other projects. Kids AI is the only surface that collects the child’s messages.

**Parental consent:** Creating the child (username, password, age tier) is the verifiable consent event. Log: parent `User` id, timestamp, child id, username, age tier selected.

There is no second “hub access” consent event in v1 because children cannot use the rest of the site.

**Parent rights:** Access, review, and delete the child’s conversation data via the dashboard. Children cannot delete their logs.

**Data retention:** 30 days from last modification; parent delete is immediate. A written retention policy should be maintained and surfaced in the privacy notice.

**Hub signup:** Unchanged. ToS can still say 13+ to create a hub account. Children never use that flow.

**Security program:** Written information security program, including periodic risk assessment and monitoring, is still required if COPPA applies.

**Penalties:** Civil penalties on the order of tens of thousands of dollars per violation (amount changes over time).

### Other regulations to monitor

- **GDPR Article 8 (EU):** Parental consent under 16 (13–16 by member state) if any users are in Europe.
- **US/state kids’ privacy laws** and any successor to COPPA that extends beyond under-13.

### Recommended pre-launch legal steps

- Lawyer review of the parent-created-child consent flow and privacy notice
- Written data retention policy
- Confirm the security program matches current COPPA expectations
- Classify Anthropic, OpenAI, and Google as integral vs non-integral third parties under COPPA (non-integral may need separate consent)

---

## Technical Notes

### AI providers

Call Anthropic, OpenAI, and Google directly, same pattern as other hub projects. No LiteLLM. API keys are already in the app environment.

**Failures**

- **Pass 1 (either model errors/times out):** fail closed — no Claude reply, no credit charge. Show the kid a generic “try again” (not a flag/lock unless a model actually flagged).
- **Primary Claude fails after Pass 1 charged:** show an error; **do not refund** the credit.
- **Pass 2 errors:** log it, do not lock, **re-enable send**. One bad Pass 2 must not freeze the kid.

### System prompt

Primary safety mechanism. Should cover age-appropriate persona, named off-limits topics, warm redirection, and common child jailbreaks. Hardcoded in v1; iterate using the moderation log.

### Moderation call pattern

Per child message, five AI calls:

1. Pass 1 — `gemini-3.5-flash-lite` (running summary + last ~20 messages + new message) → flag + concern
2. Pass 1 — `gpt-5.6-luna` (same) in parallel
3. Primary — `claude-sonnet-5` only if both Pass 1 calls pass (full conversation)
4. Pass 2 — `gemini-3.5-flash-lite` (running summary + last ~20 + new exchange) → flag + concern + updated summary
5. Pass 2 — `gpt-5.6-luna` (same) in parallel

Either flag at either pass locks and alerts. Daily email uses the stored Pass 2 summary only.

**Cost:** 5 model calls per child message. At most one of those is the “user-facing” generation. That call costs 1 credit from the parent after Pass 1 clears.

### Retention

Daily job hard-deletes conversations with `modified_at` older than 30 days. Parent deletes bypass the scheduler.

### Data model

Not designed yet. Expected entities (names TBD): parent allowlist tied to `User`, child identity (username, password hash, display name, age tier, enabled, parent id, lock count, paused), consent log, conversations, messages, moderation results / summaries, session for child auth.

Do not put children in the `user` table.

---

## Success Metrics

- Share of allowlisted parents who create at least one child
- Daily active child sessions
- Flag rate per session (too high ⇒ likely false positives / prompt tuning)
- Parent-reported trust (periodic, informal is fine at family scale)
- Daily digest open rate (if measurable)

---

## Dependencies

- Hub auth for **parents only** (`User`, `is_admin`, existing login)
- Existing `/admin` for parent allowlisting
- New Kids AI child auth (not `User` / not Flask-Login as used today)
- Mailgun for flag emails and daily digests
- Heroku Scheduler for daily digest and retention
- Anthropic, OpenAI, and Google API keys already in the environment
