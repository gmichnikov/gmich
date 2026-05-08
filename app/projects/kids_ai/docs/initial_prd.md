# PRD: Kids AI — Supervised AI Assistant

**Status:** Draft  
**Last Updated:** May 2026

---

## Overview

Kids AI is a supervised AI assistant project living inside the existing hub web app. It allows parents to provide children with access to an age-appropriate AI assistant, while giving parents visibility into conversations and automated flagging of concerning content. The project is entirely self-contained — "child" and "parent" are Kids AI concepts only; all accounts are regular hub accounts.

---

## Problem Statement

Parents want to give their children access to AI assistants for homework help, curiosity-driven learning, and creative play — but general-purpose AI tools are not designed with children as the primary user. The core risks are:

- Children steering conversations toward inappropriate topics
- No parental visibility into what their child is discussing
- No age-appropriate tone or content calibration

Kids AI solves all three.

---

## Goals

- Provide a safe, age-appropriate AI experience for children
- Give parents meaningful visibility without requiring them to read every message
- Allow platform admins to control which accounts can access the feature
- Flag concerning conversation patterns to parents proactively
- Support multiple AI model providers without tight coupling to any one

---

## Non-Goals

- Real-time conversation blocking (async moderation is sufficient for this threat model)
- Protection against sophisticated adversarial attacks (the target user is a child, not a bad actor)
- Replacing parental judgment — the system surfaces signal, parents decide what to do with it

---

## User Roles

All users are regular hub accounts. The following roles are Kids AI-specific designations only — they have no effect on any other project in the hub.

| Role               | Description                                                                                           |
| ------------------ | ----------------------------------------------------------------------------------------------------- |
| **Platform Admin** | Existing hub admin (`is_admin = True`). Creates and manages Kids AI memberships and pairings.         |
| **Adult user**     | A hub account added to Kids AI directly (no child pairing). Uses the AI chatbot without moderation.   |
| **Parent**         | A hub account linked to one or more child accounts via an admin-created pairing. Receives summaries and alerts; has a parent dashboard. |
| **Child**          | A hub account linked to a parent via an admin-created pairing. Gets the moderated AI experience; cannot modify their own settings. |

A given account can only hold one Kids AI role. An account that is a parent cannot also be a child, and vice versa.

Adult users added to Kids AI retain full hub access — Kids AI simply appears as an additional project on their hub homepage. Only child accounts have hub access restricted.

---

## Hub Access for Child Accounts

The moment an admin creates a parent-child pairing, the child account **immediately loses full hub access** — the hub homepage shows only a message like *"Your account is being set up. Check back soon."* Kids AI itself is also unavailable until the parent activates it.

The parent is not emailed — the admin notifies them offline. However, the next time the parent logs into the hub (any page), they see a **prominent banner** prompting them to activate Kids AI for their child. They do not need to know to navigate to `/kids-ai` first.

Once the parent activates Kids AI, the child can access Kids AI. Full hub access remains off unless the parent separately enables it.

**Hub access is a separate parent-controlled toggle** from Kids AI activation. Both require explicit parent action.

| Setting                | Default | Effect when enabled                                              |
| ---------------------- | ------- | ---------------------------------------------------------------- |
| Kids AI access         | Off     | Enables Kids AI with full moderation and parental visibility     |
| Full hub access        | Off     | Child can use all other hub projects without any supervision     |

When the parent enables full hub access, they are explicitly informed: *"Your child will be able to use all other features of this site without supervision."* Both consent events are logged (see COPPA section).

---

## Features

### 1. Account Management

**Admin Controls**

- Admins use the existing `/admin` UI to manage Kids AI
- Admins can add any hub account to Kids AI in one of two ways:
  - As a **standalone adult user** (no pairing; gets the chatbot without moderation)
  - As part of a **parent-child pairing** (links two hub accounts as parent and child)
- A child account must have exactly one linked parent account
- A parent account can be linked to multiple child accounts
- Admins cannot activate Kids AI on behalf of a parent — activation requires explicit parent action
- Admins cannot view conversations — their scope is membership and pairing management only

**Parent Controls**

