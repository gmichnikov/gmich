# Sports Schedules - Implementation Plan

This plan follows the Sports Schedules PRD and breaks implementation into smaller, testable chunks. The project is public (no login), read-only, and uses DoltHub as the data source.

**Status:** Phase 1 ✅ Phase 2 ✅ Phase 3 ✅ Phase 4 ✅ Phase 5 ✅ Phase 6 🔲

---

## Relevant Files

- `app/projects/sports_schedules/__init__.py` - Blueprint initialization.
- `app/projects/sports_schedules/routes.py` - Page and API routes.
- `app/projects/sports_schedules/templates/sports_schedules/index.html` - Main viewer template.
- `app/projects/sports_schedules/static/css/sports_schedules.css` - Styles (all classes use `ss-` prefix).
- `app/projects/sports_schedules/core/query_builder.py` - Build SQL from user selections.
- `app/projects/sports_schedules/core/constants.py` - Filter options (sport, league, level, day, state) for UI.
- `app/core/dolthub_client.py` - Shared DoltHub read client.
- `app/__init__.py` - App initialization (register blueprint).
- `app/projects/registry.py` - Project registry (if needed).

### Notes

- All CSS classes must use the `ss-` prefix to avoid collisions with other projects.
- No database migrations; this project reads from DoltHub only.
- League options come from ESPN config (`LEAGUE_MAP`, `LEAGUE_DISPLAY_NAMES`).

---

## Phase 1: Shared Infrastructure & Query Building [COMPLETED]

### 1.1 Extract DoltHub Client to Shared Module [COMPLETED]

- [x] Create `app/core/` directory if it does not exist
- [x] Create `app/core/__init__.py` (empty or minimal)
- [x] Create `app/core/dolthub_client.py`
  - [x] Move full `DoltHubClient` from `sports_schedule_admin/core/dolthub_client.py` (read + write + batch_upsert)
  - [x] Admin needs write and batch_upsert for sync; sports_schedules only uses `execute_sql` for reads
- [x] Update `sports_schedule_admin/core/dolthub_client.py`
  - [x] Replace with: `from app.core.dolthub_client import DoltHubClient` (re-export or delete file and update imports)
- [x] Update all imports in sports_schedule_admin (routes, logic, commands) to use `app.core.dolthub_client`
- [x] Add `from app.core.dolthub_client import DoltHubClient` in sports_schedules routes
- [x] Verify sports_schedule_admin still works (sync, preview, coverage)

**Manual Testing 1.1:**
- [x] Run a DoltHub read query from sports_schedule_admin (e.g., preview)
- [x] Verify no import errors
- [x] Confirm env vars (`DOLTHUB_API_TOKEN`, etc.) still apply

---

### 1.2 Create Constants Module (Low-Cardinality Fields) [COMPLETED]

- [x] Create `app/projects/sports_schedules/core/` directory
- [x] Create `app/projects/sports_schedules/core/__init__.py`
- [x] Create `app/projects/sports_schedules/core/constants.py`
  - [x] **Sport:** `SPORTS = ["basketball", "hockey", "football", "baseball", "soccer"]` (schema values)
  - [x] **League:** Build from `sports_schedule_admin.core.espn_client`: `LEAGUES = list(LEAGUE_MAP.keys())`; for labels use `LEAGUE_DISPLAY_NAMES.get(code, code)` so CL→"Champions League (CL)", NBA→"NBA"
  - [x] **Level:** `LEVELS = ["pro", "college"]`
  - [x] **Day:** `DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]`
  - [x] **State:** `STATES` — US state codes (AL, AK, AZ, … WY); use a standard list (e.g., `us.states` or hand-maintained)
  - [x] Export `LOW_CARDINALITY_OPTIONS`: dict mapping column → list of `(value, label)` for UI multiselects (e.g. league: `[("NBA", "NBA"), ("CL", "Champions League (CL)"), ...]`; sport/level/day/state: value and label can match or use title case)
  - [x] Export `DIMENSION_LABELS` — column → display label mapping (Sport, Level, League, Date, Day, Time (ET), etc.)
