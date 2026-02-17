# Sports Schedules - Implementation Plan

This plan follows the Sports Schedules PRD and breaks implementation into smaller, testable chunks. The project is public (no login), read-only, and uses DoltHub as the data source.

---

## Relevant Files

- `app/projects/sports_schedules/__init__.py` - Blueprint initialization.
- `app/projects/sports_schedules/routes.py` - Page and API routes.
- `app/projects/sports_schedules/templates/sports_schedules/index.html` - Main viewer template.
- `app/projects/sports_schedules/static/css/sports_schedules.css` - Styles (all classes use `ss-` prefix).
- `app/projects/sports_schedules/core/query_builder.py` - Build SQL from user selections (to create).
- `app/projects/sports_schedules/core/constants.py` - Filter options (sport, league, level, day, state) for UI (to create).
- `app/core/dolthub_client.py` - Shared DoltHub read client (to extract from sports_schedule_admin).
- `app/projects/sports_schedule_admin/core/dolthub_client.py` - Source of DoltHub client (to refactor).
- `app/__init__.py` - App initialization (register blueprint).
- `app/projects/registry.py` - Project registry (if needed).

### Notes

- All CSS classes must use the `ss-` prefix to avoid collisions with other projects.
- No database migrations; this project reads from DoltHub only.
- League options come from ESPN config (`LEAGUE_MAP`, `LEAGUE_DISPLAY_NAMES`).

---

## Phase 1: Shared Infrastructure & Query Building

### 1.1 Extract DoltHub Client to Shared Module

- [ ] Create `app/core/` directory if it does not exist
- [ ] Create `app/core/__init__.py` (empty or minimal)
- [ ] Create `app/core/dolthub_client.py`
  - [ ] Move full `DoltHubClient` from `sports_schedule_admin/core/dolthub_client.py` (read + write + batch_upsert)
  - [ ] Admin needs write and batch_upsert for sync; sports_schedules only uses `execute_sql` for reads
- [ ] Update `sports_schedule_admin/core/dolthub_client.py`
  - [ ] Replace with: `from app.core.dolthub_client import DoltHubClient` (re-export or delete file and update imports)
- [ ] Update all imports in sports_schedule_admin (routes, logic, commands) to use `app.core.dolthub_client`
- [ ] Add `from app.core.dolthub_client import DoltHubClient` in sports_schedules routes
- [ ] Verify sports_schedule_admin still works (sync, preview, coverage)

**Manual Testing 1.1:**
- [ ] Run a DoltHub read query from sports_schedule_admin (e.g., preview)
- [ ] Verify no import errors
- [ ] Confirm env vars (`DOLTHUB_API_TOKEN`, etc.) still apply

---

### 1.2 Create Constants Module (Low-Cardinality Fields)

- [ ] Create `app/projects/sports_schedules/core/` directory
- [ ] Create `app/projects/sports_schedules/core/__init__.py`
- [ ] Create `app/projects/sports_schedules/core/constants.py`
  - [ ] **Sport:** `SPORTS = ["basketball", "hockey", "football", "baseball", "soccer"]` (schema values)
  - [ ] **League:** Build from `sports_schedule_admin.core.espn_client`: `LEAGUES = list(LEAGUE_MAP.keys())`; for labels use `LEAGUE_DISPLAY_NAMES.get(code, code)` so CL→"Champions League (CL)", NBA→"NBA"
  - [ ] **Level:** `LEVELS = ["pro", "college"]`
  - [ ] **Day:** `DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]`
  - [ ] **State:** `STATES` — US state codes (AL, AK, AZ, … WY); use a standard list (e.g., `us.states` or hand-maintained)
  - [ ] Export `LOW_CARDINALITY_OPTIONS`: dict mapping column → list of `(value, label)` for UI multiselects (e.g. league: `[("NBA", "NBA"), ("CL", "Champions League (CL)"), ...]`; sport/level/day/state: value and label can match or use title case)
  - [ ] Export `DIMENSION_LABELS` — column → display label mapping (Sport, Level, League, Date, Day, Time (ET), etc.)
- [ ] **Usage:** Constants are the single source of truth. Query builder validates filter values against these allowlists before building SQL. Frontend gets options by passing `LOW_CARDINALITY_OPTIONS` and `DIMENSION_LABELS` from the index route to the template (no separate API needed for options).

**Manual Testing 1.2:**
- [ ] Import constants; verify all option lists non-empty
- [ ] League list includes NBA, NHL, EPL, etc.; display names correct for CL, EL, etc.

---