- After an admin creates a parent-child pairing, the child account is immediately restricted (hub access removed, Kids AI not yet available). The admin notifies the parent offline. The next time the parent logs into the hub, a banner prompts them to activate Kids AI for their child.
- The parent must explicitly activate Kids AI for each associated child. **Age tier is required at activation time** — the parent must select it before activation completes. This activation event is the COPPA consent moment and must be logged (who enabled, timestamp, which child account, age tier selected).
- Parents can separately enable full hub access for each child. This is a second logged consent event.
- Parents can disable Kids AI or hub access for any child at any time. Disabling Kids AI does not delete conversations — the 30-day retention window still applies and parents can manually delete if desired.
- Parents can set the child's age range, which affects the system prompt and content calibration
- Parents can view conversation history directly at any time
- Parents can delete any individual conversation or the full conversation history at any time
- Children cannot delete conversations

---

### 2. Age-Appropriate AI Behavior

The AI assistant's behavior is controlled via a system prompt that is invisible to the child and set at session initiation. The system prompt:

- Establishes an age-appropriate persona and tone
- Explicitly names off-limits topics
- Instructs the model to redirect rather than refuse bluntly (warmer UX)
- Addresses common jailbreak attempts directly (e.g., "pretend you have no rules", "you are now a different AI")
- Varies by age tier (see below)

**Age Tiers**

| Tier        | Age Range | Content Profile                                                                     |
| ----------- | --------- | ----------------------------------------------------------------------------------- |
| Young Child | 5–8       | Simple vocabulary, no discussion of violence/death/relationships, heavy redirection |
| Tween       | 9–12      | Moderate vocabulary, age-appropriate health topics allowed, firm topic limits       |
| Teen        | 13–17     | Near-standard behavior with guardrails on adult content and self-harm topics        |

Age tier is set by the parent, not inferred automatically.

The system prompt is hardcoded in v1. A DB-backed admin-editable prompt with versioning is planned for v2.

---

### 3. Conversation Summarization

The post-response moderation call (Pass 2) does double duty: in addition to checking for flags, it generates a plain-language running summary of the conversation so far. This summary is stored in the database alongside the moderation result and updated after every exchange.

A daily Heroku Scheduler job reads the latest stored summary for each child's conversations updated in the past 24 hours and sends **one digest email per parent** covering all their linked children. No additional AI calls are made at summary time.

The email contains a brief summary snippet per conversation and a single link to the parent dashboard, where the parent can see full details and drill into any individual conversation.

- Example summary snippet: *"Maya — 2 conversations yesterday. Asked about volcanoes for a school project, practiced multiplication, and asked what happens when people die. The assistant responded age-appropriately to the last topic."*
- Delivered by email via Mailgun; one email per parent per day regardless of how many children or conversations
- Raw conversation logs are accessible to parents on demand via the parent dashboard
- **Children are explicitly informed** that their conversations are summarized for their parent. This is a firm product decision, not a configurable option.

---

### 4. Moderation & Flagging

Moderation applies only to child accounts. Adult users and parents use the chatbot without moderation.

**Two moderation passes run on every child message exchange.**

**Pass 1 — Pre-response check (before AI response is generated)**

Before the child's message is sent to the primary AI, it is evaluated by two moderation calls in parallel using different models from different providers. Both receive the full conversation history plus the child's new message. If either model flags:

- The primary AI response is not generated or shown
- The child is shown a brief warning (e.g., "This conversation has been flagged") and redirected to the Kids AI home page (`/kids-ai/`)
- The conversation is locked — the child cannot reopen or continue it; they must start a new one
- The parent receives an immediate email alert (see Email Alert spec below)
- The conversation is flagged in the database

**Pass 2 — Post-response review (fires immediately after each AI response is delivered)**

The moment the primary AI response is shown to the child, a background review is triggered on the full conversation history including the new exchange. This is not a scheduled batch job — it runs after every single response. It catches cases where the conversation is drifting in a bad direction even if no single message was obviously problematic. The Pass 2 call also generates an updated plain-language summary of the conversation (see Summarization). If either model flags:

- The child is shown a warning and redirected to `/kids-ai/`
- The conversation is locked
- The parent receives an immediate email alert
- The conversation is flagged in the database

