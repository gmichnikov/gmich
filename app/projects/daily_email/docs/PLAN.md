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

## Phase 1: Weather Module + Database Models ✅

### 1.1 Database Models ✅

- [x] Create `app/projects/daily_email/models.py`
  - [x] `DailyEmailProfile` — per-user digest master record
  - [x] `DailyEmailWeatherLocation` — up to 3 per user
  - [x] `DailyEmailStockTicker` — up to 10 per user
  - [x] `DailyEmailSportsWatch` — up to 10 per user
  - [x] `DailyEmailJobsConfig` — 1 per user
  - [x] `DailyEmailSendLog` — idempotency anchor with `UNIQUE(user_id, digest_local_date)`
- [x] Import all models in `app/__init__.py`

**Manual Testing 1.1:**
- [ ] Run `flask db migrate -m "Add daily email models"`
- [ ] Review migration file
- [ ] Run `flask db upgrade`
- [ ] Confirm all tables exist with correct schema

---

### 1.2 Weather Module ✅

- [x] Create `app/projects/daily_email/modules/` directory with `__init__.py`
- [x] `geocode_location(query)` — Open-Meteo Geocoding API, returns lat/lon/label
- [x] `fetch_weather(lat, lon, user_timezone)` — 7-day forecast with high/low/precip_pct/precip_sum/condition/emoji/sunrise/sunset
- [x] `render_weather_section(locations, user_timezone)` — HTML card per location; WMO emoji icons; day name + date in 7-day strip; user timezone anchors all locations to same calendar date

---

## Phase 2: Email Infrastructure + First Working Send ✅

### 2.1 Email Builder ✅

- [x] `build_digest_html(user, profile, module_results)` — fixed section order, error cards for failed modules, "nothing loaded" fallback
- [x] `build_subject(user)` — date-stamped subject line

### 2.2 Send Command ✅

- [x] `flask daily_email send` — due-check, already-sent check, credits check, claim row, parallel fetch, Mailgun send, credit deduct
- [x] `flask daily_email send_test --user-id <id>` — immediate send, costs 1 credit, no send log row
- [x] `flask daily_email send-now` admin route — purple button on dashboard, admin-only, confirm dialog
- [x] Registered in `app/__init__.py`

### 2.3 Settings UI ✅

- [x] `GET /daily-email/` — dashboard with status card, module badges, last sent, credits, Preview + Send Now buttons
- [x] `GET /daily-email/settings` — settings form
- [x] `POST /daily-email/settings/save` — save profile (on/off, send hour, module toggles)
- [x] `POST /daily-email/settings/weather/add` — geocode + save location (max 3)
- [x] `POST /daily-email/settings/weather/delete/<id>` — remove location
- [x] `POST /daily-email/preview` — renders email HTML in new tab, no send, no credit
- [x] CSS with `de-` prefix throughout

**Manual Testing 2.x — do before Phase 3:**
- [ ] Navigate to `/daily-email/` — dashboard loads
- [ ] Go to settings, toggle digest on, set send hour, save — changes persist
- [ ] Add a weather location — geocode works, location appears in list
- [ ] Try adding a 4th location — blocked with flash error
- [ ] Delete a location — removed
- [ ] Click Preview — email HTML renders in new tab (no send)
- [ ] Click Send Now (admin) — email arrives, credit decremented
- [ ] Run `flask daily_email send` with send hour matching current local hour — email arrives, log row inserted
- [ ] Run again same hour — skipped (already sent today)

---

## Phase 3: Stocks Module

### 3.1 Stocks Fetch

- [ ] Add `yfinance` to `requirements.txt`
- [ ] Create `app/projects/daily_email/modules/stocks.py`
  - [ ] `validate_ticker(symbol: str) -> bool`
    - [ ] Call `yfinance.Ticker(symbol).fast_info`; return True if price present
    - [ ] Timeout via `concurrent.futures` 5s; return False on exception
  - [ ] `fetch_stocks(tickers: list[str]) -> list[dict]`
    - [ ] Per-ticker `.history(period="2d")` calls
    - [ ] Return list of `{"symbol": str, "price": float, "change": float, "pct_change": float}`
    - [ ] Partial results OK; return empty list if all fail
  - [ ] `render_stocks_section(tickers: list[DailyEmailStockTicker]) -> str | None`
    - [ ] Up to 10 tickers; HTML card with a row per ticker showing price + day change colored green/red

### 3.2 Stocks Settings UI

- [ ] Add to `routes.py`:
  - [ ] `POST /daily-email/settings/stocks/add` — validate ticker server-side, save, reject if ≥ 10 or invalid
  - [ ] `POST /daily-email/settings/stocks/delete/<id>` — remove ticker
- [ ] Add stocks section to `settings.html`:
  - [ ] Toggle (now active, not "coming soon"), ticker list, add form, validation error display
  - [ ] Note: "Data from Yahoo Finance; unofficial, may be delayed"
- [ ] Wire `render_stocks_section` into `commands.py` parallel fetch (replace `_not_implemented_yet` stub)
- [ ] Wire into `routes.py` preview

**Manual Testing 3.2:**
- [ ] Add valid ticker (AAPL) — saved, appears in list
- [ ] Add invalid ticker (NOTREAL123) — inline error, not saved
- [ ] Add 11th ticker — blocked
- [ ] Click Preview — stocks card appears with prices and day change
- [ ] Click Send Now — email includes stocks card
- [ ] Disable stocks toggle — card absent from preview