### 1.3 Create Query Builder Module

- [ ] Create `app/projects/sports_schedules/core/query_builder.py`
  - [ ] Import `LOW_CARDINALITY_OPTIONS`, `DIMENSION_LABELS` from `constants`
  - [ ] Define `DIMENSIONS` from constants (column, display_label)
  - [ ] Define `HIGH_CARDINALITY_FILTERS`: home_team, road_team, location, home_city (contains search — no fixed options)
  - [ ] **Low-cardinality validation:** When building WHERE, validate each filter value is in the corresponding allowlist from constants; reject unknown values (return error or ignore)
  - [ ] **Run requirement validation:** Reject if no dimensions selected AND count is off — return error e.g. "Select at least one dimension or turn on count to run a query." (PRD: user must select at least one dimension, OR turn on count)
  - [ ] Create `build_sql(params)` function
    - [ ] Accept dict with: dimensions, filters (low + high), date_mode, date_exact, date_start, date_end, date_year, date_n, anchor_date (for relative modes), count, limit, sort_column, sort_dir
    - [ ] Build SELECT clause from dimensions (or `*` if none and no count)
    - [ ] Add COUNT(*) and GROUP BY when count is on
    - [ ] Build WHERE clause from filters (AND logic)
    - [ ] Add date conditions (exact, range, year, last N days, next N days)
    - [ ] Sanitize contains filters: escape single quotes, handle `%` and `_` for LIKE
    - [ ] Add ORDER BY from sort_column, sort_dir
    - [ ] Add LIMIT (default 500, max 5000)
    - [ ] Return `(sql_string, error_message)` — error_message if validation fails
  - [ ] Validate: row limit 1–5000, date range start ≤ end, relative N > 0
  - [ ] Use allowlist for dimensions; never accept raw user input for column names

**Manual Testing 1.3:**
- [ ] Unit test or manual call: `build_sql({"dimensions": [], "count": 0})` → validation error
- [ ] Unit test or manual call: `build_sql({"dimensions": ["league", "date"], "limit": 10})` → valid SELECT
- [ ] Test with count on, dimensions selected → GROUP BY present
- [ ] Test with count on, no dimensions → single COUNT(*)
- [ ] Test date modes: exact, range, year, last 7 days, next 30 days
- [ ] Test contains filter escaping (e.g., "O'Brien" → proper escaping)

---

### 1.4 Create Query API Endpoint

- [ ] Add `GET /sports-schedules/api/query` route in `routes.py`
  - [ ] Parse query params per URL schema (5.1): dimensions, filters (sport, league, level, day, home_state, home_team, road_team, location, home_city), date_mode, date_exact, date_start, date_end, date_year, date_n, anchor_date, count, limit, sort_column, sort_dir
  - [ ] Call `build_sql()` with parsed params
  - [ ] If validation error (including no-dimensions-and-no-count), return `{"error": message}` with 400
  - [ ] Call DoltHub client `execute_sql(sql)`
  - [ ] If DoltHub error, return `{"error": "Unable to load data. Please try again."}` with 500
  - [ ] Return `{"rows": [...], "sql": sql_string}` (include SQL for "Show SQL" feature)
  - [ ] Handle empty results: return `{"rows": [], "sql": sql_string}` (no error)

**Manual Testing 1.4:**
- [ ] Call API with no dimensions and count=0 → 400 with validation error
- [ ] Call API with `?dimensions=league,date&limit=5`
- [ ] Verify rows returned
- [ ] Verify `sql` in response
- [ ] Test invalid params (e.g., limit=10000) → 400
- [ ] Test with filters applied

---

## Phase 2: Sidebar UI – Layout & Dimension Picker

### 2.1 Page Layout & Structure

- [ ] **Page container (separate from homepage purple):** Update `ss-wrapper` to act as a contained UI panel so the site’s purple gradient doesn’t bleed through. Follow pattern from sports_schedule_admin (`ssa-wrapper`) or betfake (`bf-page-wrapper`): give `ss-wrapper` its own background (e.g., white or light neutral), padding, optionally border-radius and box-shadow. Content should read as a distinct panel/card, not floating on the homepage background.
- [ ] Update `routes.py` index route to pass `LOW_CARDINALITY_OPTIONS` and `DIMENSION_LABELS` from constants to template
- [ ] Update `templates/sports_schedules/index.html`
  - [ ] Replace placeholder with two-column layout: sidebar (left) + main area (right)
  - [ ] Sidebar: fixed or sticky, collapsible on mobile
  - [ ] Main area: results table container (initially empty state)
  - [ ] Add "Run" button (prominent, in sidebar or above results)
  - [ ] Use `ss-` prefix for all classes (e.g., `ss-sidebar`, `ss-main`, `ss-run-btn`)
