# Daily Email — Implementation Plan

This plan follows the PRD phases but breaks them into small, testable chunks.  
**Module build order:** Weather first (simplest fetch, proves email plumbing) → Mailgun / scheduler / send infrastructure → Stocks → Sports → Ashby Jobs.

---

## Relevant Files

- `app/projects/daily_email/__init__.py` — module docstring / package marker
- `app/projects/daily_email/routes.py` — Flask blueprint, settings + preview routes
- `app/projects/daily_email/models.py` — all DB models (new)
- `app/projects/daily_email/commands.py` — `flask daily_email send` CLI command (new)
- `app/projects/daily_email/email_builder.py` — assembles HTML digest from module results (new)
- `app/projects/daily_email/modules/weather.py` — Open-Meteo fetch + geocode (new)
- `app/projects/daily_email/modules/stocks.py` — yfinance fetch (new)
- `app/projects/daily_email/modules/sports.py` — ESPN fetch + filter (new)
- `app/projects/daily_email/modules/jobs.py` — Ashby fetch + filter (new)
- `app/projects/daily_email/templates/daily_email/index.html` — settings / dashboard page (existing, expand)
- `app/projects/daily_email/static/daily_email.css` — styles using `de-` prefix (existing, expand)
- `app/__init__.py` — register commands (needs update when commands added)

### Notes

- CSS classes use `de-` prefix throughout to avoid cross-project collisions.
- All new DB models go in `models.py`; import them in `app/__init__.py` so Flask-Migrate sees them.
- Credit logic mirrors Reminders exactly: decrement `user.credits` by 1 **after** Mailgun returns 2xx.
- Timezone is always read from `User.time_zone` (IANA string, same as Reminders).
- No migration files are created manually — ask user to run `flask db migrate / upgrade`.

---

## Phase 1: Weather Module + Database Models

### 1.1 Database Models

- [ ] Create `app/projects/daily_email/models.py`
  - [ ] `DailyEmailProfile` — per-user digest master record
    - [ ] `id`, `user_id` (FK → `user.id`, unique), `digest_enabled` (Boolean, default False)
    - [ ] `send_hour_local` (Integer 0–23, default 6)
    - [ ] `include_weather` (Boolean, default True)
    - [ ] `include_stocks` (Boolean, default True)
    - [ ] `include_sports` (Boolean, default True)
    - [ ] `include_jobs` (Boolean, default True)
    - [ ] `created_at`, `updated_at`
    - [ ] `__repr__`
  - [ ] `DailyEmailWeatherLocation` — up to 3 per user
    - [ ] `id`, `user_id` (FK), `display_label` (String 100), `lat` (Float), `lon` (Float)
    - [ ] `sort_order` (Integer), `created_at`
    - [ ] `__repr__`
  - [ ] `DailyEmailStockTicker` — up to 10 per user
    - [ ] `id`, `user_id` (FK), `symbol` (String 20), `sort_order` (Integer), `created_at`
    - [ ] `__repr__`
  - [ ] `DailyEmailSportsWatch` — up to 10 per user
    - [ ] `id`, `user_id` (FK), `league_code` (String 10, e.g. "NBA"), `espn_team_id` (String 20), `team_display_name` (String 80)
    - [ ] `sort_order` (Integer), `created_at`
    - [ ] `__repr__`
  - [ ] `DailyEmailJobsConfig` — 1 per user
    - [ ] `id`, `user_id` (FK → `user.id`, unique)
    - [ ] `ashby_slug` (String 255, nullable), `filter_phrase` (String 100, nullable)
    - [ ] `created_at`, `updated_at`
    - [ ] `__repr__`
  - [ ] `DailyEmailSendLog` — one row per successful/attempted send
    - [ ] `id`, `user_id` (FK), `digest_local_date` (Date)
    - [ ] `status` (String 20: `sent`, `failed`, `no_credits`)
    - [ ] `modules_included` (String 100, comma-separated, nullable)
    - [ ] `error_summary` (String 500, nullable)
    - [ ] `sent_at` (DateTime, nullable — set on success)
    - [ ] `created_at` (DateTime, default utcnow)
    - [ ] Unique constraint on `(user_id, digest_local_date)` — idempotency anchor
    - [ ] `__repr__`
