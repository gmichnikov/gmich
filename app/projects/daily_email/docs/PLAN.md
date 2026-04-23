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
- [x] `include_sports` toggle live; `include_jobs` via hidden field (coming soon) so save doesn’t clear DB flags
- [x] Save Settings snapshot JS includes `include_sports`
- [x] Dashboard Preview button if weather locations **or** stock tickers **or** sports watches exist (when that module is on)

**Manual Testing 4.2:**

- [ ] Add NBA + a team — saved, listed
- [ ] Add 11th watch — error redirect
- [ ] Preview — scores card (or “no games” / “add teams” as appropriate)
- [ ] Send Now / scheduled send — includes sports when enabled
- [ ] Turn off sports module — no sports card in preview

---

## Phase 5: Ashby Jobs Module

### 5.1 Jobs Fetch

- [ ] Create `app/projects/daily_email/modules/jobs.py` (slug/URL parse, fetch, render)

### 5.2 Jobs Settings UI

- [ ] Routes: save, clear, optional inline test
- [ ] Enable `include_jobs` toggle (remove hidden-only hack or merge with real toggle)

**Manual Testing 5.2:** (unchanged from prior plan)

---

## Phase 6: Full Integration + Polish

- [ ] All 4 modules + timing logs
- [ ] Idempotency / credits edge cases
- [ ] Email HTML polish in `email_builder.py`

---

## Completion Checklist

- [x] All 6 DB models created and migrated
- [x] Weather, stocks, sports modules + settings
- [ ] Ashby jobs module + settings
- [x] Email builder, send command, preview, admin Send Now
- [x] Parallel module fetch in `commands.py`
- [ ] Full 4-module send test on production
- [x] `de-` CSS prefix; settings dirty-state for main save button

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
