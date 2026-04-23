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
- `app/projects/daily_email/modules/sports.py` — ESPN scoreboard + team filter (new)
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

- [x] All models + weather module (see previous checklist)

---

## Phase 2: Email Infrastructure + First Working Send ✅

- [x] email_builder, commands, settings UI, preview, Send Now (admin)

---

## Phase 3: Stocks Module ✅

- [x] `yfinance` in `requirements.txt`
- [x] `modules/stocks.py` — validate_ticker, fetch_stocks, render_stocks_section
- [x] `POST` add/delete tickers, settings section, wire commands + preview
- [x] Inline validation feedback + disabled button while validating

---

## Phase 4: Sports Scores Module ✅

### 4.1 Sports Fetch ✅

- [x] `modules/sports.py` — `render_sports_section(watches, user_timezone)`
- [x] `ESPNClient` + `LEAGUE_MAP` for scoreboard URL; `dates=YYYYMMDD-YYYYMMDD` for yesterday–today in user TZ
- [x] Filter events by `competitor.team.id` vs stored `espn_team_id` per league
- [x] Cap 25 rows, partial failure if at least one league fetch succeeds
- [x] NFL, NBA, MLB, NHL only

### 4.2 Sports Settings UI ✅

- [x] `GET /daily-email/settings/sports/teams?league=NBA` — JSON team list
- [x] `POST /daily-email/settings/sports/add` — max 10 watches, dedupe league+team
- [x] `POST /daily-email/settings/sports/delete/<id>` — remove watch
- [x] Settings: league dropdown → load teams → pick team → Add; list with Remove
- [x] `include_sports` toggle live; `include_jobs` was a hidden “coming soon” field (superseded in Phase 5 by a real toggle)
- [x] Save Settings snapshot JS includes `include_sports` (and `include_jobs` as of Phase 5)
- [x] Dashboard Preview button if weather locations **or** stock tickers **or** sports watches **or** a saved Ashby board exist (when that module is on)

**Manual Testing 4.2:** (user to confirm)

- [x] Add NBA + a team — saved, listed
- [x] Add 11th watch — error redirect
- [x] Preview — scores card (or “no games” / “add teams” as appropriate)
- [x] Send Now / scheduled send — includes sports when enabled
- [x] Turn off sports module — no sports card in preview

---

## Phase 5: Job boards (multi-ATS) ✅

### 5.1 Jobs fetch ✅

- [x] `app/projects/daily_email/modules/jobs.py` — **Ashby** and **Greenhouse** public APIs; parse URL or token; optional title/department filter; up to 12 rows per board; `render_jobs_section` takes a **list** of watches
- [x] `DailyEmailJobWatch` model: `ats` + `board_token` + `filter_phrase` + `sort_order` (many per user; unique on user + ats + token)

### 5.2 Settings UI ✅

- [x] `POST .../settings/jobs/add` and `POST .../settings/jobs/delete/<id>` (live fetch validates on add)
- [x] `include_jobs` toggle; dashboard preview when `include_jobs` and at least one watch

**Manual Testing 5.2:** (user to run)

- [x] Add multiple boards (mix Ashby + Greenhouse) — all listed, digest shows subsections
- [x] Invalid board — error message, not saved
- [x] Per-board filter — subset or omit when no matches
- [x] Remove one watch — list updates; digest matches
- [x] `include_jobs` off — no jobs block

---

## Phase 6: Full Integration + Polish ✅

- [x] All 4 modules + **timing logs** (`INFO` lines: per-module ms, fetch wall time, HTML build ms, Mailgun ms, total; on success)
- [x] **Idempotency / credits:** only skip scheduled send when a log row for that local **date** is already **`sent`**; refresh `user` before send; if credits go to 0 after fetch, set log `no_credits` and do not send; `failed` / `no_credits` rows can be **retried** (replaced on next claim); do not delete `pending` rows; credit decremented only after Mailgun returns
- [x] **Email HTML polish** in `email_builder.py` (preheader, font stack, header gradient, card radius/shadow, error + footer copy, `color-scheme: light`)

---

## Completion Checklist

- [x] All 6 DB models created and migrated
- [x] Weather, stocks, sports modules + settings
- [x] Job boards (Ashby + Greenhouse) + list settings
- [x] Email builder, send command, preview, admin Send Now
- [x] Parallel module fetch in `commands.py`
- [ ] Full 4-module send test on production
- [x] `de-` CSS prefix; settings dirty-state for main save button

---

## Future Enhancements (Post-v1)

- [ ] Headlines (NewsAPI)
- [ ] Local events (Ticketmaster / Eventbrite)
- [ ] Google Calendar (per-user OAuth, later phase)
- [ ] Additional job boards (Lever, etc.): add `ats` value, parser, and fetcher in `modules/jobs.py` + template option
- [ ] AQI toggle on weather
- [ ] Plain-text multipart email
- [ ] Per-module "last fetched" timestamps in dashboard
- [ ] Admin view: send log across all users, failure rate alerts
- [ ] TTL cache (Redis or DB table) for hot shared API keys across hourly runs
