# Sports Schedules — Scheduled Emails Implementation Plan

This plan implements the weekly digest feature as specified in `ScheduledEmailsPRD.md`. Users select saved queries and receive one email per week (always Thursday) at a chosen hour in their timezone.

**Status:** Phase 1 ✅ Phase 2 ✅ Phase 3 ✅ Phase 4 ✅ Phase 5 ✅ Phase 6 (partial) ⬜

---

## ⚠️ Remaining / Important

| Item | Notes |
|------|-------|
| **Cron job** | Add `flask sports_schedules send_digests` to run **every hour** on Heroku/Render. Without this, no digest emails are sent. |
| **Manual testing** | Full flow (create digest → Thursday → receive email) still needs production verification. |
| **Credits display** | Plan called for "1 credit per weekly email • You have X credits" in the digest UI; not currently shown in the modal. |
| **Mobile** | Digest modal has `width: 90%`, `max-height: 85vh`, `overflow-y: auto` but no explicit `@media (max-width: 480px)` override like the NL modal. |

---

## Relevant Files

- `app/projects/sports_schedules/models.py` — Add `SportsScheduleScheduledDigest`, `SportsScheduleScheduledDigestQuery`
- `app/projects/sports_schedules/routes.py` — Digest API routes; update index route to pass digest data
- `app/projects/sports_schedules/commands.py` (new) — Flask CLI `flask sports_schedules send_digests`
- `app/projects/sports_schedules/email.py` (new) — `send_digest_email(digest, query_results)`
- `app/projects/sports_schedules/core/config_to_url.py` (new) — `config_to_url_params(config, base_url, anchor_date)` for "View full results" links
- `app/projects/sports_schedules/templates/sports_schedules/index.html` — Digest settings UI (or new digests template)
- `app/projects/sports_schedules/static/css/sports_schedules.css` — `ss-digest-*` styles
- `app/__init__.py` — Register CLI command
- `app/projects/sports_schedules/core/sample_queries.py` — `config_to_params()` for query execution
- `app/projects/sports_schedules/core/query_builder.py` — `build_sql()`
- `app/core/dolthub_client.py` — `DoltHubClient`
- `app/utils/email_service.py` — `send_email()`

### Notes

- All new CSS classes use the `ss-` prefix.
- User must run `flask db migrate` and `flask db upgrade` after Phase 1.
- Requires `MAILGUN_API_KEY`, `CUSTOM_DOMAIN`, `SENDER_EMAIL`, `BASE_URL` in env.
- Pattern follows `app/projects/reminders/` for cron + email.

---

## Phase 1: Models & Migration

### 1.1 Database Models

- [x] Add `SportsScheduleScheduledDigest` to `app/projects/sports_schedules/models.py`
  - [x] `id` — Integer primary key
  - [x] `user_id` — ForeignKey to `user.id`, unique (one digest per user), ondelete CASCADE
  - [x] `schedule_hour` — Integer, 5–22 (5am–10pm in 24h format)
  - [x] `enabled` — Boolean, default True
  - [x] `created_at` — DateTime, default utcnow
  - [x] `last_sent_at` — DateTime, nullable; set when email is successfully sent
  - [x] `__tablename__` = `sports_schedule_scheduled_digests`
  - [x] Relationship: `user = db.relationship('User', backref=...)`
  - [x] Index on `user_id`
- [x] Add `SportsScheduleScheduledDigestQuery` to same file
  - [x] `id` — Integer primary key
  - [x] `digest_id` — ForeignKey to `sports_schedule_scheduled_digests.id`, ondelete CASCADE
  - [x] `saved_query_id` — ForeignKey to `sports_schedule_saved_queries.id`, ondelete CASCADE (PRD: "remove from digest" when saved query deleted; CASCADE auto-removes digest_query row)
  - [x] `sort_order` — Integer, default 0 (display order in email)
  - [x] `__tablename__` = `sports_schedule_scheduled_digest_queries`
  - [x] Unique constraint on `(digest_id, saved_query_id)` to prevent duplicates
  - [x] Relationships: `digest`, `saved_query`
- [x] Import new models in `app/__init__.py` (if models are imported there; check existing pattern for `SportsScheduleSavedQuery`)

**Manual Testing 1.1:**
- [x] Ask user to run `flask db migrate -m "Add scheduled digest tables"`
- [x] Review migration file — check columns, unique constraints, CASCADE
- [x] Ask user to run `flask db upgrade`
- [x] Verify tables exist with correct schema

---

## Phase 2: Config-to-URL Helper & Email Module

### 2.1 Config to URL Params

