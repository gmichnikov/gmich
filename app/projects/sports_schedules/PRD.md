# Sports Schedules - Product Requirements Document

## Overview

Sports Schedules is a **public, no-login** UI for viewing sports schedule data stored in DoltHub. It functions as a visual query builder—users select dimensions (columns), apply filters, and optionally include a count. The data source is the `combined-schedule` table populated by the Sports Schedule Admin project.

## Project Details

- **Project name:** `sports_schedules`
- **Route prefix:** `/sports-schedules`
- **CSS prefix:** `ss-` (all classes must use this prefix)
- **Data source:** DoltHub `combined-schedule` table (read-only)
- **Authentication:** None
- **Database:** None (no app DB usage; reads from DoltHub API)

## Goals

1. Let any user browse and filter sports schedules without SQL knowledge.
2. Provide a BI-tool-style interface: pick dimensions, apply filters, optionally get a count.
3. Support both low-cardinality filters (multiselect) and high-cardinality filters (contains search).
4. Offer flexible date filtering (absolute and relative).

## Data Schema (Source: `combined-schedule`)

| Column      | Type   | Notes                          |
|-------------|--------|--------------------------------|
| primary_key | varchar| Internal; not user-filterable  |
| sport       | varchar| e.g., basketball, hockey       |
| level       | varchar| e.g., pro, college            |
| league      | varchar| e.g., NBA, NCAAM, EPL          |
| date        | date   | Game date                      |
| day         | varchar| e.g., Thursday                 |
| time        | varchar| e.g., 7:30 PM (Eastern)        |
| home_team   | varchar| Home team name                 |
| road_team   | varchar| Away/road team name            |
| location    | varchar| Venue name                     |
| home_city   | varchar| City                           |
| home_state  | varchar| State (e.g., MA, CA)           |

---

## Core Components

### 1. Dimension Picker (Columns to Include)

Users select which columns appear in the result table.

**Selectable dimensions:** sport, level, league, date, day, time, home_team, road_team, location, home_city, home_state

- **primary_key** is not exposed as a dimension.
- To run a query: user must select at least one dimension, OR turn on count (which can return a total with zero dimensions).
- **UI:** Checkbox list. Column order in results follows checkbox selection order.
- **Display labels:** Use human-readable labels in the UI (see table below).

### 2. Filter Picker

Users apply filters to narrow results. **All filtering is optional**—dimension filters, date filter, and contains searches can all be left empty. Filters combine with AND logic.

#### Low-Cardinality Filters (Multiselect Dropdowns)

| Filter     | Column     | Behavior                                      |
|------------|------------|-----------------------------------------------|
| Sport      | sport      | Multiselect; e.g., basketball, hockey         |
| League     | league     | Multiselect; e.g., NBA, NHL, EPL              |
| Level      | level      | Multiselect; e.g., pro, college               |
| Day        | day        | Multiselect; e.g., Thursday, Saturday         |
| State      | home_state | Multiselect; e.g., MA, CA, NY                 |

Options use static lists from known schema: sport (basketball, hockey, football, baseball, soccer), level (pro, college), league (from ESPN config: NBA, NHL, MLB, etc.), day (Monday–Sunday), state (US state codes).

#### High-Cardinality Filters (Contains Search)

| Filter        | Column     | Behavior                                      |
|---------------|------------|-----------------------------------------------|
| Home Team     | home_team  | Case-insensitive "contains" (e.g., "Celtics") |
| Road Team     | road_team  | Case-insensitive "contains"                   |
| Location      | location   | Case-insensitive "contains" (venue name)       |
| City          | home_city  | Case-insensitive "contains"                   |

Single text input per filter. Matches rows where the column value contains the entered substring.

#### No Filters On

- **primary_key** – Internal identifier.
- **time** – Not needed for typical use cases.

### 3. Date Filter

One mode at a time. UI changes based on selected mode (e.g., single date picker vs. range vs. year input vs. N days input).

#### Absolute Date Options

| Mode        | Description                    | Example                    |
|-------------|--------------------------------|----------------------------|
| Exact date  | Single date                    | 2026-02-19                 |
| Date range  | Start and end date (inclusive) | 2026-02-01 to 2026-02-28   |
| Year only   | All games in a given year      | 2026                       |

#### Relative Date Options