- [x] **Usage:** Constants are the single source of truth. Query builder validates filter values against these allowlists before building SQL. Frontend gets options by passing `LOW_CARDINALITY_OPTIONS` and `DIMENSION_LABELS` from the index route to the template (no separate API needed for options).

**Manual Testing 1.2:**
- [x] Import constants; verify all option lists non-empty
- [x] League list includes NBA, NHL, EPL, etc.; display names correct for CL, EL, etc.

---

### 1.3 Create Query Builder Module [COMPLETED]

- [x] Create `app/projects/sports_schedules/core/query_builder.py`
  - [x] Import `LOW_CARDINALITY_OPTIONS`, `DIMENSION_LABELS` from `constants`
  - [x] Define `DIMENSIONS` from constants (column, display_label)
  - [x] Define `HIGH_CARDINALITY_FILTERS`: home_team, road_team, location, home_city (contains search — no fixed options)
  - [x] **Low-cardinality validation:** When building WHERE, validate each filter value is in the corresponding allowlist from constants; reject unknown values (return error or ignore)
  - [x] **Run requirement validation:** Reject if no dimensions selected AND count is off — return error e.g. "Select at least one dimension or turn on count to run a query." (PRD: user must select at least one dimension, OR turn on count)
  - [x] Create `build_sql(params)` function
    - [x] Accept dict with: dimensions, filters (low + high), date_mode, date_exact, date_start, date_end, date_year, date_n, anchor_date (for relative modes), count, limit, sort_column, sort_dir
    - [x] Build SELECT clause from dimensions (or `*` if none and no count)
    - [x] Add COUNT(*) and GROUP BY when count is on
    - [x] Build WHERE clause from filters (AND logic)
    - [x] Add date conditions (exact, range, year, last N days, next N days)
    - [x] Sanitize contains filters: escape single quotes, handle `%` and `_` for LIKE
    - [x] Add ORDER BY from sort_column, sort_dir
    - [x] Add LIMIT (default 500, max 5000)
    - [x] Return `(sql_string, error_message)` — error_message if validation fails
  - [x] Validate: row limit 1–5000, date range start ≤ end, relative N > 0
  - [x] Use allowlist for dimensions; never accept raw user input for column names
  - [x] Case-insensitive contains (LOWER on both sides of LIKE)

**Manual Testing 1.3:**
- [x] Unit test or manual call: `build_sql({"dimensions": [], "count": 0})` → validation error
- [x] Unit test or manual call: `build_sql({"dimensions": ["league", "date"], "limit": 10})` → valid SELECT
- [x] Test with count on, dimensions selected → GROUP BY present
- [x] Test with count on, no dimensions → single COUNT(*)
- [x] Test date modes: exact, range, year, last 7 days, next 30 days
- [x] Test contains filter escaping (e.g., "O'Brien" → proper escaping)

---

### 1.4 Create Query API Endpoint [COMPLETED]

- [x] Add `GET /sports-schedules/api/query` route in `routes.py`
  - [x] Parse query params per URL schema (5.1): dimensions, filters (sport, league, level, day, home_state, home_team, road_team, location, home_city), date_mode, date_exact, date_start, date_end, date_year, date_n, anchor_date, count, limit, sort_column, sort_dir
  - [x] Call `build_sql()` with parsed params
  - [x] If validation error (including no-dimensions-and-no-count), return `{"error": message}` with 400
  - [x] Call DoltHub client `execute_sql(sql)`
  - [x] If DoltHub error, return `{"error": "Unable to load data. Please try again."}` with 500
  - [x] Return `{"rows": [...], "sql": sql_string}` (include SQL for "Show SQL" feature)
  - [x] Handle empty results: return `{"rows": [], "sql": sql_string}` (no error)

**Manual Testing 1.4:**
- [x] Call API with no dimensions and count=0 → 400 with validation error
- [x] Call API with `?dimensions=league,date&limit=5`
- [x] Verify rows returned
- [x] Verify `sql` in response
- [x] Test invalid params (e.g., limit=10000) → 400
- [x] Test with filters applied

---

## Phase 2: Sidebar UI – Layout & Dimension Picker [COMPLETED]

### 2.1 Page Layout & Structure [COMPLETED]