---

## Phase 4: Sports Scores Module

### 4.1 Sports Fetch

- [ ] Create `app/projects/daily_email/modules/sports.py`
  - [ ] Import `parse_scoreboard`, `LEAGUE_TO_SPORT_KEY` from `sports_scores/core/espn_parser.py`
  - [ ] Import `ESPNClient` from `sports_schedule_admin/core/espn_client.py` for `LEAGUE_MAP`
  - [ ] `fetch_sports_for_digest(watches, user_tz) -> str | None`
    - [ ] Compute yesterday + today dates in `user_tz` using `ZoneInfo`
    - [ ] One ESPN scoreboard call per distinct league (`dates=YYYYMMDD-YYYYMMDD`)
    - [ ] Filter games where home or away matches watched `espn_team_id`
    - [ ] Cap at 25 rows; add "+ N more" if truncated
    - [ ] HTML card: score if final, status label if live/scheduled

### 4.2 Sports Settings UI

- [ ] Add to `routes.py`:
  - [ ] `GET /daily-email/settings/sports/teams?league=NBA` — JSON list of teams (reuse ESPNClient)
  - [ ] `POST /daily-email/settings/sports/add` — save watch, reject if ≥ 10
  - [ ] `POST /daily-email/settings/sports/delete/<id>` — remove watch
- [ ] Add sports section to `settings.html`:
  - [ ] Toggle (now active), watch list, league dropdown → team dropdown (JS-populated) → Add button
  - [ ] Leagues: NFL, NBA, MLB, NHL only
- [ ] Wire `fetch_sports_for_digest` into `commands.py` and preview

**Manual Testing 4.2:**
- [ ] Add a sports watch (e.g. NBA + Lakers) — saved
- [ ] Add 11th watch — blocked
- [ ] Preview — sports card shows recent games for watched teams only
- [ ] Send Now — email includes sports card
- [ ] Disable sports — card absent from preview

---

## Phase 5: Ashby Jobs Module

### 5.1 Jobs Fetch

- [ ] Create `app/projects/daily_email/modules/jobs.py`
  - [ ] `parse_slug_from_input(raw) -> str | None` — accepts slug or URL (`jobs.ashbyhq.com/{slug}`, `{org}.ashbyhq.com`)
  - [ ] `fetch_ashby_jobs(slug, filter_phrase) -> list[dict] | None`
    - [ ] `GET https://api.ashbyhq.com/posting-api/job-board/{slug}`; timeout 10s
    - [ ] Case-insensitive substring filter on title (+ department if present)
    - [ ] Return list of `{"title", "url", "team", "location"}`, max 12; `[]` if no matches; `None` on error
  - [ ] `render_jobs_section(config: DailyEmailJobsConfig) -> str | None`
    - [ ] None if no slug; omit section if `[]`; error card if fetch fails

### 5.2 Jobs Settings UI

- [ ] Add to `routes.py`:
  - [ ] `POST /daily-email/settings/jobs/save` — parse slug, validate via live Ashby call, save
  - [ ] `POST /daily-email/settings/jobs/clear` — clear slug/filter
- [ ] Add jobs section to `settings.html`:
  - [ ] Toggle (now active), URL/slug input, optional filter phrase (max 100 chars)
  - [ ] Show current slug after save; inline error if invalid
- [ ] Wire into `commands.py` and preview

**Manual Testing 5.2:**
- [ ] Paste valid Ashby URL — slug extracted, validated, saved
- [ ] Paste bad URL — inline error, not saved
- [ ] Filter phrase matches subset of jobs — only matching rows in email
- [ ] Filter matches 0 jobs — section omitted
- [ ] Preview and Send Now both include jobs card
- [ ] Disable jobs — card absent from preview

---

## Phase 6: Full Integration + Polish

### 6.1 Parallel Fetch Verification

- [ ] All 4 modules wired into `ThreadPoolExecutor` in `commands.py`
- [ ] Log per-module timing
- [ ] Verify one failing module doesn't block the others

### 6.2 Credit and Idempotency Hardening

- [ ] Test credits = 0 path — skipped, no log row
- [ ] Test all-modules-fail path — "nothing loaded" email, 1 credit deducted
- [ ] Test double-run same hour — second run skips via unique constraint

### 6.3 Email HTML Polish

- [ ] Dark header shows primary weather location city if set
- [ ] Test rendering in Gmail web + mobile
- [ ] Verify footer preferences link works

---

## Completion Checklist

- [x] All 6 DB models created and migrated
- [x] Weather geocode + forecast fetch working (with emoji, precip sum, sunrise/sunset, user-tz anchor)
- [x] Email builder produces valid HTML
- [x] Send command: due-check, idempotency, credits, parallel fetches, error handling
- [x] Send test command works on demand
- [x] Settings UI: weather configurable; stocks/sports/jobs coming soon stubs
- [x] Preview works (no send, no credit)
- [x] Admin "Send Now" button
- [x] CSS uses `de-` prefix throughout
- [ ] `yfinance` stocks fetch + settings UI
- [ ] ESPN sports fetch + settings UI
- [ ] Ashby jobs fetch + settings UI
- [ ] All 4 modules in parallel fetch
- [ ] Full send test with all 4 modules
- [ ] Email rendering tested in Gmail

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