- [ ] Import all models in `app/__init__.py` under the existing model imports

**Manual Testing 1.1:**
- [ ] Ask user to run `flask db migrate -m "Add daily email models"`
- [ ] Review migration file (all 6 tables, unique constraints on `user_id` for Profile/JobsConfig, composite unique on SendLog)
- [ ] Ask user to run `flask db upgrade`
- [ ] Confirm all tables exist with correct schema

---

### 1.2 Weather Module

- [ ] Create `app/projects/daily_email/modules/` directory with `__init__.py`
- [ ] Create `app/projects/daily_email/modules/weather.py`
  - [ ] `geocode_location(query: str) -> dict | None`
    - [ ] Call Open-Meteo Geocoding API: `https://geocoding-api.open-meteo.com/v1/search?name={query}&count=1`
    - [ ] Return `{"lat": float, "lon": float, "label": str}` or `None` on failure
    - [ ] Timeout: 5s; log errors; return None on any exception
  - [ ] `fetch_weather(lat: float, lon: float) -> dict | None`
    - [ ] Call Open-Meteo forecast: `https://api.open-meteo.com/v1/forecast`
    - [ ] Params: `latitude`, `longitude`, `daily` (temperature_2m_max, temperature_2m_min, precipitation_probability_max, weathercode), `current_weather=true`, `forecast_days=7`, `temperature_unit=fahrenheit`, `timezone=auto`
    - [ ] Return structured dict: `{"today": {...}, "week": [...]}`
    - [ ] Timeout: 8s; return None on any exception
  - [ ] `render_weather_section(locations: list[DailyEmailWeatherLocation]) -> str | None`
    - [ ] For each location, call `fetch_weather(lat, lon)` (up to 3)
    - [ ] Return HTML string for this module's card; return None if all fetches fail
    - [ ] Include location display label, today's high/low/precip, 7-day strip

**Manual Testing 1.2:**
- [ ] In Python shell: `from app.projects.daily_email.modules.weather import geocode_location, fetch_weather`
- [ ] Test `geocode_location("Denver, CO")` — returns lat/lon/label
- [ ] Test `geocode_location("80202")` — ZIP lookup works
- [ ] Test `fetch_weather(39.74, -104.99)` — returns structured dict
- [ ] Inspect `today` and `week` keys present

---

## Phase 2: Email Infrastructure + First Working Send

### 2.1 Email Builder

- [ ] Create `app/projects/daily_email/email_builder.py`
  - [ ] `build_digest_html(user, profile, module_results: dict) -> str`
    - [ ] Module results: `{"weather": html_or_none, "stocks": html_or_none, "sports": html_or_none, "jobs": html_or_none}`
    - [ ] Fixed section order: weather → stocks → sports → jobs (skip if None **and** module not enabled, or show error card if enabled but failed)
    - [ ] "Error card" copy: e.g. "Weather temporarily unavailable"
    - [ ] If all modules are None: include single "nothing loaded" card with link to settings
    - [ ] Single-column responsive HTML email with `de-` CSS classes; dark header with date + greeting; one card per enabled module; footer with manage preferences link
    - [ ] Return complete `<!DOCTYPE html>` string
  - [ ] `build_subject(user) -> str`
    - [ ] e.g. `"Your morning digest — Thursday, Apr 23"`

**Manual Testing 2.1:**
- [ ] Call `build_digest_html(user, profile, {"weather": "<p>test</p>", ...})` in Python shell
- [ ] Verify valid HTML returned; check header and footer present

---