- [x] Create `app/projects/sports_schedules/core/config_to_url.py`
  - [x] Define `config_to_url_params(config: dict, base_url: str = None, anchor_date: str = None) -> str`
  - [x] Accept optional `anchor_date` (YYYY-MM-DD) so "View full results" links use the same Thursday anchor as the digest; for relative date modes this ensures the link loads the correct date range
  - [x] When building params for URL: merge `anchor_date` into config (or use `config_to_params(config, anchor_date)` and serialize params) so the URL includes `anchor_date=...` for consistency
  - [x] Convert to query string matching `_parse_query_params()` expectations:
    - [x] `dimensions` → `dimensions=date,time,home_team,road_team`
    - [x] `filters` → `home_state=NJ` or `home_state=NJ,NY`; `either_team` → `either_team_1=X&either_team_2=Y`
    - [x] `date_mode`, `date_exact`, `date_start`, `date_end`, `date_year`, `date_n`, `anchor_date`, `count`, `limit`, `sort_column`, `sort_dir`
  - [x] Use `urllib.parse.urlencode` for safe encoding
  - [x] Return full URL: `{base_url}/sports-schedules?{query_string}` or just `?{query_string}` if base_url omitted
  - [x] Handle `either_team` array → `either_team_1`, `either_team_2` (first two elements)
- [ ] Add unit test or manual verification that URL produced loads the same query in the app

**Manual Testing 2.1:**
- [ ] Call `config_to_url_params(sample_config)` with a known config (e.g. from SAMPLE_QUERIES)
- [ ] Paste resulting URL in browser; verify query loads and runs correctly

---

### 2.2 Digest Email Function

- [x] Create `app/projects/sports_schedules/email.py`
  - [x] Define `send_digest_email(digest, query_results: list[dict]) -> None`
    - [x] `query_results`: list of `{"name": str, "rows": list, "count": bool, "url": str, "error": str | None}` per query
    - [x] Build subject: `Sports Schedules: Your weekly digest` (or similar)
    - [x] Build HTML body:
      - [x] Per query: query name, then either:
        - [x] If `count`: show "X games" (single number)
        - [x] Else: HTML table with columns from row keys (date, time, home_team, road_team, etc.), max 25 rows
        - [x] If `error`: show "Could not load [query name]: {error}"
        - [x] If empty rows and not count: show "No games found for [query name]"
      - [x] Each section: "View full results" link using `url` from query_results
    - [x] Footer: link to `/sports-schedules` (or digest settings)
    - [x] Use `ss-digest-*` class prefix for email styles (inline where needed for email clients)
    - [x] Build plain text fallback
  - [x] Call `send_email(to_email=digest.user.email, subject=..., text_content=..., html_content=...)`
  - [x] Raise on failure (caller handles)
  - [x] Use `BASE_URL` from env for links

**Manual Testing 2.2:**
- [ ] In Flask shell: create a digest with 1–2 saved queries, build mock `query_results`, call `send_digest_email`
- [ ] Verify email arrives with correct structure, table renders, links work
- [ ] Test with empty rows, count query, and error case

---

## Phase 3: CLI Command (Send Digests)

### 3.1 Cron Command Logic

- [x] Create `app/projects/sports_schedules/commands.py`
  - [x] Flask CLI group: `flask sports_schedules` with subcommand `send_digests`
  - [x] `@with_appcontext` on command
  - [x] Logic:
    1. [x] Get `now = datetime.utcnow()`
    2. [x] Query all `SportsScheduleScheduledDigest` where `enabled=True`, join `user`, join `digest_queries` → `saved_query`
    3. [x] Filter to digests with ≥1 `SportsScheduleScheduledDigestQuery` whose `saved_query` exists and belongs to same user
    4. [x] For each digest:
       - [x] Convert `now` to user's `time_zone` (use `zoneinfo.ZoneInfo`)
       - [x] If weekday != 3 (Thursday), skip
       - [x] If `current_hour` not in `[schedule_hour-1, schedule_hour, schedule_hour+1]`, skip (handle 5→4 and 22→23 boundaries)
       - [x] Check `last_sent_at`: convert to user TZ; if same calendar date as user's "today" (Thursday), skip (already sent this week)
       - [x] Check `user.credits >= 1` and `user.email_verified`; if not, skip
       - [x] For each digest query (by sort_order): load saved_query, run query (see 3.2), collect results into `query_results`
       - [x] If `query_results` is non-empty (we processed ≥1 query — includes errors/empty; PRD: always send when we have queries to report), call `send_digest_email(digest, query_results)`
       - [x] On success: set `digest.last_sent_at = utcnow()`, deduct 1 credit, commit
       - [x] On failure: log error, rollback, continue to next digest
    5. [x] Print summary: N sent, N failed, N skipped (with reasons)
  - [x] Register in `app/__init__.py` via `init_app` pattern (like reminders)