The child may experience this as seeing a response and then immediately being redirected — this is acceptable in v1. The mechanism: after rendering the primary AI response, the child's UI polls a lightweight status endpoint. If the conversation has been locked (by Pass 2 completing), the UI redirects to `/kids-ai/` and shows the warning. The polling interval should be short (e.g., 1–2 seconds) and stop once a non-locked status is confirmed or a lock is detected.

**Dual-Model Moderation Rationale**

Two moderation calls are made per pass using different models from different providers (e.g., Claude + GPT-4o). Either model flagging is sufficient to trigger the full response — the union, not the intersection. Both models receive the same prompt. This approach reduces blind spots any single model might have and makes the system more robust to model-specific failure modes.

**Moderation Prompts**

Pass 1 and Pass 2 use different prompts because their context differs.

**Pass 1 prompt** instructs the model to return:
1. A binary flag (yes/no)
2. A brief plain-English explanation of the concern, if flagged (used in the parent email)

Pass 1 runs before the primary AI has responded, so there is no new exchange to summarize yet.

**Pass 2 prompt** instructs the model to return:
1. A binary flag (yes/no)
2. A brief plain-English explanation of the concern, if flagged (used in the parent email)
3. A plain-language running summary of the full conversation so far, including the latest exchange (stored for the daily email job)

All explanations are free-form, not chosen from a fixed list. Both prompts enumerate the same risk dimensions and ask for a concise, parent-readable reason if any are detected.

**Risk Dimensions Scored**

- Self-harm or mental health crisis signals
- Bullying or aggression (incoming or expressed)
- Sexual or adult content attempts
- Requests for personally identifying information
- Repeated probing of off-limits topics

**Flagging Behavior**

| Trigger                                          | Child Experience                                                    | Parent Notification       | DB State |
| ------------------------------------------------ | ------------------------------------------------------------------- | ------------------------- | -------- |
| Either moderation model flags (Pass 1 or Pass 2) | Warning shown, redirected to `/kids-ai/`, conversation locked       | Immediate email           | Flagged  |
| Neither model flags                              | No interruption                                                     | Included in daily summary | Normal   |

**Email Alert to Parent**

Sent immediately via Mailgun when a flag is triggered. Contains:

- Which child's conversation was flagged
- A plain-English description of the concern, as generated by the flagging model
- A link to sign in and view the full conversation in the app

The email does not quote the child's message verbatim. The free-form description from the model provides context; the full exchange is available in-app. No rate limiting on flag emails in v1.

**Conversation Locking**

- A locked conversation is completely inaccessible to the child — they cannot reopen it or see its contents
- The parent can view the locked conversation in full via the parent dashboard
- Locks are permanent in v1. Parents cannot unlock conversations. (Unlock with parent-provided rationale is planned for v2.)
- No cooldown before the child can start a new conversation
- No context from a locked conversation carries over to new conversations

---

### 5. Parent Dashboard

- The parent dashboard lives at `/kids-ai/dashboard` (requires login; only accessible to parent-role accounts)
- Shows each linked child account with their Kids AI status (active/inactive) and hub access status
- Selecting a child shows a list of their conversations, each displaying: date, opening message, whether the conversation is flagged, and the latest summary snippet
- Flagged conversations are visually distinguished
- Selecting a conversation shows the full exchange
- Parents can toggle Kids AI access and hub access for each child from this view
- Parents can delete any individual conversation or all conversations for a child
- No other required actions — the dashboard is primarily informational

---

### 6. Model Selection

In v1, a single primary model is chosen and hardcoded for the child's conversation. No per-child or per-parent model selection is available. The moderation passes use two different hardcoded models from different providers (e.g., Claude for Model A, GPT-4o for Model B) — this is also fixed in v1.

Model configurability is deferred to v2.

---

### 7. Credits

Sending a message costs 1 credit, deducted from the **child's own** hub credit balance. Moderation calls (Pass 1 and Pass 2) do not cost additional credits. Credit deduction happens after Pass 1 clears — no credit is charged if a message is blocked at Pass 1.

If a child has no credits, they cannot send messages. Credits must be added to the child's account by an admin (same mechanism as any other hub account).

---

### 8. Conversations

A conversation is a named unit of chat history. A child starts a new conversation explicitly (a "New conversation" button on the Kids AI home page). There is no automatic timeout or session-based splitting. A child can have multiple conversations in a day; each is stored and summarized independently. Locked conversations are permanently closed — the child must start a new one.