### 2.2 Send Command (Weather-only first pass)

- [ ] Create `app/projects/daily_email/commands.py`
  - [ ] `init_app(app)` registers the CLI group
  - [ ] `@click.group(name="daily_email")` → `daily_email_cli`
  - [ ] `flask daily_email send` command
    - [ ] Query all users with `DailyEmailProfile.digest_enabled == True`
    - [ ] For each user compute `now_local` using `ZoneInfo(user.time_zone or "UTC")`
    - [ ] Compute `local_date = now_local.date()`, `local_hour = now_local.hour`
    - [ ] **Due check:** `local_hour == profile.send_hour_local`
    - [ ] **Already sent check:** `EXISTS DailyEmailSendLog(user_id, digest_local_date=local_date, status="sent")`
    - [ ] **Credits check:** `user.credits >= 1`
    - [ ] If all pass: **claim row** — `INSERT INTO daily_email_send_log (user_id, digest_local_date, status, created_at) VALUES (..., 'pending')` (or skip if conflict on unique key)
    - [ ] Fetch modules in parallel using `ThreadPoolExecutor` (weather only at this phase)
    - [ ] Build digest HTML
    - [ ] Call `send_email(to=user.email, subject=..., html=...)` (existing hub Mailgun util)
    - [ ] On Mailgun 2xx: update log row `status="sent", sent_at=now`, decrement `user.credits -= 1`, commit
    - [ ] On failure: update log row `status="failed"`, roll back credit, log error
    - [ ] Print summary: `N sent, N failed, N skipped`
  - [ ] `flask daily_email send_test --email <addr>` subcommand
    - [ ] Accepts `--user-id` or `--email` to identify user
    - [ ] Builds and sends one digest immediately regardless of schedule/hour
    - [ ] Deducts one credit same as real send
    - [ ] Does **not** insert a send log row (so scheduled send still fires later that day)
- [ ] Register `init_daily_email_commands` in `app/__init__.py`

**Manual Testing 2.2:**
- [ ] Manually create a `DailyEmailProfile` row (or via Python shell) with `digest_enabled=True`, `send_hour_local` set to current local hour, enough credits
- [ ] Add a `DailyEmailWeatherLocation` row for that user
- [ ] Run `flask daily_email send` — email should arrive
- [ ] Check `DailyEmailSendLog` row inserted with `status="sent"`
- [ ] Check `user.credits` decremented by 1
- [ ] Run `flask daily_email send` again same hour — should skip (already sent today)
- [ ] Run `flask daily_email send_test --email <your@email.com>` — email arrives, credits decremented

---

### 2.3 Settings UI — Phase 1 (Digest On/Off + Weather)

- [ ] Expand `routes.py`
  - [ ] `GET /daily-email/` — dashboard: show profile status, last sent, next scheduled, link to settings
    - [ ] Create `DailyEmailProfile` row if none exists for user (with defaults)
  - [ ] `GET /daily-email/settings` — tabbed settings form
  - [ ] `POST /daily-email/settings` — save profile (on/off, send_hour_local, module toggles)
  - [ ] `POST /daily-email/settings/weather/add` — geocode query → save `DailyEmailWeatherLocation`
    - [ ] Server-side: reject if ≥ 3 locations already; validate geocode succeeds
    - [ ] Flash error if geocode fails ("Location not found — try a city name or ZIP")
  - [ ] `POST /daily-email/settings/weather/delete/<id>` — remove location
  - [ ] `POST /daily-email/preview` — builds email HTML in memory, returns rendered page (no send, no credit)
- [ ] Update `templates/daily_email/index.html` — dashboard view
  - [ ] Greeting + project description
  - [ ] Digest status card: on/off, send time in user's timezone, credits remaining
  - [ ] "Last sent" / "Next expected send" summary
  - [ ] Link to full settings page; Preview button
