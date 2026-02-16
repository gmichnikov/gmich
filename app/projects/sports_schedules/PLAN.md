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

### 1.2 Create Query Builder Module

- [ ] Create `app/projects/sports_schedules/core/` directory
- [ ] Create `app/projects/sports_schedules/core/__init__.py`
- [ ] Create `app/projects/sports_schedules/core/query_builder.py`
  - [ ] Define `DIMENSIONS` constant: list of (column, display_label) for sport, level, league, date, day, time, home_team, road_team, location, home_city, home_state
  - [ ] Define `LOW_CARDINALITY_FILTERS`: sport, league, level, day, home_state with static option lists
  - [ ] Define `HIGH_CARDINALITY_FILTERS`: home_team, road_team, location, home_city (contains search)
  - [ ] Create `build_sql(params)` function
    - [ ] Accept dict with: dimensions, filters (low + high), date_mode, date_value(s), count, limit, sort_column, sort_dir
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

**Manual Testing 1.2:**
- [ ] Unit test or manual call: `build_sql({"dimensions": ["league", "date"], "limit": 10})` → valid SELECT
- [ ] Test with count on, dimensions selected → GROUP BY present
- [ ] Test with count on, no dimensions → single COUNT(*)
- [ ] Test date modes: exact, range, year, last 7 days, next 30 days
- [ ] Test contains filter escaping (e.g., "O'Brien" → proper escaping)

---

### 1.3 Create Query API Endpoint

- [ ] Add `GET /sports-schedules/api/query` route in `routes.py`
  - [ ] Parse query params: dimensions (comma-separated), filters (JSON or repeated params), date_mode, date_start, date_end, date_exact, date_year, date_n, count, limit, sort_column, sort_dir
  - [ ] Call `build_sql()` with parsed params
  - [ ] If validation error, return `{"error": message}` with 400
  - [ ] Call DoltHub client `execute_sql(sql)`
  - [ ] If DoltHub error, return `{"error": "Unable to load data. Please try again."}` with 500
  - [ ] Return `{"rows": [...], "sql": sql_string}` (include SQL for "Show SQL" feature)
  - [ ] Handle empty results: return `{"rows": [], "sql": sql_string}` (no error)

**Manual Testing 1.3:**
- [ ] Call API with `?dimensions=league,date&limit=5`
- [ ] Verify rows returned
- [ ] Verify `sql` in response
- [ ] Test invalid params (e.g., limit=10000) → 400
- [ ] Test with filters applied

---

## Phase 2: Sidebar UI – Layout & Dimension Picker

### 2.1 Page Layout & Structure

- [ ] Update `templates/sports_schedules/index.html`
  - [ ] Replace placeholder with two-column layout: sidebar (left) + main area (right)
  - [ ] Sidebar: fixed or sticky, collapsible on mobile
  - [ ] Main area: results table container (initially empty state)
  - [ ] Add "Run" button (prominent, in sidebar or above results)
  - [ ] Use `ss-` prefix for all classes (e.g., `ss-sidebar`, `ss-main`, `ss-run-btn`)
- [ ] Add base styles in `static/css/sports_schedules.css`
  - [ ] Layout: flex or grid for sidebar + main
  - [ ] Sidebar width ~280px on desktop
  - [ ] Collapsible sections: Dimensions, Filters, Date, Options

**Manual Testing 2.1:**
- [ ] Page loads at `/sports-schedules/`
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

**Manual Testing 2.2:**
- [ ] Check/uncheck dimensions
- [ ] Verify selection order is preserved
- [ ] Empty state shows when nothing selected and count off

---

### 2.3 Filter Picker – Low-Cardinality (Multiselect)

- [ ] Add "Filters" collapsible section
  - [ ] Add hint: "All filters combined with AND"
  - [ ] Sport: multiselect dropdown (basketball, hockey, football, baseball, soccer)
  - [ ] League: multiselect — create `core/constants.py` with league list from ESPN `LEAGUE_MAP` (or import from `sports_schedule_admin.core.espn_client`); use `LEAGUE_DISPLAY_NAMES` for labels where available
  - [ ] Level: multiselect (pro, college)
  - [ ] Day: multiselect (Monday–Sunday)
  - [ ] State: multiselect (US state codes)
  - [ ] All optional; empty = no filter on that dimension
- [ ] Wire filter values to query params

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
  - [ ] Use "today" as anchor
  - [ ] Validate N > 0 for Last N / Next N
- [ ] Wire to query builder (compute date range server-side)

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

- [ ] Encode query params in URL
  - [ ] dimensions, filters, date params, count, limit, sort_column, sort_dir
  - [ ] Use query string (e.g., `?dimensions=league,date&sport=basketball`)
  - [ ] Support decoding on page load: if URL has params, populate form and optionally auto-run
- [ ] Update URL when user runs query (replaceState or pushState)
- [ ] Handle long URLs (browser limits); document tradeoff

**Manual Testing 5.1:**
- [ ] Set dimensions, filters, run query
- [ ] Copy URL, open in new tab
- [ ] Verify form state restored from URL
- [ ] Optionally: verify auto-run on load with params

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
