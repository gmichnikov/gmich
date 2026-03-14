# Sports Schedules — Scheduled Emails PRD

## Overview

Add **scheduled email digests** to Sports Schedules. Users select a subset of their saved queries and receive **one email per week** — always on **Thursday** — at a chosen hour in their timezone. The email contains the live results of those queries. Example: "Every Thursday at 8am, send me the results of 'Games in NJ this weekend' and 'Celtics this month'."

---

## Current Capabilities (Existing in Codebase)

### Saved Queries (`SportsScheduleSavedQuery`)

- **Model:** `user_id`, `name`, `config` (JSON), `created_at`
- **Config structure:** Same as URL params — `dimensions`, `filters`, `date_mode`, `date_exact`, `date_start`/`date_end`, `date_year`, `date_n`, `anchor_date`, `count`, `limit`, `sort_column`, `sort_dir`
- **Relative date modes:** `this_weekend`, `next_week`, `next_n`, `last_n`, `future` — anchor is computed at runtime via `config_to_params(anchor_date=...)`
- **Execution:** `config_to_params()` → `build_sql()` → `DoltHubClient.execute_sql()` → rows
- **Limit:** 20 saved queries per user

### Email Service (`app.utils.email_service`)

- **`send_email(to_email, subject, text_content, html_content=None)`** — Mailgun API
- Requires env: `MAILGUN_API_KEY`, `CUSTOM_DOMAIN`, `SENDER_EMAIL`
- **Pattern from reminders:** HTML emails with consistent styling, links back to the app

### Scheduling Infrastructure (Reminders Project)

- **Flask CLI:** `flask reminders send` runs on Render Cron every 5–10 minutes
- **Pattern:** Query for items due in a time window → send email → set `sent_at`, deduct credits
- **Credits:** Each send costs 1 credit; users with 0 credits are skipped
- **User fields:** `email`, `time_zone` (stored in `User` model)

---

## User Stories

1. **As a logged-in user with saved queries**, I can opt in to the weekly digest and choose which of my saved queries to include.
2. **As a user who sets a schedule**, I pick an hour (5am–10pm) in my timezone. I receive one email every Thursday around that time.
3. **As a user receiving the email**, I see each query's name, a table of results (up to 25 rows per query), and a link to open each query in the app for full results.

---

## Requirements

### Core Concept

- **One digest per user** — one email per week, always on Thursday
- User chooses **hour only** (5am–10pm) in their timezone
- Digest = user + list of saved query IDs + schedule_hour + enabled flag
- At send time, for each selected query:
  - Use `config_to_params(anchor_date=thursday_in_user_tz)` so relative dates (e.g. `this_weekend`) are computed from Thursday
  - Run `build_sql()` → DoltHub → get rows
  - Include results in the email (HTML table, max 25 rows per query)
- **Sample queries do not count** — digests only reference user's saved queries. If a user has no saved queries selected, they do not receive an email.

### Schedule Definition

- **Day:** Always Thursday (fixed)
- **Time:** User picks hour only (5am–10pm local) — stored as 5–22 in 24h format (5=5am, 22=10pm)
- **Cron:** Scheduler (Heroku or Render — same as reminders) runs `flask sports_schedules send_digests` every hour
- **Send logic:** For each user with an enabled digest that has ≥1 saved query:
  - Convert current UTC time to user's `time_zone`
  - If it's Thursday AND the current hour (in user TZ) is within ±1 of their chosen hour → send
  - Example: user chose 8am → send if cron runs when it's 7am, 8am, or 9am Thursday in their TZ
- **Deduplication:** Store `last_sent_at` on the digest. Before sending, check: have we already sent "this Thursday" (in user TZ)? If `last_sent_at` converted to user TZ falls on the same Thursday, skip. This ensures at most one email per week per user even if cron runs multiple times in the window.

### Anchor Date

- **Always Thursday** in the user's timezone at send time
- For `date_mode: "this_weekend"`, Thursday anchor correctly yields Fri–Sun of that week
- `config_to_params(config, anchor_date=thursday_ymd_in_user_tz)`

### Data Model

```
SportsScheduleScheduledDigest
  - id
  - user_id (FK, unique — one digest per user)
  - schedule_hour (5-22, local time in user's time_zone)
  - enabled (boolean, default True)
  - created_at
  - last_sent_at (nullable) — set when email is successfully sent

SportsScheduleScheduledDigestQuery (join table)
  - digest_id (FK)
  - saved_query_id (FK)
  - sort_order (int) — display order in email
```

- Digest references only `SportsScheduleSavedQuery` rows (user's own saved queries)
- If user deletes a saved query that's in a digest, skip that query when sending (or remove from digest — TBD)

### Query Execution at Send Time

- **Params:** `config_to_params(config, anchor_date=thursday_ymd_in_user_tz)`
- **Row limit:** Override to **25** for all queries in the email, regardless of the saved query's `limit`
- **DoltHub failure:** If one query fails (e.g. DoltHub error), skip that query's section and continue with the others. Do not fail the whole digest.
- **Empty results:** Show "No games found for [query name]" rather than omitting the section

### Links to Open Queries

- Build the URL from the stored config params (same structure as URL query params)
- Each query section in the email includes a link: "View full results" → `/sports-schedules?dimensions=...&filters=...&date_mode=...` etc.
- User can get full row count in the app; email caps at 25 for readability

### Email Content

- **Subject:** e.g. `Sports Schedules: Your weekly digest` or `Your sports schedule for this weekend`
- **Body per query:** Query name + table of dimensions (date, time, home_team, road_team, etc.) + "View full results" link
- **Footer:** Link to `/sports-schedules` and to manage digest settings

### Credits

- 1 credit per digest send (aligned with reminders)
- Users with 0 credits: skip send
- Only allow scheduling if `user.email_verified`

### Management UI

- **Where:** New section on sports-schedules index when logged in, or `/sports-schedules/digests`
- **Actions:** Enable/disable digest, choose hour (5am–10pm dropdown), select which saved queries to include (checkboxes)
- **Validation:** User can only attach their own saved queries
- **Requirement:** Digest must have ≥1 saved query to be valid. If user removes all queries, no email is sent.

---

## Out of Scope (Initial)

- User-chosen day (always Thursday)
- Minute-level precision (hour only)
- Multiple digests per user
- Sample queries in digest (only user's saved queries)
- SMS or other channels
- Unsubscribe link (could add later for compliance)

---

## Technical Dependencies

| Component           | Source                                         |
|---------------------|------------------------------------------------|
| Query execution     | `config_to_params`, `build_sql`, `DoltHubClient`|
| Email sending       | `app.utils.email_service.send_email`           |
| Cron pattern        | `app.projects.reminders.commands` (`flask reminders send`) |
| User email/TZ       | `User.email`, `User.time_zone`                 |
| Credits             | `User.credits`, `User.deduct_credits()`       |

---

## Next Steps

1. Finalize data model and migrations
2. Implement `flask sports_schedules send_digests` CLI command
3. Build digest management UI (enable, hour picker, query checkboxes)
4. Design HTML email template with `ss-`-prefixed classes (per project CSS convention)
5. Add Heroku scheduler cron job for the send command
6. Document schedule semantics for users (Thursday, anchor = "this weekend")