- [ ] Create `templates/daily_email/settings.html`
  - [ ] **Digest toggle:** on/off
  - [ ] **Send time:** hour picker 0–23 with timezone label (from `User.time_zone`), note about ~1-hour window
  - [ ] **Weather section:** toggle, location list, "Add location" search box, delete buttons
  - [ ] Module toggles for stocks/sports/jobs (grayed out / "coming soon" at this phase, or hidden)
  - [ ] Save button, flash messages
- [ ] `app/projects/daily_email/static/daily_email.css` — expand with `de-` prefixed styles
  - [ ] Settings form layout, location cards, toggle switches, module section headers

**Manual Testing 2.3:**
- [ ] Navigate to `/daily-email/` — dashboard loads
- [ ] Go to settings, toggle digest on, set send hour, save — changes persist
- [ ] Add a weather location — geocode works, location appears in list
- [ ] Try adding a 4th location — blocked with flash error
- [ ] Delete a location — removed
- [ ] Click Preview — email HTML renders in page (no send)
- [ ] Check timezone label shown next to send time picker

---

## Phase 3: Stocks Module

### 3.1 Stocks Fetch

- [ ] Create `app/projects/daily_email/modules/stocks.py`
  - [ ] `validate_ticker(symbol: str) -> bool`
    - [ ] Call `yfinance.Ticker(symbol).fast_info`; return True if `regularMarketPrice` present
    - [ ] Timeout via `concurrent.futures` with 5s; return False on exception
  - [ ] `fetch_stocks(tickers: list[str]) -> list[dict] | None`
    - [ ] Call `yfinance.download(tickers, period="2d", interval="1d")` or individual `.history()`
    - [ ] Return list of `{"symbol": str, "price": float, "change": float, "pct_change": float}` per ticker
    - [ ] Return None if all tickers fail; partial results OK
  - [ ] `render_stocks_section(tickers: list[DailyEmailStockTicker]) -> str | None`
    - [ ] Up to 10 tickers; return HTML card with table rows

### 3.2 Stocks Settings UI

- [ ] Add to `routes.py`:
  - [ ] `POST /daily-email/settings/stocks/add` — validate ticker server-side, save row, reject if ≥ 10 or invalid symbol
  - [ ] `POST /daily-email/settings/stocks/delete/<id>` — remove ticker
- [ ] Add stocks section to `settings.html`:
  - [ ] Toggle, ticker list, add form with symbol input, server-side validation error display
  - [ ] Note: "Data from Yahoo Finance; unofficial, may be delayed"

**Manual Testing 3.2:**
- [ ] Add valid ticker (AAPL) — saved, appears in list
- [ ] Add invalid ticker (NOTREAL123) — inline error, not saved
- [ ] Add 11th ticker — blocked
- [ ] Enable stocks, run `flask daily_email send_test` — email includes stocks card
- [ ] Disable stocks — stocks card absent from preview

---

## Phase 4: Sports Scores Module

### 4.1 Sports Fetch

- [ ] Create `app/projects/daily_email/modules/sports.py`
  - [ ] Reuse `app/projects/sports_scores/core/espn_parser.py` — import `SUPPORTED_LEAGUES`, `LEAGUE_TO_SPORT_KEY`, `parse_scoreboard`
  - [ ] Reuse `app/projects/sports_scores/core/scores_service.py` — import `fetch_scoreboard_for_sport` (or mirror the ESPN fetch call)
  - [ ] `fetch_sports_for_digest(watches: list[DailyEmailSportsWatch], user_tz: str) -> str | None`
    - [ ] Compute yesterday and today in `user_tz` using `ZoneInfo`
    - [ ] Collect distinct `league_code`s from watches
    - [ ] For each league: call ESPN scoreboard once with `dates=YYYYMMDD-YYYYMMDD`
    - [ ] Filter games where home or away team matches any watched `espn_team_id`
    - [ ] Cap at 25 game rows; add "+ N more" note if truncated
    - [ ] Return HTML card with game rows (score if final, "in progress" / "scheduled" label otherwise)