- [ ] Add base styles in `static/css/sports_schedules.css`
  - [ ] `ss-wrapper`: background, padding, max-width, margin; optional border-radius, box-shadow
  - [ ] Layout: flex or grid for sidebar + main
  - [ ] Sidebar width ~280px on desktop
  - [ ] Collapsible sections: Dimensions, Filters, Date, Options

**Manual Testing 2.1:**
- [ ] Page loads at `/sports-schedules/`
- [ ] Page has its own background panel — purple gradient from homepage does not show through content area
- [ ] Sidebar and main area visible
- [ ] Run button visible
- [ ] No layout shift or overflow on desktop

---

### 2.2 Dimension Picker

- [ ] Add "Dimensions" collapsible section in sidebar
  - [ ] Section header: "Dimensions" with expand/collapse toggle
  - [ ] Checkbox list for each dimension: Sport, Level, League, Date, Day, Time (ET), Home Team, Road Team, Location, City, State
  - [ ] Use display labels from PRD (e.g., "Time (ET)" not "time")
  - [ ] Column order in results = checkbox selection order
  - [ ] No dimensions selected by default
- [ ] Wire dimension state to a JS object or hidden inputs for form submit
- [ ] Add "Select dimensions and click Run to view schedules" empty-state message when no dimensions and no count
- [ ] **Run button validation:** When user clicks Run with no dimensions and count off, either disable the button or show inline validation message ("Select at least one dimension or turn on count") — prefer inline message so user understands the requirement

**Manual Testing 2.2:**
- [ ] Check/uncheck dimensions
- [ ] Verify selection order is preserved
- [ ] Empty state shows when nothing selected and count off
- [ ] Click Run with no dimensions and count off → validation message shown (or API returns 400, show error)

---

### 2.3 Filter Picker – Low-Cardinality (Multiselect)

- [ ] Add "Filters" collapsible section
  - [ ] Add hint: "All filters combined with AND"
  - [ ] Populate multiselect options from `core/constants.LOW_CARDINALITY_OPTIONS` (expose via API or embed in template)
  - [ ] Sport: multiselect from `SPORTS`
  - [ ] League: multiselect from `LEAGUES` (use display names for labels)
  - [ ] Level: multiselect from `LEVELS`
  - [ ] Day: multiselect from `DAYS`
  - [ ] State: multiselect from `STATES`
  - [ ] All optional; empty = no filter on that dimension
- [ ] Wire filter values to query params (values sent must match constants; backend validates)

**Manual Testing 2.3:**
- [ ] Select Sport = basketball, League = NBA
- [ ] Run query, verify results filtered
- [ ] Verify AND hint visible

---

### 2.4 Filter Picker – High-Cardinality (Contains Search)

- [ ] Add contains-search inputs in Filters section
  - [ ] Home Team: text input, placeholder "e.g., Celtics"
  - [ ] Road Team: text input
  - [ ] Location: text input (venue name)
  - [ ] City: text input
  - [ ] Case-insensitive contains (LIKE %value%)
- [ ] Wire to query builder; ensure server-side escaping

**Manual Testing 2.4:**
- [ ] Enter "Celtics" in Home Team, run query
- [ ] Verify only games with "Celtics" in home_team
- [ ] Test special chars (apostrophe) — no SQL error

---

## Phase 3: Date Filter & Options

### 3.1 Date Filter – Absolute Modes

- [ ] Add "Date" collapsible section
  - [ ] Mode selector: Exact date | Date range | Year only
  - [ ] Exact date: single date input (YYYY-MM-DD)
  - [ ] Date range: start date + end date (inclusive)
  - [ ] Year only: year input (e.g., 2026)
  - [ ] Validate: start ≤ end for range
- [ ] Wire date params to API

**Manual Testing 3.1:**
- [ ] Select exact date 2026-02-19, run → only that date
- [ ] Select range 2026-02-01 to 2026-02-28 → only that range
- [ ] Select year 2026 → all games in 2026
- [ ] Invalid range (end before start) → validation error

---

### 3.2 Date Filter – Relative Modes

- [ ] Add relative date options to Date section
  - [ ] Last week (7 days), Last month (30 days), Last N days (N input)
  - [ ] Next week (7 days), Next N days (N input)
  - [ ] Validate N > 0 for Last N / Next N