Adult user conversations follow the same model but without moderation or locking. Adult user conversations are stored with a `modified_at` timestamp and subject to the same 30-day retention policy as child conversations.

---

## Technical Architecture

```
[Child UI]
    |
    v
[Pass 1: Pre-response moderation]
  - Model A (e.g. Claude) ]
  - Model B (e.g. GPT-4o) ] run in parallel, receive full convo history + new message
  - If either flags → lock convo, warn child, redirect to /kids-ai/, email parent, stop
    |
    v (only if Pass 1 clear — deduct 1 credit here)
[Primary AI Call]
  - System prompt selected based on child's age tier
  - Generates response shown to child
    |
    v
[Pass 2: Post-response moderation] (fires immediately, non-blocking to child UI)
  - Model A ] run in parallel, receive full convo history including new exchange
  - Model B ] each returns: flag (yes/no), concern description if flagged, running summary
  - Store summary (from whichever model; prefer unflagged model's summary if one flags)
  - If either flags → lock convo, warn child, redirect to /kids-ai/, email parent

[Daily Summary Job] (Heroku Scheduler, runs once per day)
  - For each active child with conversations updated in the past 24 hours:
    - Pull the latest stored summary per conversation
    - Send digest email to parent via Mailgun

[Retention Scheduler] (Heroku Scheduler, runs daily)
  - Hard-deletes conversations where modified_at > 30 days ago
```

---

## Decisions

1. **Data retention:** Conversations are retained for 30 days from last modification, enforced by a daily Heroku Scheduler job. Parents can manually delete at any time (immediate). Children cannot delete. Disabling Kids AI does not trigger deletion.
2. **Child awareness:** Children are explicitly told their conversations are summarized for their parent. Full transparency, non-configurable.
3. **False positive handling:** No feedback mechanism in v1. To revisit post-launch.
4. **Moderation prompt:** Hardcoded in v1. DB-backed admin-editable prompts with versioning deferred to v2.
5. **Minimum age / COPPA:** No hard minimum age. Parental consent is required for all child accounts regardless of age, satisfied by the explicit parent activation step (see COPPA section).
6. **Conversation locking:** Permanent in v1. Parent unlock with rationale planned for v2.
7. **Context across conversations:** None. Locked conversations do not carry context into new ones.
8. **Admin scope:** Membership and pairing management only, via the existing `/admin` UI. Admins cannot view conversations.
9. **Parent dashboard actions:** Parents can view conversations, toggle Kids AI and hub access, and delete conversations. No other actions in v1.
10. **Email content:** Free-form model-generated description of the concern + link to app. No verbatim message quoting. No rate limiting on flag emails in v1.
11. **Moderation models:** Same prompt given to both models. Full conversation history passed to each. Either flagging triggers action.
12. **Credits:** 1 credit per message, deducted from the child's own credit balance after Pass 1 clears. No credit charged if blocked at Pass 1. Moderation calls are free. No credits for adult users' messages (same 1-credit rule applies to all users).
13. **Summarization:** Generated by the Pass 2 moderation call (dual-purpose). Stored in DB. Daily job sends one digest email per parent — no AI calls at summary time.
14. **Hub access for children:** Restricted immediately on pairing creation. Parent can grant full hub access as a separate toggle. Both activation events are logged for COPPA. Adult users retain full hub access.
15. **Model selection:** Single hardcoded primary model in v1. Moderation uses two hardcoded models from different providers. No per-user or per-child model selection in v1.
16. **Age tier:** Required at activation time. Parent must select before activation completes. Logged as part of the consent event.
17. **Conversations:** Started explicitly by the child (no auto-split). Multiple conversations per day are allowed. 30-day retention applies to both child and adult user conversations.

---

## Legal & Compliance

### COPPA (US)

COPPA triggers on "actual knowledge" that a user is under 13. In this system, actual knowledge is established at the moment an admin creates a parent-child pairing — not at account creation (no age is collected during signup). From that point, COPPA applies to the child account's use of the entire platform, not just Kids AI.

This is addressed by restricting child accounts to Kids AI only by default. If a parent grants full hub access, they do so with explicit informed consent that covers the child's use of all hub projects.

