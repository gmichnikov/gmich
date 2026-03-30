# Sports Scores - Implementation Plan

This plan follows the Sports Scores PRD and breaks implementation into smaller, testable phases. The project is public (no login), reads from ESPN's unofficial API, and persists game data in the app database.

**Status:** Phase 1 🔲 Phase 2 🔲 Phase 3 🔲 Phase 4 🔲

**CSS prefix:** `sc-` (Sports sCores)

---

## Relevant Files

- `app/projects/sports_scores/__init__.py` — Blueprint initialization
- `app/projects/sports_scores/routes.py` — Page and API routes
- `app/projects/sports_scores/models.py` — DB models (`ScoresFetchLog`, `ScoresGame`)
- `app/projects/sports_scores/core/espn_parser.py` — Parse ESPN scoreboard JSON → normalized game dicts
- `app/projects/sports_scores/core/scores_service.py` — Orchestrate fetch/throttle/upsert logic
- `app/projects/sports_scores/templates/sports_scores/index.html` — Main scores page
- `app/projects/sports_scores/static/css/sports_scores.css` — Styles (all classes use `sc-` prefix)
- `app/projects/sports_schedule_admin/core/espn_client.py` — Reuse `ESPNClient` and `LEAGUE_MAP`
- `app/__init__.py` — Register blueprint
- `app/projects/registry.py` — Already registered

### Notes

- All CSS classes must use the `sc-` prefix to avoid collisions with other projects.
- No auth required; same data for all visitors.
- No background jobs; fetch happens on page load (throttled to 1/min per sport).
- Supported sports for v1: **NFL, NBA, MLB, NHL** only.

---

## Database Schema

### `ScoresFetchLog` table (`scores_fetch_log`)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `sport_key` | String(16) | e.g. `"nfl"`, `"nba"`, `"mlb"`, `"nhl"` |
| `last_fetched_at` | DateTime | UTC; updated on each successful ESPN fetch |

One row per sport. Used only for throttle enforcement.

### `ScoresGame` table (`scores_game`)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `espn_event_id` | String(64) | ESPN's event ID; unique per sport |
| `sport_key` | String(16) | `"nfl"`, `"nba"`, `"mlb"`, `"nhl"` |
| `game_date` | Date | Calendar date of the game (UTC from ESPN) |
| `start_time_utc` | DateTime | Exact kickoff/tip-off in UTC |
| `home_team` | String(128) | Full team name |
| `away_team` | String(128) | Full team name |
| `home_score` | Integer | Null if game hasn't started |
| `away_score` | Integer | Null if game hasn't started |
| `status_state` | String(16) | ESPN state: `"pre"`, `"in"`, `"post"` |
| `status_detail` | String(128) | Human-readable: `"7:30 PM ET"`, `"Q3 14:22"`, `"Final"` |
| `updated_at` | DateTime | UTC; set on each upsert |

Unique constraint: `(espn_event_id, sport_key)`. Upserted on each successful fetch.

---

## Display Logic

### Time window shown