- [x] **Page container (separate from homepage purple):** Update `ss-wrapper` to act as a contained UI panel so the site’s purple gradient doesn’t bleed through. Follow pattern from sports_schedule_admin (`ssa-wrapper`) or betfake (`bf-page-wrapper`): give `ss-wrapper` its own background (e.g., white or light neutral), padding, optionally border-radius and box-shadow. Content should read as a distinct panel/card, not floating on the homepage background.
- [x] Update `routes.py` index route to pass `LOW_CARDINALITY_OPTIONS` and `DIMENSION_LABELS` from constants to template
- [x] Update `templates/sports_schedules/index.html`
  - [x] Replace placeholder with two-column layout: sidebar (left) + main area (right)
  - [x] Sidebar: fixed or sticky, collapsible on mobile
  - [x] Main area: results table container (initially empty state)
  - [x] Add "Run" button (prominent, in sidebar or above results)
  - [x] Use `ss-` prefix for all classes (e.g., `ss-sidebar`, `ss-main`, `ss-run-btn`)
- [x] Add base styles in `static/css/sports_schedules.css`
  - [x] `ss-wrapper`: background, padding, max-width, margin; optional border-radius, box-shadow
  - [x] Layout: flex or grid for sidebar + main
  - [x] Sidebar width ~280px on desktop
  - [x] Collapsible sections: Dimensions, Filters, Date, Options

**Manual Testing 2.1:**
- [x] Page loads at `/sports-schedules/`
- [x] Page has its own background panel — purple gradient from homepage does not show through content area
- [x] Sidebar and main area visible
- [x] Run button visible
- [x] No layout shift or overflow on desktop

---

### 2.2 Dimension Picker [COMPLETED]

- [x] Add "Dimensions" collapsible section in sidebar
  - [x] Section header: "Dimensions" with expand/collapse toggle
  - [x] Checkbox list for each dimension: Sport, Level, League, Date, Day, Time (ET), Home Team, Road Team, Location, City, State
  - [x] Use display labels from PRD (e.g., "Time (ET)" not "time")
  - [x] Column order in results = checkbox selection order
  - [x] No dimensions selected by default
- [x] Wire dimension state to a JS object or hidden inputs for form submit
- [x] Add "Select dimensions and click Run to view schedules" empty-state message when no dimensions and no count
- [x] **Run button validation:** When user clicks Run with no dimensions and count off, either disable the button or show inline validation message ("Select at least one dimension or turn on count") — prefer inline message so user understands the requirement

**Manual Testing 2.2:**
- [x] Check/uncheck dimensions
- [x] Verify selection order is preserved
- [x] Empty state shows when nothing selected and count off
- [x] Click Run with no dimensions and count off → validation message shown (or API returns 400, show error)

---

### 2.3 Filter Picker – Low-Cardinality (Multiselect) [COMPLETED]

- [x] Add "Filters" collapsible section
  - [x] Add hint: "All filters combined with AND"
  - [x] Populate multiselect options from `core/constants.LOW_CARDINALITY_OPTIONS` (expose via API or embed in template)
  - [x] Sport: multiselect from `SPORTS`
  - [x] League: multiselect from `LEAGUES` (use display names for labels)
  - [x] Level: multiselect from `LEVELS`
  - [x] Day: multiselect from `DAYS`
  - [x] State: multiselect from `STATES`
  - [x] All optional; empty = no filter on that dimension
- [x] Wire filter values to query params (values sent must match constants; backend validates)

**Manual Testing 2.3:**
- [x] Select Sport = basketball, League = NBA
- [x] Run query, verify results filtered
- [x] Verify AND hint visible

---

### 2.4 Filter Picker – High-Cardinality (Contains Search) [COMPLETED]

- [x] Add contains-search inputs in Filters section
  - [x] Home Team: text input, placeholder "e.g., Celtics"
  - [x] Road Team: text input
  - [x] Location: text input (venue name)
  - [x] City: text input
  - [x] Case-insensitive contains (LIKE %value%)
- [x] Wire to query builder; ensure server-side escaping

**Manual Testing 2.4:**
- [x] Enter "Celtics" in Home Team, run query
- [x] Verify only games with "Celtics" in home_team
- [x] Test special chars (apostrophe) — no SQL error

---

## Phase 3: Date Filter & Options [mostly COMPLETED]