**Manual Testing 3.1:**
- [ ] Create digest for test user with schedule_hour = current hour (or next hour) on a Thursday
- [ ] Set user timezone to match local; ensure 1+ saved query in digest
- [ ] Run `flask sports_schedules send_digests`
- [ ] Verify email arrives, `last_sent_at` set, credit deducted
- [ ] Run command again immediately — verify no second email (dedup works)
- [ ] Set user credits to 0, run — verify skipped
- [ ] Set digest to different day (or change system time) — verify skipped when not Thursday

---

### 3.2 Query Execution in Command

- [x] For each `SportsScheduleScheduledDigestQuery` in digest (ordered by sort_order):
  - [x] Load `saved_query` (skip if deleted/orphaned)
  - [x] Parse config: `config = json.loads(saved_query.config)` if str
  - [x] Compute anchor: `thursday_ymd = user_local_now.strftime("%Y-%m-%d")` (user's Thursday date)
  - [x] Params: `params = config_to_params(config, anchor_date=thursday_ymd)`
  - [x] Override: `params["limit"] = 25`
  - [x] Build SQL: `sql, err = build_sql(params)`; if err, add `{"name": ..., "error": err, "rows": [], "url": ...}` and continue
  - [x] Execute: `DoltHubClient().execute_sql(sql)`; if `"error" in result`, add error entry and continue
  - [x] Rows: `rows = result.get("rows", [])[:25]` (cap at 25)
  - [x] URL: `config_to_url_params(config, base_url, anchor_date=thursday_ymd)` — PRD requires anchor in URL so "View full results" shows same date range
  - [x] Add `{"name": saved_query.name, "rows": rows, "count": params.get("count", False), "url": url, "error": None}` to query_results
- [x] If `count` is True: rows may have one row with count; format as "X games" in email

**Manual Testing 3.2:**
- [ ] Verify "this_weekend" query with Thursday anchor yields Fri–Sun
- [ ] Verify DoltHub failure on one query skips that section, others still send
- [ ] Verify 25-row cap applied
- [ ] Verify "View full results" URL runs same query in browser

---

## Phase 4: API Routes for Digest Management

### 4.1 GET Digest (for UI)

- [x] Add `GET /sports-schedules/api/digest` in `routes.py`
  - [x] Require login; return 401 if not authenticated
  - [x] Query `SportsScheduleScheduledDigest` for `current_user.id`
  - [x] If none, return `{"digest": null}`
  - [x] If exists: return `{"digest": {"id", "schedule_hour", "enabled", "last_sent_at", "query_ids": [saved_query_id, ...]}}`
  - [x] `query_ids` from `SportsScheduleScheduledDigestQuery` for this digest, ordered by sort_order

**Manual Testing 4.1:**
- [ ] Logged out: GET → 401
- [ ] Logged in, no digest: GET → `{"digest": null}`
- [ ] Create digest via shell; GET → correct structure

---

### 4.2 PUT Digest (create or update)

- [x] Add `PUT /sports-schedules/api/digest` in `routes.py`
  - [x] Require login; 401 if not authenticated
  - [x] Validate `user.email_verified`; if not, return 400 `{"error": "Verify your email to use weekly digests"}`
  - [x] Parse JSON: `schedule_hour` (required, 5–22), `enabled` (bool), `query_ids` (list of saved_query ids)
  - [x] Validate `schedule_hour` in range
  - [x] Validate each `query_id` belongs to `current_user` (query `SportsScheduleSavedQuery` by id and user_id)
  - [x] If `query_ids` empty and `enabled` True: return 400 `{"error": "Select at least one saved query"}`
  - [x] Upsert: get or create `SportsScheduleScheduledDigest` for user
    - [x] On create: use `schedule_hour`, `enabled`, `query_ids` from request (default `schedule_hour=8` if omitted)
    - [x] On update: apply same fields
  - [x] Replace digest queries: delete existing `SportsScheduleScheduledDigestQuery` for this digest; insert new ones with sort_order from list order
  - [x] Commit, return `{"digest": {...}}` same shape as GET

**Manual Testing 4.2:**
- [ ] PUT with valid data — digest created or updated
- [ ] PUT with query_ids from another user — 400 or ignore those ids
- [ ] PUT with empty query_ids and enabled=true — 400
- [ ] PUT with schedule_hour=25 — 400
- [ ] User with unverified email — 400

---

### 4.3 CSRF

- [x] Use same CSRF pattern as saved-queries: client sends `X-CSRFToken` header; ensure PUT is not exempted (use default CSRF for API if applicable)

---

## Phase 5: UI for Digest Settings

### 5.1 Digest Section Markup

- [x] Add digest settings section to `sports_schedules/index.html` (or create `digests.html` if separate page)
  - [x] Only visible when `is_authenticated`
  - [x] Place below or near Saved Queries — **implemented as modal** ("Email digest" button in Saved Queries header)
  - [x] Section: "Weekly email digest"
  - [x] Toggle: Enable/disable digest (`ss-digest-enabled-toggle`)
  - [x] Hour dropdown: 5am–10pm options (`ss-digest-hour-select`), values 5–22
  - [x] Checkboxes: list of user's saved queries (`ss-digest-query-checkbox`), each with query name
  - [x] Save button (`ss-digest-save-btn`)
  - [x] Message: "Emails go out every Thursday. Select at least one saved query."
  - [x] If `user.email_verified` is False: show "Verify your email to use weekly digests" and disable form
  - [ ] Credits display: "1 credit per weekly email • You have X credits" — **not in modal**
- [x] Update index route to pass `digest` (or fetch via API on load) and `saved_queries` for checkboxes

**Manual Testing 5.1:**
- [ ] Logged in: digest section visible
- [ ] Logged out: section hidden
- [ ] Hour dropdown has 5am–10pm
- [ ] Checkboxes show user's saved queries only
- [ ] Unverified email: form disabled with message

---

### 5.2 Digest Section JavaScript

- [x] On page load (when authenticated): fetch `GET /sports-schedules/api/digest`
  - [x] If digest exists: set toggle, hour, checkboxes from `query_ids`
  - [x] If null: show defaults (enabled=false, hour=8, no checkboxes)
- [x] On Save click:
  - [x] Collect: enabled, schedule_hour, checked query ids
  - [x] Validate: if enabled and no query ids, show alert
  - [x] PUT to `/sports-schedules/api/digest` with JSON body
  - [x] On success: show "Saved" or update UI
  - [x] On error: show error message
- [x] Use `X-CSRFToken` header from `meta[name="csrf-token"]`

**Manual Testing 5.2:**
- [ ] Load page, change settings, Save — verify PUT succeeds
- [ ] Enable with no queries selected — validation error
- [ ] Create digest, refresh — settings persist

---

### 5.3 Styles

- [x] Add `ss-digest-*` styles in `sports_schedules.css`
  - [x] Section container, toggle, dropdown, checkbox list, save button
  - [x] Modal styles (ss-digest-modal, backdrop, box); mobile-friendly (width: 90%, max-height: 85vh)

**Manual Testing 5.3:**
- [ ] Digest section looks correct on desktop and mobile

---

## Phase 6: Scheduler Setup & Polish

### 6.1 Register Cron Command

- [x] In `app/__init__.py` (or wherever reminders CLI is registered): import and call `init_app` from `app/projects/sports_schedules/commands.py`
- [x] Verify `flask sports_schedules send_digests` runs and shows help

**Manual Testing 6.1:**
- [ ] `flask sports_schedules send_digests` — runs without error (may send 0 if no digests due)

---

### 6.2 Scheduler Configuration (Heroku/Render)

- [ ] Add cron job: `flask sports_schedules send_digests` every hour
- [ ] Document in README or deployment notes

**Manual Testing 6.2:**
- [ ] On production: create digest for Thursday 8am (user TZ), wait for cron
- [ ] Verify email arrives within ~1 hour of expected time

---

### 6.3 Edge Cases & Polish

- [ ] Deleted saved query: PRD allowed "skip" or "remove from digest"; we use CASCADE (remove). When user deletes a saved query, `SportsScheduleScheduledDigestQuery` rows with that `saved_query_id` are CASCADE deleted. Verify digest still works if other queries remain.
- [ ] Count queries: verify `count=True` saved queries display as "X games" in email
- [ ] Empty digest: if user removes all queries, digest has 0 digest_queries; cron skips (no send)
- [ ] Timezone edge: user in UTC+12; Thursday 10pm in their TZ = schedule_hour 22; verify window 21–23 (9pm–11pm) works. When it's Friday 12am (hour 0) in user TZ, skip (no longer Thursday).
- [ ] Default hour: when creating digest, use 8 (8am) as default

**Manual Testing 6.3:**
- [ ] Delete a saved query that's in a digest — verify digest still sends with remaining queries (or CASCADE removes it)
- [ ] Create count-type saved query, add to digest — verify email shows "X games"
- [ ] Full flow: create digest → wait for Thursday → receive email → verify links work
- [ ] Verify no regressions to saved queries, sample queries, or main query builder

---

## Summary Checklist

- [x] Phase 1: Models + migration
- [x] Phase 2: Config-to-URL helper + email module
- [x] Phase 3: CLI send_digests command
- [x] Phase 4: API routes (GET/PUT digest)
- [x] Phase 5: UI (digest modal via "Email digest" button, JS, styles)
- [ ] Phase 6: Scheduler registration ✅ + **cron job** ⬜ + edge cases
- [x] All CSS uses `ss-` prefix
- [x] Credits checked before send; 1 credit deducted per digest
- [x] `last_sent_at` deduplication works
- [x] Thursday + hour window logic correct