**Parental consent:** Verifiable parental consent is required before collecting personal information from a child. This is implemented via the explicit parent activation flow: an admin creates the pairing, but the parent must separately log in and enable Kids AI for each child. This activation event is the primary consent moment. A second consent event is logged if the parent later grants full hub access. Both events record: which parent account consented, timestamp, and which child account.

**Parent rights:** Parents must be able to access, review, and delete their child's data. Implemented via the parent dashboard. Children cannot delete their own conversation logs.

**Data retention:** Conversations retained for 30 days from last modification. Parent-initiated deletions are immediate. A written retention policy must be maintained and surfaced in the privacy notice.

**No age collection at signup:** Regular account creation does not ask for age. A standard ToS clause (must be 13+ to create an account) covers non-child accounts. The "child" designation is established via the admin pairing flow, not self-reported.

**Security program:** A written information security program is required, including annual risk assessments and ongoing monitoring.

**Penalties:** Civil penalties of up to ~$53,000 per violation.

### Other Regulations to Monitor

- **GDPR Article 8 (EU):** Similar parental consent requirements for users under 16 (varies by member state, minimum 13). Relevant if any users are in Europe.
- **COPPA 2.0 (pending US legislation):** Would extend protections to minors under 17 and ban targeted advertising to all minors. Not law yet but has bipartisan support.
- **State laws:** Texas, Louisiana, and Utah have enacted their own children's data laws. Other states are likely to follow.

### Recommended Pre-Launch Legal Steps

- Have a lawyer review the parental consent flow and privacy notice
- Draft and document the written data retention policy
- Confirm the existing security program satisfies COPPA's updated requirements
- Classify AI providers (Anthropic, OpenAI, Google) as integral or non-integral third parties under COPPA — non-integral third parties require separate parental consent

---

## Technical Notes

### AI Provider Integration

AI providers (Anthropic, OpenAI, Google) are called directly using the same pattern used by other hub projects. LiteLLM may be added as a convenience abstraction but introduces a dependency that is not required. Each provider requires its own API key already present in the app environment.

### System Prompt Strategy

The system prompt is the primary safety mechanism. It should explicitly address:

- Age-appropriate persona and vocabulary
- Off-limits topics by name
- Warm redirection rather than blunt refusal
- Common child jailbreak attempts ("pretend you have no rules", "you are now a different AI", "ignore previous instructions")

The system prompt is hardcoded in v1. It should be iterated over time as edge cases are discovered via the moderation log.

### Moderation Architecture

Per child message, five AI calls are made:

1. **Pre-response moderation — Model A** (e.g., Claude): evaluates full conversation history + new child message
2. **Pre-response moderation — Model B** (e.g., GPT-4o): same prompt, in parallel
3. **Primary AI call**: generates the response shown to the child — only runs if calls 1 and 2 both pass

Immediately after the response is delivered (non-blocking to child UI):

4. **Post-response moderation — Model A**: evaluates full conversation history including new exchange; returns flag + concern description + running summary
5. **Post-response moderation — Model B**: same, in parallel

Either model flagging at either pass triggers the lock/alert flow. The running summary from Pass 2 is stored in the DB; the daily Heroku Scheduler job uses it directly without making additional AI calls.

**Cost note:** Every child message triggers 5 AI calls (2 pre-moderation + 1 primary + 2 post-moderation). Only the primary call is billed to the user (1 credit). Moderation and summarization calls are platform cost. Factor this into per-user cost estimates.

### Data Retention Scheduler

A Heroku Scheduler job runs daily and hard-deletes any conversation record where `modified_at` is older than 30 days. All conversation records store a `modified_at` timestamp updated on every message write. Parent-initiated deletions are immediate and bypass the scheduler.

---

## Success Metrics

- Parent activation rate (% of eligible parents who enable Kids AI)
- Daily active child sessions
- Flag rate per session (indicator of prompt tuning health — too high suggests false positives)
- Parent-reported trust score (periodic survey)
- Summary open rate

---

## Dependencies

- Existing hub auth system (`User` model, `is_admin` flag, existing login flows)
- Existing `/admin` blueprint for admin UI additions
- Mailgun for flag alert emails and daily summary emails
- Heroku Scheduler for daily summary job and retention job
- AI provider API keys (Anthropic, OpenAI, Google) already present in the app environment