### 3.1 Date Filter – Absolute Modes [COMPLETED]

- [x] Add "Date" collapsible section
  - [x] Mode selector: Exact date | Date range | Year only
  - [x] Exact date: single date input (YYYY-MM-DD)
  - [x] Date range: start date + end date (inclusive)
  - [x] Year only: year input (e.g., 2026)
  - [x] Validate: start ≤ end for range (backend)
- [x] Wire date params to API

**Manual Testing 3.1:**
- [ ] Select exact date 2026-02-19, run → only that date
- [ ] Select range 2026-02-01 to 2026-02-28 → only that range
- [ ] Select year 2026 → all games in 2026
- [ ] Invalid range (end before start) → validation error

---

### 3.2 Date Filter – Relative Modes [COMPLETED]

- [x] Add relative date options to Date section
  - [x] Last week (7 days), Last month (30 days), Last N days (N input)
  - [x] Next week (7 days), Next N days (N input)
  - [x] Validate N > 0 for Last N / Next N
- [x] **"Today" / anchor date:** Client sends `anchor_date` (YYYY-MM-DD) via `toLocaleDateString('en-CA')` so "today" is user-local without requiring auth.

**Manual Testing 3.2:**
- [ ] Select "Last week" → past 7 days from today
- [ ] Select "Next 30 days" → next 30 days from today
- [ ] Select "Last 14 days" → past 14 days

---

### 3.3 Options: Count, Row Limit, Sort [COMPLETED]

- [x] Add "Options" collapsible section
  - [x] "Include count" toggle (default: off)
  - [x] Row limit: numeric input, default 500, max 5000, min 1
  - [x] Sort column: dropdown (options = selected dimensions + "# Games" when count on)
  - [x] Sort direction: Ascending / Descending
  - [x] When count on, default sort: "# Games" descending (backend default)
- [x] Wire count, limit, sort_column, sort_dir to API

**Manual Testing 3.3:**
- [x] Turn count on, no dimensions → single total count
- [x] Turn count on, dimensions = league, date → GROUP BY league, date, count per group
- [x] Change row limit to 10 → max 10 rows
- [ ] Sort by date ascending → results ordered correctly

---

## Phase 4: Results Display

### 4.1 Results Table [COMPLETED]

- [x] Add results container in main area
  - [x] Table with columns from selected dimensions (in order)
  - [x] When count on: add "# Games" column
  - [x] Display-only; no row-level interactions
  - [x] Use display labels for column headers
  - [x] Date format: YYYY-MM-DD
- [x] Call API on Run click (or form submit)
  - [x] Show loading state (spinner or skeleton) while request in flight
  - [x] Render rows on success
  - [x] Handle error: show "Unable to load data. Please try again."
  - [x] Handle empty: show row count (e.g. "Showing 0 rows")

**Manual Testing 4.1:**
- [x] Select dimensions, click Run
- [x] Loading state appears
- [x] Table renders with correct columns
- [x] Empty results show message
- [x] Error (e.g., disconnect) shows user-friendly message

---

### 4.2 Results Summary & Row Numbers [COMPLETED]

- [x] Add results summary above or below table
  - [x] "Showing N rows" when N < limit
  - [x] "N rows (limit reached)" when N equals limit (user may want to increase limit)
- [x] Optional: subtle row numbers (1, 2, 3…) in first column
  - [x] Muted styling, small font

**Manual Testing 4.2:**
- [x] Run query returning 50 rows → "Showing 50 rows"
- [x] Run with limit 10, 10 results → "10 rows (limit reached)"
- [ ] Row numbers visible if implemented

---

## Phase 5: URL State, Show SQL, Polish

### 5.1 URL State (Shareable Links) [COMPLETED]

- [x] **URL param format** (same schema for both URL and API; keep URLs shareable):
  - [x] `dimensions` — comma-separated: `league,date,home_team`
  - [x] Low-cardinality filters: `sport`, `league`, `level`, `day`, `home_state` — comma-separated for multi
  - [x] High-cardinality (contains): `home_team`, `road_team`, `location`, `home_city` — single value each
  - [x] Date: `date_mode`, `date_exact`, `date_start`/`date_end`, `date_year`, `date_n`, `anchor_date`
  - [x] `count`, `limit`, `sort_column`, `sort_dir`
  - [x] Omit params that are empty/default