| Mode        | Description                    | Example                    |
|-------------|--------------------------------|----------------------------|
| Last week   | Past 7 days                    | —                          |
| Last month  | Past 30 days                   | —                          |
| Last N days | User-specified N               | Last 14 days               |
| Next week   | Next 7 days                    | —                          |
| Next N days | User-specified N               | Next 30 days               |

Relative options use "today" as the anchor.

### 4. Optional Count Metric

- **Toggle:** "Include count" (default: off).
- When on: SQL uses `COUNT(*)` with `GROUP BY` on the selected dimensions.
- **Behavior:** When dimensions are selected: `GROUP BY` those dimensions, show count per group. When no dimensions selected: single total `COUNT(*)` (no GROUP BY).
- **Column label:** "# Games".
- **Count** is the only available metric in V1.

### 5. Row Limit

- **User input:** Numeric field for max rows returned.
- **Default:** 500.
- **Max:** 5000.
- Applied as `LIMIT N` in the SQL query.

### 6. Sort Order

- **Sort column:** User selects from the currently selected dimensions, or from "# Games" when count is on.
- **Direction:** Ascending or descending.
- **Default when count is on:** Sort by "# Games" descending (most games first).
- Applied as `ORDER BY column ASC/DESC` in the SQL query.

---

## UI Layout

- **BI-style sidebar:** Left sidebar with dimension picker, filters, date filter, count toggle, row limit, sort options.
- **Collapsible sections:** Sidebar sections (Dimensions, Filters, Date, Options) can be collapsed to save space.
- **Main area:** Results table.
- **First load:** No dimensions selected, no defaults. Show basic empty-state message (e.g., "Select dimensions and click Run to view schedules").
- **Run trigger:** Explicit "Run" button only (no auto-run).
- **Loading state:** Spinner or skeleton while query runs.
- **Mobile:** Usable on mobile; layout details to be refined once the UI exists.

### Column Display Labels

| Column     | Display Label |
|------------|---------------|
| sport      | Sport         |
| level      | Level         |
| league     | League        |
| date       | Date          |
| day        | Day           |
| time       | Time (ET)     |
| home_team  | Home Team     |
| road_team  | Road Team     |
| location   | Location      |
| home_city  | City          |
| home_state | State         |

---

## Technical Considerations

### Data Access

- **Read-only:** DoltHub SQL API (GET) for SELECT queries.
- **No write operations.**
- **Rate limits:** DoltHub may throttle; consider caching or debouncing.

### Query Construction

- Build SQL dynamically from user selections:
  - `SELECT` clause from dimension picker.
  - `WHERE` clause from filters (AND logic).
  - `GROUP BY` from dimensions when count is used with grouping.
  - `COUNT(*)` when count metric is on.

### Performance

- Row limit (default 500, max 5000) applied to all queries.
- Pagination and export are out of scope for V1.

### DoltHub Client

- Reuse read-only DoltHub client from sports_schedule_admin. Extract to shared module (e.g., `app/core/dolthub_client.py` or `app/projects/sports_common/`) so both projects import it. Same env vars: `DOLTHUB_API_TOKEN`, `DOLTHUB_OWNER`, `DOLTHUB_REPO`, `DOLTHUB_BRANCH`.

### Error Handling

- **Query timeout / DoltHub down:** Show user-friendly message (e.g., "Unable to load data. Please try again.").
- **Invalid SQL / API error:** Show brief error message; log details server-side.
- **Empty results:** "No games match your filters."

### URL State

- Encode query params (dimensions, filters, date, count, limit, sort) in the URL so views are shareable and bookmarkable.
- **Downsides:** URLs can get long with many filters; need to handle encoding/decoding; browser history may fill with query variations. Acceptable tradeoff for shareability.

### Validation

- **Row limit:** 1–5000 (default 500).
- **Date range:** Start date must be ≤ end date.
- **Relative N days:** N must be > 0.

### Security

- **Dimensions:** Column names come from a fixed allowlist only; never from user input.
- **Multiselect filters:** Values come from static option lists.
- **Contains filters:** User-entered strings must be escaped/parameterized appropriately for the SQL dialect (e.g., single-quote escaping for LIKE patterns).

---

## Out of Scope (V1)

- Natural language query ("When do the Red Sox play?").
- Saved queries or bookmarks.
- Export to CSV/Excel.
- Authentication or user preferences.