### 4.2 Sports Settings UI

- [ ] `GET /daily-email/settings/sports/teams` (or AJAX) — return list of teams for a given league
  - [ ] Reuse `ESPNClient.fetch_teams(sport_key)` or equivalent from `sports_schedule_admin`
- [ ] Add to `routes.py`:
  - [ ] `POST /daily-email/settings/sports/add` — add watch (league + team), reject if ≥ 10
  - [ ] `POST /daily-email/settings/sports/delete/<id>` — remove watch
- [ ] Add sports section to `settings.html`:
  - [ ] Toggle, watch list (league + team name), league dropdown → team dropdown → Add button
  - [ ] Leagues: NFL, NBA, MLB, NHL only (v1)

**Manual Testing 4.2:**
- [ ] Add a sports watch (e.g. NBA + Lakers) — saved
- [ ] Add 11th watch — blocked
- [ ] Run `flask daily_email send_test` — email includes sports card with recent games
- [ ] Disable sports — card absent from preview
- [ ] Verify games filtered to watched teams only (not all league games)

---

## Phase 5: Ashby Jobs Module

### 5.1 Jobs Fetch

- [ ] Create `app/projects/daily_email/modules/jobs.py`
  - [ ] `parse_slug_from_input(raw: str) -> str | None`
    - [ ] Accept either a slug string or a URL like `jobs.ashbyhq.com/{slug}` / `{org}.ashbyhq.com`
    - [ ] Return extracted slug or None if unrecognizable
  - [ ] `fetch_ashby_jobs(slug: str, filter_phrase: str | None) -> list[dict] | None`
    - [ ] Call `https://api.ashbyhq.com/posting-api/job-board/{slug}`; timeout 10s
    - [ ] If filter_phrase: case-insensitive substring match on `title` (and `department` if present)
    - [ ] Return list of `{"title": str, "url": str, "team": str|None, "location": str|None}`, max 12
    - [ ] Return None on network failure; return `[]` if response OK but no matches
  - [ ] `render_jobs_section(config: DailyEmailJobsConfig) -> str | None`
    - [ ] Return None if `ashby_slug` is empty
    - [ ] If fetch fails: return error card HTML
    - [ ] If `[]` results: return "No matching roles" card or omit section (product choice: omit)
    - [ ] Otherwise: return card with up to 12 job rows + "see full board" link

### 5.2 Jobs Settings UI

- [ ] Add to `routes.py`:
  - [ ] `POST /daily-email/settings/jobs/save` — save slug + filter phrase; validate slug via live Ashby call; reject if invalid (flash error "Could not find that job board")
  - [ ] `POST /daily-email/settings/jobs/delete` — clear slug/filter
- [ ] Add jobs section to `settings.html`:
  - [ ] Toggle, URL/slug input, optional filter phrase input (max 100 chars)
  - [ ] After save, show current slug + last-known company name (from Ashby response label)
  - [ ] "Test" button that previews matched jobs inline (no email, no credit)

**Manual Testing 5.2:**
- [ ] Paste valid Ashby URL — slug extracted, validation call made, saved
- [ ] Paste bad URL — inline error shown, not saved
- [ ] Paste valid slug with filter phrase — jobs filtered by title substring
- [ ] Run `flask daily_email send_test` — email includes jobs card with ≤ 12 rows
- [ ] Set filter that matches 0 jobs — section omitted from email
- [ ] Disable jobs — section absent from preview

---

## Phase 6: Full Integration + Polish

### 6.1 Parallel Fetches in Send Command

- [ ] Update `commands.py` `send` command to fetch all four modules in parallel
  - [ ] Use `ThreadPoolExecutor(max_workers=4)` — one thread per module
  - [ ] Each module call has its own try/except; failure returns None (does not block others)
  - [ ] Log per-module timing for observability