- [x] Encode query params in URL using above schema
- [x] Support decoding on page load: if URL has params, populate form and auto-run
- [x] Update URL when user runs query (replaceState)
- [x] Handle long URLs: skip URL update if > 2000 chars

**Manual Testing 5.1:**
- [ ] Set dimensions, filters, run query
- [ ] Copy URL, open in new tab
- [ ] Verify form state restored from URL
- [ ] Verify auto-run on load with params

---

### 5.1a "Today" / Timezone for Relative Dates [COMPLETED]

- [x] **Problem:** Relative dates (last week, next 30 days) need "today" as anchor. Sports Schedules is public (no auth), so no user account or stored timezone.
- [x] **Approach:** Client sends `anchor_date` (YYYY-MM-DD) with each query that uses relative date mode.
  - [x] Frontend computes "today" in the user's browser: use `new Date().toLocaleDateString('en-CA')` (YYYY-MM-DD in local timezone) or equivalent — `toISOString()` is UTC and wrong for local date.
  - [x] Include `anchor_date` in API request when `date_mode` is relative.
  - [x] Include `anchor_date` in URL when encoding state
- [x] **Fallback:** If `anchor_date` is omitted for a relative query, server uses its own "today" (e.g., UTC date or app-configured timezone).
- [x] **Future:** If auth/user preferences are added later, use `user.preferred_timezone` or `user.time_zone` to compute anchor server-side; for now, client-sent anchor is sufficient.

**Manual Testing 5.1a:**
- [ ] Set "Last 7 days", run — verify date range uses correct anchor
- [ ] Change system date/timezone in browser (or mock), verify anchor reflects it
- [ ] Share URL with anchor_date, open in new tab — verify same range

---

### 5.2 Show SQL [COMPLETED]

- [x] Add "Show SQL" link/control (small, muted)
  - [x] Hidden by default or collapsed
  - [x] Click expands to show SQL in monospace block
  - [x] SQL comes from API response (`sql` field)
  - [x] Visually secondary (small text, muted color)
- [x] Only show after a successful query

**Manual Testing 5.2:**
- [ ] Run query
- [ ] Click "Show SQL"
- [ ] SQL block appears with generated query
- [ ] Collapse/expand works

---

### 5.3 Error Handling & Validation [COMPLETED]

- [x] Query validation errors: show inline in sidebar or above results
- [x] DoltHub timeout / API error: "Unable to load data. Please try again."
- [x] Invalid date range: "Start date must be before or equal to end date." (backend)
- [x] Invalid row limit: "Row limit must be between 1 and 5000." (backend)
- [x] Invalid N days: "Number of days must be greater than 0." (client + backend)
- [x] Log detailed errors server-side; never expose raw SQL errors to user

**Manual Testing 5.3:**
- [ ] Trigger validation error → user sees message
- [ ] Simulate DoltHub failure → generic message shown
- [ ] No stack traces or raw errors in UI

---

### 5.4 Mobile Responsiveness [COMPLETED]

- [x] Sidebar collapsible on mobile (sections collapse; column layout on narrow)
- [x] Results table: horizontal scroll (`overflow-x: auto` on wrapper)
- [x] Touch targets ≥ 44px (section headers, Run button, checkboxes, Show SQL)
- [x] Run button accessible
- [x] Text readable (16px for inputs — prevents iOS zoom)

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

- [x] DoltHub client shared or correctly imported
- [x] Query builder produces valid SQL for all combinations
- [x] API returns rows and SQL
- [x] All sidebar sections functional (Dimensions, Filters, Date, Options)
- [x] Results table displays correctly
- [x] Results summary and optional row numbers
- [x] Show SQL works
- [x] URL state works (shareable links)
- [x] AND logic hint visible in Filters
- [x] Error handling in place
- [x] Mobile usable
- [x] All CSS uses `ss-` prefix
- [x] No auth required (public access)

---

## Out of Scope (V1)

- Natural language query
- Saved queries / bookmarks
- Export to CSV/Excel
- Pagination beyond row limit
- Authentication or user preferences