- [ ] **"Today" / anchor date:** See Phase 5.1a below. Client sends `anchor_date` (YYYY-MM-DD) so "today" is user-local without requiring auth.

**Manual Testing 3.2:**
- [ ] Select "Last week" → past 7 days from today
- [ ] Select "Next 30 days" → next 30 days from today
- [ ] Select "Last 14 days" → past 14 days

---

### 3.3 Options: Count, Row Limit, Sort

- [ ] Add "Options" collapsible section
  - [ ] "Include count" toggle (default: off)
  - [ ] Row limit: numeric input, default 500, max 5000, min 1
  - [ ] Sort column: dropdown (options = selected dimensions + "# Games" when count on)
  - [ ] Sort direction: Ascending / Descending
  - [ ] When count on, default sort: "# Games" descending
- [ ] Wire to API

**Manual Testing 3.3:**
- [ ] Turn count on, no dimensions → single total count
- [ ] Turn count on, dimensions = league, date → GROUP BY league, date, count per group
- [ ] Change row limit to 10 → max 10 rows
- [ ] Sort by date ascending → results ordered correctly

---

## Phase 4: Results Display

### 4.1 Results Table

- [ ] Add results container in main area
  - [ ] Table with columns from selected dimensions (in order)
  - [ ] When count on: add "# Games" column
  - [ ] Display-only; no row-level interactions
  - [ ] Use display labels for column headers
  - [ ] Date format: YYYY-MM-DD
- [ ] Call API on Run click (or form submit)
  - [ ] Show loading state (spinner or skeleton) while request in flight
  - [ ] Render rows on success
  - [ ] Handle error: show "Unable to load data. Please try again."
  - [ ] Handle empty: show "No games match your filters."

**Manual Testing 4.1:**
- [ ] Select dimensions, click Run
- [ ] Loading state appears
- [ ] Table renders with correct columns
- [ ] Empty results show message
- [ ] Error (e.g., disconnect) shows user-friendly message

---

### 4.2 Results Summary & Row Numbers

- [ ] Add results summary above or below table
  - [ ] "Showing N rows" when N < limit
  - [ ] "N rows (limit reached)" when N equals limit (user may want to increase limit)
- [ ] Optional: subtle row numbers (1, 2, 3…) in first column
  - [ ] Muted styling, small font

**Manual Testing 4.2:**
- [ ] Run query returning 50 rows → "Showing 50 rows"
- [ ] Run with limit 10, 10 results → "10 rows (limit reached)"
- [ ] Row numbers visible if implemented

---

## Phase 5: URL State, Show SQL, Polish

### 5.1 URL State (Shareable Links)

- [ ] **URL param format** (same schema for both URL and API; keep URLs shareable):
  - [ ] `dimensions` — comma-separated: `league,date,home_team`
  - [ ] Low-cardinality filters: `sport`, `league`, `level`, `day`, `home_state` — comma-separated for multi: `sport=basketball,hockey`
  - [ ] High-cardinality (contains): `home_team`, `road_team`, `location`, `home_city` — single value each
  - [ ] Date: `date_mode` = `exact` | `range` | `year` | `last_week` | `last_month` | `last_n` | `next_week` | `next_n`
  - [ ] Date values: `date_exact` (YYYY-MM-DD), `date_start`/`date_end` (range), `date_year` (year), `date_n` (for last_n/next_n)
  - [ ] `anchor_date` — YYYY-MM-DD, "today" for relative modes (see 5.1a)
  - [ ] `count` — 0 or 1
  - [ ] `limit` — 1–5000
  - [ ] `sort_column`, `sort_dir` — asc | desc
  - [ ] Omit params that are empty/default
- [ ] Encode query params in URL using above schema
- [ ] Support decoding on page load: if URL has params, populate form and optionally auto-run
- [ ] Update URL when user runs query (replaceState or pushState)
- [ ] Handle long URLs (browser limits ~2000 chars); document tradeoff; consider shortening filter keys if needed

**Manual Testing 5.1:**
- [ ] Set dimensions, filters, run query
- [ ] Copy URL, open in new tab
- [ ] Verify form state restored from URL
- [ ] Optionally: verify auto-run on load with params

---

### 5.1a "Today" / Timezone for Relative Dates