**Manual Testing 6.1:**
- [ ] With all 4 modules enabled, run `flask daily_email send_test`
- [ ] Confirm all 4 sections in email
- [ ] Temporarily break weather URL in test — verify email still sends with other 3 modules + weather error card

---

### 6.2 Credit and Idempotency Hardening

- [ ] Verify `DailyEmailSendLog` unique constraint blocks double-sends
  - [ ] Simulate two concurrent `send` commands (two terminal tabs) — second should skip gracefully
- [ ] Verify credits = 0 path: user gets no send, no log row, clear skip in CLI output
- [ ] Verify "all modules fail" path: send still fires with "nothing loaded" body; 1 credit deducted

**Manual Testing 6.2:**
- [ ] Set `user.credits = 0`, run `flask daily_email send` — user skipped, logged
- [ ] Set credits back, run send twice — second call sees existing log row, skips

---

### 6.3 Dashboard Enhancement

- [ ] Update `index.html` dashboard
  - [ ] Show which modules are currently enabled (checkmarks/badges)
  - [ ] "Next send" estimated time: compute next future `local_hour == send_hour_local` wall-clock
  - [ ] "Last sent" from most recent `DailyEmailSendLog` where `status="sent"`
  - [ ] Credit balance display with "0 credits" warning state
  - [ ] Preview button (calls `POST /daily-email/preview`)

**Manual Testing 6.3:**
- [ ] Dashboard reflects correct next/last send times in user's timezone
- [ ] 0-credit warning visible
- [ ] Preview renders current settings without sending

---

### 6.4 Email HTML Polish

- [ ] Final HTML email template in `email_builder.py`
  - [ ] Inline critical CSS (email clients strip `<style>` blocks)
  - [ ] Mobile-friendly single column, max-width 600px
  - [ ] Dark header: "Good morning — [Weekday, Month Day]" + "City, ST" if weather location set
  - [ ] Module cards: icon + title bar, content rows, subtle borders
  - [ ] Footer: "Manage your digest preferences" link → `/daily-email/settings`; "You're receiving this because you opted in"
  - [ ] Test rendering in Gmail, Apple Mail, mobile

**Manual Testing 6.4:**
- [ ] Send test to real email address; check rendering in Gmail web and mobile
- [ ] Verify all sections render cleanly
- [ ] Verify footer link works

---

## Completion Checklist

Before considering v1 complete:

- [ ] All 6 DB models created and migrated
- [ ] Weather geocode + forecast fetch working
- [ ] Stocks fetch + validation working
- [ ] Sports fetch (ESPN, 4 leagues) + team filter working
- [ ] Ashby jobs fetch + slug/URL parsing working
- [ ] Email builder produces valid HTML with all 4 modules
- [ ] Send command: due-check, idempotency, credits, parallel fetches, error handling
- [ ] Send test command works on demand
- [ ] Settings UI: all 4 modules configurable within caps
- [ ] Preview works (no send, no credit)
- [ ] CSS uses `de-` prefix throughout
- [ ] All `@login_required` decorators in place
- [ ] Partial failure (one module down) does not block send
- [ ] All-modules-fail sends "nothing loaded" email + deducts 1 credit
- [ ] Credits = 0 skips send gracefully
- [ ] Full send test passed: sign in → configure → receive digest email

---

## Future Enhancements (Post-v1)

- [ ] Headlines (NewsAPI)
- [ ] Local events (Ticketmaster / Eventbrite)
- [ ] Google Calendar (per-user OAuth, later phase)
- [ ] Additional job boards (Greenhouse, Lever)
- [ ] Multiple Ashby boards per user
- [ ] AQI toggle on weather
- [ ] Plain-text multipart email
- [ ] Per-module "last fetched" timestamps in dashboard
- [ ] Admin view: send log across all users, failure rate alerts
- [ ] TTL cache (Redis or DB table) for hot shared API keys across hourly runs