- **Past 2 days + today + future games today** — i.e., yesterday, the day before, and today (including games that haven't started yet).
- "Today" is determined by the `dates=` parameter sent to ESPN (UTC default, or browser-supplied date via query param).
- Days with no stored games show a date header + "No games scheduled."

### Game status rendering

| `status_state` | Display |
|---|---|
| `"pre"` | Show `start_time_utc` converted to **US Eastern (ET)** — e.g. `7:30 PM ET` |
| `"in"` | Show live score + `status_detail` (e.g. `Q3 14:22`) with a **LIVE** badge |
| `"post"` | Show final score + `"Final"` label |

---

## Phase 1: Models, ESPN Parser, Fetch Service

### 1.1 Database Models

- [ ] Create `app/projects/sports_scores/models.py`
  - [ ] Define `ScoresFetchLog` (columns: `id`, `sport_key`, `last_fetched_at`)
  - [ ] Define `ScoresGame` (all columns listed in schema above)
  - [ ] Add unique constraint on `(espn_event_id, sport_key)` in `ScoresGame`
  - [ ] Import models in `app/projects/sports_scores/__init__.py` so Flask-Migrate picks them up
- [ ] Ask user to run: `flask db migrate -m "Add sports scores models"` then `flask db upgrade`
- [ ] Verify tables created: `scores_fetch_log`, `scores_game`

**Manual Testing 1.1:**
- [ ] Confirm migration runs without errors
- [ ] Confirm both tables exist with correct columns

---

### 1.2 ESPN Parser

- [ ] Create `app/projects/sports_scores/core/__init__.py`
- [ ] Create `app/projects/sports_scores/core/espn_parser.py`
  - [ ] Import `ESPNClient.LEAGUE_MAP` from `sports_schedule_admin.core.espn_client` for league path lookup
  - [ ] Define `SUPPORTED_SPORTS = ["nfl", "nba", "mlb", "nhl"]`
  - [ ] Define `SPORT_DISPLAY = {"nfl": "NFL", "nba": "NBA", "mlb": "MLB", "nhl": "NHL"}`
  - [ ] Implement `parse_scoreboard(sport_key, api_response) -> list[dict]`
    - [ ] Iterate `api_response["events"]`
    - [ ] For each event extract:
      - `espn_event_id`: `event["id"]`
      - `sport_key`: passed in
      - `game_date`: `event["date"][:10]` (YYYY-MM-DD)
      - `start_time_utc`: parse `event["date"]` as UTC datetime
      - `home_team`: competitor where `homeAway == "home"` → `team["displayName"]`
      - `away_team`: competitor where `homeAway == "away"` → `team["displayName"]`
      - `home_score`: `int(competitor["score"])` if present, else `None`
      - `away_score`: same for away
      - `status_state`: `event["status"]["type"]["state"]` (values: `"pre"`, `"in"`, `"post"`)
      - `status_detail`: `event["status"]["type"]["shortDetail"]` (e.g. `"7:30 PM ET"`, `"Q3 14:22"`, `"Final"`)
    - [ ] Return list of dicts; skip events that raise parsing errors (log warning, continue)

**Manual Testing 1.2:**
- [ ] Call `parse_scoreboard("nba", sample_response)` with a real or mocked ESPN payload
- [ ] Verify all fields populated correctly for pre/in/post game examples
- [ ] Verify malformed events are skipped without crashing

---

### 1.3 Scores Service (Fetch + Throttle + Upsert)

- [ ] Create `app/projects/sports_scores/core/scores_service.py`
  - [ ] Import `ESPNClient` from `sports_schedule_admin.core.espn_client`
  - [ ] Import `parse_scoreboard` from `espn_parser`
  - [ ] Import `ScoresFetchLog`, `ScoresGame` from `models`
  - [ ] Implement `get_or_create_fetch_log(sport_key) -> ScoresFetchLog`
  - [ ] Implement `should_fetch(sport_key) -> bool`
    - [ ] Returns `True` if no fetch log exists for sport, or `last_fetched_at` is > 60 seconds ago
  - [ ] Implement `fetch_and_store(sport_key, dates_param=None)`
    - [ ] Build `dates_param` from today's UTC date if not provided (format: `YYYYMMDD`)
    - [ ] Call `ESPNClient().fetch_schedule(sport_key, dates_param)` — or equivalent scoreboard endpoint
    - [ ] On success: call `parse_scoreboard`, upsert each game into `ScoresGame`, update `ScoresFetchLog.last_fetched_at`
    - [ ] On ESPN error: log error, do not update fetch log (so next load can retry)
    - [ ] Upsert logic: `INSERT ... ON CONFLICT (espn_event_id, sport_key) DO UPDATE SET ...` — or SQLAlchemy merge
  - [ ] Implement `get_games_for_display(sport_key, anchor_date=None) -> dict`
    - [ ] `anchor_date` defaults to UTC today if not provided
    - [ ] Query `ScoresGame` where `sport_key=sport_key` and `game_date` in `[anchor_date - 2 days, anchor_date - 1 day, anchor_date]`
    - [ ] Return dict keyed by date string, value = list of game dicts sorted by `start_time_utc`
    - [ ] Include all three dates as keys even if empty (so template can show "No games scheduled")

**Manual Testing 1.3:**
- [ ] Call `should_fetch("nba")` with no fetch log → returns `True`
- [ ] Call `fetch_and_store("nba")` → games upserted, fetch log updated
- [ ] Call `should_fetch("nba")` immediately after → returns `False`
- [ ] Call `get_games_for_display("nba")` → returns dict with 3 date keys, games under correct dates

---

## Phase 2: Routes & Page Structure

### 2.1 Main Route

- [ ] Update `app/projects/sports_scores/routes.py`
  - [ ] Add `GET /sports-scores/` route
    - [ ] Accept optional `?sport=` query param (default: `"nfl"`); validate against `SUPPORTED_SPORTS`
    - [ ] Accept optional `?date=YYYY-MM-DD` query param (browser-supplied anchor date); fall back to UTC today if missing/invalid
    - [ ] Call `should_fetch(sport_key)` → if True, call `fetch_and_store(sport_key, dates_param)`
    - [ ] Call `get_games_for_display(sport_key, anchor_date)` to get games
    - [ ] Pass to template: `sport_key`, `games_by_date` (dict), `supported_sports`, `sport_display`, `anchor_date`
  - [ ] Add `GET /sports-scores/api/scores` JSON endpoint (for future client polling; returns same data as above as JSON)
    - [ ] Same params: `sport`, `date`
    - [ ] Returns `{"sport": ..., "games_by_date": {...}, "fetched_at": ...}`

**Manual Testing 2.1:**
- [ ] Load `/sports-scores/` → no errors, page renders
- [ ] Load `/sports-scores/?sport=nba` → NBA data
- [ ] Load `/sports-scores/?sport=invalid` → falls back to NFL or returns 400
- [ ] Load `/sports-scores/api/scores?sport=nhl` → JSON response

---

### 2.2 Page Layout & Sport Tabs

- [ ] Create `app/projects/sports_scores/templates/sports_scores/index.html`
  - [ ] Extend base template
  - [ ] `sc-wrapper`: page container with its own background (white/light neutral panel, not the homepage purple gradient)
  - [ ] Sport tabs: `NFL | NBA | MLB | NHL` — each tab is a link to `?sport=nfl` etc.
  - [ ] Active tab highlighted
  - [ ] Below tabs: scores content area (date sections + game cards)
  - [ ] Include a small "Last updated: X min ago" or "Live" indicator near the tab bar
- [ ] Create `app/projects/sports_scores/static/css/sports_scores.css`
  - [ ] `sc-wrapper`: background, padding, max-width, margin, optional border-radius/box-shadow
  - [ ] `sc-tabs`: tab bar styles; `sc-tab`, `sc-tab--active`
  - [ ] `sc-date-section`: date header + game list grouping
  - [ ] `sc-date-header`: date label (e.g. "Sunday, Mar 30")
  - [ ] `sc-game-card`: individual game row/card
  - [ ] `sc-no-games`: "No games scheduled" empty state text
  - [ ] All classes use `sc-` prefix

**Manual Testing 2.2:**
- [ ] Page loads at `/sports-scores/`
- [ ] Four sport tabs visible; active tab highlighted
- [ ] Page has its own background panel — homepage purple gradient does not bleed through
- [ ] No layout shift or overflow on desktop

---

### 2.3 Game Cards

- [ ] Implement game card HTML in template (loop over `games_by_date`)
  - [ ] For each date key (past 2 days + today), render a `sc-date-section`:
    - [ ] `sc-date-header`: formatted date (e.g. "Sunday, Mar 30" or "Today, Mar 30")
    - [ ] If no games for date: `sc-no-games` message
    - [ ] For each game: `sc-game-card` containing:
      - Away team name + score (or `–` if pre-game)
      - Home team name + score (or `–` if pre-game)
      - Status display (per display logic table above):
        - `"pre"`: scheduled time in ET (e.g. `7:30 PM ET`)
        - `"in"`: `status_detail` + `sc-live-badge` ("LIVE")
        - `"post"`: "Final"
  - [ ] Order: most recent date at top, oldest at bottom (or reverse — see question below — decided: **most recent first**)
  - [ ] Within a date: games sorted by `start_time_utc` ascending

**Manual Testing 2.3:**
- [ ] Pre-game shows scheduled time in ET, no score
- [ ] In-progress shows score + period/clock + LIVE badge
- [ ] Final shows score + "Final"
- [ ] Empty date shows "No games scheduled"
- [ ] Dates labeled correctly ("Today" for today, formatted date for others)

---

## Phase 3: Styling & Mobile Polish

### 3.1 Game Card Styling

- [ ] Style `sc-game-card` for clarity and scannability:
  - [ ] Two-row or two-column layout: away team on top/left, home team on bottom/right
  - [ ] Score prominent (larger font, bold)
  - [ ] Team name readable but secondary to score
  - [ ] Status (time / LIVE / Final) clearly visible, right-aligned or below scores
  - [ ] `sc-live-badge`: small colored badge (e.g. red/green dot or pill) for in-progress games
  - [ ] Subtle divider between game cards
- [ ] Style `sc-date-header`: bold, slightly larger, clear visual separation between date groups

**Manual Testing 3.1:**
- [ ] Scores are the most prominent element on each card
- [ ] LIVE badge is visually distinct
- [ ] Cards are easy to scan quickly

---

### 3.2 Mobile Responsiveness

- [ ] Tabs: full-width on mobile, tap targets ≥ 44px
- [ ] Game cards: full-width on mobile, comfortable padding
- [ ] No horizontal overflow at 375px width
- [ ] Font size ≥ 16px for all inputs/interactive elements (prevents iOS zoom)
- [ ] Test at 375px and 768px widths

**Manual Testing 3.2:**
- [ ] Load on mobile or narrow viewport (375px)
- [ ] All tabs tappable
- [ ] Cards readable and not clipped
- [ ] No horizontal scroll

---

### 3.3 Error & Edge Case Handling

- [ ] If ESPN fetch fails and no games are stored: show a clear message ("Scores unavailable. Refresh to try again.") instead of empty date sections
- [ ] If `sport` param is invalid: silently default to `"nfl"` (no 400 error for the page route)
- [ ] If `date` param is invalid/missing: silently default to UTC today
- [ ] Log all ESPN errors server-side; never expose raw errors to the user
- [ ] "Last updated" indicator: show `last_fetched_at` from `ScoresFetchLog` in a human-readable form (e.g. "Updated 2 min ago") — helps user know if data is stale

**Manual Testing 3.3:**
- [ ] Simulate ESPN failure (bad URL or offline) → user sees friendly message, no stack trace
- [ ] Load with `?sport=garbage` → defaults to NFL, no error
- [ ] Load with `?date=notadate` → defaults to today, no error
- [ ] "Updated X min ago" visible and accurate

---

## Phase 4: Integration & Final Checks

### 4.1 End-to-End Flow

- [ ] Load `/sports-scores/` cold (no DB rows) → ESPN fetch fires, games stored, page renders
- [ ] Reload within 1 minute → no ESPN fetch, renders from DB
- [ ] Switch sport tab (NFL → NBA) → NBA fetch fires if needed
- [ ] Switch back to NFL within 1 minute → no fetch, renders from DB
- [ ] Verify all four sports work (NFL, NBA, MLB, NHL)
- [ ] Verify "Updated X min ago" reflects correct time

**Manual Testing 4.1:**
- [ ] Full cold-start flow as above
- [ ] Confirm throttle works (check logs for ESPN call count)
- [ ] All four sport tabs render without errors

---

### 4.2 Security & Edge Cases

- [ ] `sport` param validated against allowlist before any DB or ESPN call
- [ ] `date` param validated as YYYY-MM-DD before use; invalid input falls back to UTC today
- [ ] No user input is ever interpolated into raw SQL
- [ ] ESPN errors logged server-side; generic message shown to user

**Manual Testing 4.2:**
- [ ] Try `?sport='; DROP TABLE scores_game; --` → no effect, defaults to NFL
- [ ] Try `?date=2099-99-99` → defaults to today, no crash

---

### 4.3 Registry & Blueprint Check

- [ ] Confirm `sports_scores` is registered in `app/__init__.py` (blueprint)
- [ ] Confirm `sports_scores` entry exists in `app/projects/registry.py` (already present as of writing)
- [ ] Confirm `/sports-scores/` is accessible from the homepage

---

## Completion Checklist

Before considering v1 complete:

- [ ] DB migration applied; both tables exist
- [ ] ESPN parser handles pre/in/post game states correctly
- [ ] Throttle enforced (≤ 1 fetch/min per sport)
- [ ] Games upserted correctly on each fetch
- [ ] Page renders for all four sports
- [ ] Sport tabs work; active tab highlighted
- [ ] Game cards show correct status display (time / LIVE / Final)
- [ ] Empty days show "No games scheduled"
- [ ] "Updated X min ago" indicator present
- [ ] ESPN errors handled gracefully (no stack traces in UI)
- [ ] Mobile layout usable at 375px
- [ ] All CSS uses `sc-` prefix
- [ ] No auth required (public access)

---

## Out of Scope (v1)

- Client-side polling (auto-refresh scores without full page reload)
- Backfill fetches for days with no stored games
- More than one ESPN call per sport per page load
- Favorites or personalization
- Deep stats, play-by-play, or box scores
- News, articles, video
- Betting integrations
- Additional sports beyond NFL, NBA, MLB, NHL