- [ ] **Problem:** Relative dates (last week, next 30 days) need "today" as anchor. Sports Schedules is public (no auth), so no user account or stored timezone.
- [ ] **Approach:** Client sends `anchor_date` (YYYY-MM-DD) with each query that uses relative date mode.
  - [ ] Frontend computes "today" in the user's browser: use `new Date().toLocaleDateString('en-CA')` (YYYY-MM-DD in local timezone) or equivalent — `toISOString()` is UTC and wrong for local date.
  - [ ] Include `anchor_date` in API request when `date_mode` is relative.
  - [ ] Include `anchor_date` in URL when encoding state, so shared links use the same anchor (or omit and default to server date on load — document behavior).
- [ ] **Fallback:** If `anchor_date` is omitted for a relative query, server uses its own "today" (e.g., UTC date or app-configured timezone). Document this edge case.
- [ ] **Future:** If auth/user preferences are added later, use `user.preferred_timezone` or `user.time_zone` to compute anchor server-side; for now, client-sent anchor is sufficient.

**Manual Testing 5.1a:**
- [ ] Set "Last 7 days", run — verify date range uses correct anchor
- [ ] Change system date/timezone in browser (or mock), verify anchor reflects it
- [ ] Share URL with anchor_date, open in new tab — verify same range

---

### 5.2 Show SQL

- [ ] Add "Show SQL" link/control (small, muted)
  - [ ] Hidden by default or collapsed
  - [ ] Click expands to show SQL in monospace block
  - [ ] SQL comes from API response (`sql` field)
  - [ ] Visually secondary (small text, muted color)
- [ ] Only show after a successful query

**Manual Testing 5.2:**
- [ ] Run query
- [ ] Click "Show SQL"
- [ ] SQL block appears with generated query
- [ ] Collapse/expand works

---

### 5.3 Error Handling & Validation

- [ ] Query validation errors: show inline in sidebar or above results
- [ ] DoltHub timeout / API error: "Unable to load data. Please try again."
- [ ] Invalid date range: "Start date must be before or equal to end date."
- [ ] Invalid row limit: "Row limit must be between 1 and 5000."
- [ ] Log detailed errors server-side; never expose raw SQL errors to user

**Manual Testing 5.3:**
- [ ] Trigger validation error → user sees message
- [ ] Simulate DoltHub failure → generic message shown
- [ ] No stack traces or raw errors in UI

---

### 5.4 Mobile Responsiveness

- [ ] Sidebar collapsible on mobile (hamburger or accordion)
- [ ] Results table: horizontal scroll or card layout on small screens
- [ ] Touch targets ≥ 44px
- [ ] Run button accessible
- [ ] Text readable (min 16px for inputs)

**Manual Testing 5.4:**
- [ ] Test at 375px width
- [ ] No horizontal overflow
- [ ] All controls usable
- [ ] Table readable or scrollable

---

## Phase 6: Integration & Final Checks

### 6.1 End-to-End Flow

- [ ] Full flow: select dimensions (league, date, home_team, road_team)
- [ ] Apply filters: Sport=basketball, League=NBA
- [ ] Set date: Next 7 days
- [ ] Run query
- [ ] Verify results match filters
- [ ] Verify results summary
- [ ] Show SQL, verify SQL reflects selections
- [ ] Copy URL, open in new tab, verify state

**Manual Testing 6.1:**
- [ ] Complete flow as above
- [ ] Test with count on (dimensions + count)
- [ ] Test with contains filter (e.g., "Lakers")
- [ ] Test empty result set

---

### 6.2 Security & Edge Cases

- [ ] Verify dimension names from allowlist only
- [ ] Verify filter values sanitized (contains inputs)
- [ ] Test SQL injection attempts in contains fields → no breach
- [ ] Test very long filter values → handled gracefully
- [ ] Test limit=0, limit=-1 → validation rejects

**Manual Testing 6.2:**
- [ ] Try `' OR 1=1--` in Home Team → no unexpected results
- [ ] Try invalid dimension in URL → ignored or 400

---

## Completion Checklist

Before considering V1 complete:

- [ ] DoltHub client shared or correctly imported
- [ ] Query builder produces valid SQL for all combinations
- [ ] API returns rows and SQL
- [ ] All sidebar sections functional (Dimensions, Filters, Date, Options)
- [ ] Results table displays correctly
- [ ] Results summary and optional row numbers
- [ ] Show SQL works
- [ ] URL state works (shareable links)
- [ ] AND logic hint visible in Filters
- [ ] Error handling in place
- [ ] Mobile usable
- [ ] All CSS uses `ss-` prefix
- [ ] No auth required (public access)

---

## Out of Scope (V1)

- Natural language query
- Saved queries / bookmarks
- Export to CSV/Excel
- Pagination beyond row limit
- Authentication or user preferences
