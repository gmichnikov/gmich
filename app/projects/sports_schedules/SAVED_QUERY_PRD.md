# Sports Schedules — Saved Queries PRD

## Overview

Add **saved queries** to Sports Schedules. The feature is optional and only available when a user is signed in. The main project stays public and does not require login for browsing or running queries.

---

## User Stories

1. **As an anonymous user**, I can run queries and see results. When I click Save, I am taken to login and returned with my exact query state intact, then prompted to name and save it.

2. **As a logged-in user**, I see sample queries (everyone) and my saved queries. I can click any to load and run it. After running a query, I can click Save to store it with a name. I can delete my saved queries.

3. **As a returning user**, I see my saved queries and can quickly re-run common views (e.g., "NBA this weekend", "Michigan basketball home games") without rebuilding the query.

---

## Core Requirements

### Sample Queries (Hardcoded)

- **2–3 sample queries** that everyone sees, regardless of login state.
- Examples: "NBA next 7 days", "College basketball this weekend in Michigan", etc.
- Implemented as static config in `sample_queries.py`.
- Clicking loads the query config and runs it.
- No edit/delete for samples.

### User-Saved Queries

- **Name** and **query config** per saved query.
- Query config = same structure as URL params: dimensions, filters, date_mode, date_exact, etc.
- Clicking a saved query populates the form and runs the query.
- **Delete** supported; **edit** not supported (delete + save new if needed).
- Only visible when user is logged in.

### Save Flow

- **Save button** in `ss-results-actions` (alongside Copy, Copy URL, Download CSV). Visible only after a query has been run; enabled when there is a runnable query state (≥1 dimension or count selected).
- **Not logged in:** Click Save → redirect to `auth.login` with `next` = full sports-schedules URL including query params + `&prompt_save=1` → after login, return with state intact, auto-open Save modal.
- **Logged in:** Click Save → open modal to enter query name → submit to save.

### Auth Integration

- Use existing `url_for('auth.login', next=...)` for post-login redirect.
- `next` must be the full sports-schedules index URL with all query params (e.g. `/sports-schedules?dimensions=date,home_team&date_mode=next_week&...`).
- On return, page loads with URL params → existing `ssApplyParamsFromUrl` populates form → user can then Save (modal opens).

---

## Additional Considerations

### 1. Duplicate Names

- **Decision:** Allow duplicates (user may want "NBA Home" for different leagues over time). If we disallow in future, show clear error: "You already have a saved query with that name."

### 2. Save Modal: When to Open After Login

- Add `prompt_save=1` to the `next` URL when Save triggered the login redirect. On load, if `prompt_save=1` and user is logged in, auto-open the Save modal. Use `history.replaceState()` to strip `prompt_save` from the URL so refresh does not re-open the modal.

### 3. Limit on Saved Queries

- **Decision:** 20 per user. Use a `SAVED_QUERY_LIMIT = 20` constant. Return clear error if limit reached.

### 4. Query Config Storage Format

- Store as **JSON**: same shape as `_parse_query_params()` returns — i.e. what `build_sql()` consumes.
- Keys: `dimensions` (comma-separated string), `filters` (dict: e.g. `league: ["NBA"]`, `home_team: "Celtics"`, `either_team: ["Team1", "Team2"]`), `date_mode`, `date_exact`, `date_start`, `date_end`, `date_year`, `date_n`, `anchor_date`, `count` (bool), `limit`, `sort_column`, `sort_dir`.
- For relative date modes (`this_weekend`, `next_week`, `last_n`, `next_n`): store the mode; `anchor_date` can be omitted or null — filled with "today" at load time. Loader computes `date_start`/`date_end` or `date_exact` as needed before running (same as current frontend logic — e.g. `ssComputeThisWeekend()` for `this_weekend`).

**Config ↔ URL mapping (`either_team`):** Both conversions are frontend (JavaScript) logic. URLs use `either_team_1` and `either_team_2`; stored config uses `filters.either_team` as an array. When converting:
- **Config → URL** (for loading into form): map `either_team: [a, b]` to `either_team_1=a`, `either_team_2=b` (empty if absent).
- **URL → Config** (for Save): map `either_team_1` + `either_team_2` from `ssCollectParams` to `filters.either_team = [v1, v2]` (filtering out empties).

### 5. Sample vs. User Query UX

- **Visual distinction:** Samples have a "Sample" badge; user queries show a delete button.
- **Ordering:** Samples first, then user queries (e.g., by created_at desc).

### 6. "Save As" vs. "Save"

- With no-edit rule, "Save" always creates a new saved query.
- If user runs a saved query and clicks Save, they create a duplicate.
- **Decision:** Allow saving again — it becomes a new saved query. "Already saved" detection (config hash) is future enhancement.

### 7. SQL vs. Config Storage

- Store **query config** (params), not raw SQL. SQL is derived by `build_sql()` and may change with schema/query-builder updates.
- **Decision:** Store config only.

### 8. Invalid/Stale Saved Queries

- If constants or schema change, a saved query might produce an error when run.
- **Decision:** Run as-is; show error to user. Don't block save/load on validation.

### 9. Empty / No Results

- User can save a query that returns 0 rows. That's valid (e.g., "Games on Christmas" when none exist).
- **Decision:** Allow saving regardless of result count.

### 10. UI Placement

- **Placement:** Collapsible section **above the filter bar** in the main area (not in the sidebar).
- Filter bar shows active filters; saved queries sit above it.
- **Collapsed vs expanded:** Collapsed when there are only sample queries (no user saved queries); expanded when user has at least one saved query.
- **Title:** "Saved Queries".

---

## Data Model

```python
# New model — add to app/projects/sports_schedules/models.py (project-specific, matching football_squares, meals, etc.)
class SportsScheduleSavedQuery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # User-facing name
    config = db.Column(db.Text, nullable=False)       # JSON: dimensions, filters, date_*, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __tablename__ = 'sports_schedule_saved_queries'
```

- Index on `user_id` for fast listing.
- No unique constraint on (user_id, name) if we allow duplicates.

---

## API Endpoints

| Method | Route | Auth | Purpose |
|--------|-------|------|---------|
| GET | `/sports-schedules/api/saved-queries` | Optional | List sample + user queries (user's only if logged in) |
| POST | `/sports-schedules/api/saved-queries` | Required | Create saved query (name + config from current params) |
| DELETE | `/sports-schedules/api/saved-queries/<id>` | Required | Delete (verify `query.user_id == current_user.id`) |

**POST error responses (for client display):**

| Condition | HTTP | Body |
|-----------|------|------|
| Not authenticated | 401 | `{"error": "Login required"}` |
| Limit (20) reached | 400 | `{"error": "Saved query limit (20) reached. Delete one to save a new query."}` |
| Invalid name (empty, >100 chars) | 400 | `{"error": "Name is required"}` or `{"error": "Name must be 100 characters or less"}` |
| Invalid config (missing, malformed, >2KB) | 400 | `{"error": "Invalid query config"}` |

---

## Sample Query Config

Samples live in code, e.g.:

```python
# In app/projects/sports_schedules/core/sample_queries.py
SAMPLE_QUERIES = [
    {
        "id": "sample-nba-next7",
        "name": "NBA next 7 days",
        "config": {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"league": ["NBA"]},
            "date_mode": "next_week",
            "anchor_date": None,  # filled at runtime with today
        },
    },
    {
        "id": "sample-college-bball-mi-weekend",
        "name": "College basketball this weekend in Michigan",
        "config": {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"league": ["NCAAM", "NCAAW"], "home_state": ["MI"]},
            "date_mode": "this_weekend",
            "anchor_date": None,
        },
    },
    {
        "id": "sample-pro-hockey-mi",
        "name": "Pro hockey in Michigan",
        "config": {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"league": ["NHL"], "home_state": ["MI"]},
            "date_mode": "next_week",
            "anchor_date": None,
        },
    },
]
```

- `anchor_date` and other relative date params: fill at runtime when loading (same as today's behavior).
- For `this_weekend`, loader must compute `date_start`/`date_end` using equivalent logic to `ssComputeThisWeekend()`.
- Sample IDs are string identifiers for UI (e.g., to attach delete handler only to user queries).

---

## Additional Improvement Ideas

### UX Polish

- **Delete confirmation:** Inline "Are you sure?" or undo toast ("Deleted. Undo?") for 5 seconds before hard delete. Simpler: single click delete with no undo.
- **Save/Delete feedback:** Brief toast after save ("Saved as 'NBA this weekend'") and after delete ("Removed").
- **Empty state:** When user has no saved queries: "Save your current query to quickly access it later" CTA in the collapsible area.
- **Sample tooltips:** Optional short description on hover (e.g. "NBA games in the next 7 days").
- **Loading state:** When clicking a saved query, show loading indicator; optionally disable Run/Save until load + run completes.

### Sorting

- **Sort user queries:** By `created_at` desc (newest first).

### Accessibility & Keyboard

- **Keyboard nav:** Tab through saved query buttons; Enter to run.
- **ARIA:** Collapsible has `aria-expanded`, `aria-controls`; list has `role="list"` or `role="group"`.
- **Save shortcut:** Avoid Cmd+S (browser conflict); consider no shortcut for v1.

### Mobile & Responsive

- **Layout:** Collapsible helps; query list could wrap or scroll horizontally on narrow screens. Ensure tap targets are adequate (44px min).
- **Modal:** Save modal should be usable on mobile (full-width or centered, not cut off).

### Edge Cases

- **Very long names:** Truncate with ellipsis in list; show full name on hover or in modal.
- **XSS:** Escape user-provided names when rendering (e.g. in saved-queries list).
- **Many saved queries:** If at limit (20), show "Limit reached. Delete one to save a new query." in Save modal.
- **Concurrent edits:** Low risk; single user. No special handling.

### Future / Out of Scope for v1

- **Share link:** Generate URL that loads a saved query (read-only) — requires shareable IDs or slugs.
- **Import/export:** Download saved queries as JSON; import from file.
- **Duplicate detection:** "This matches an existing saved query. Save anyway?" when config hash matches.

---

## Open Questions

- **`next` URL length:** Browsers limit URL length (~2K). Very filter-heavy queries could truncate. Mitigation: keep filters concise; if needed later, store in session instead of `next`.

---

## Summary

| Feature | Behavior |
|---------|----------|
| Sample queries | 2–3 hardcoded, everyone sees, load + run on click |
| User saved queries | Name + config, user-scoped, load + run, delete, no edit |
| Save button | Visible after run; if not logged in → login with `next` + `prompt_save=1` → return → open Save modal |
| Storage | JSON config (not SQL) |
| Auth | Optional; Save/create/list user queries require login |

---

## Implementation Plan

**Status:** Phase 1 ✅ Phase 2 ✅ Phase 3 ✅ Phase 4 ✅ Phase 5 ✅

---

### Phase 1: Data Model & Migration

- [x] Create `SportsScheduleSavedQuery` model
  - [x] Add to `app/projects/sports_schedules/models.py` (project-specific, matching other projects)
  - [x] Columns: `id`, `user_id` (FK to user), `name` (String 100), `config` (Text/JSON), `created_at`
  - [x] Table name: `sports_schedule_saved_queries`
  - [x] Relationship: `user_id` → `user.id`
- [x] Add index on `user_id` for listing queries by user
- [x] Use `ondelete="CASCADE"` on `user_id` FK
- [x] Ensure models module is imported (e.g. when registering blueprint) so Flask-Migrate discovers it
- [x] Request user to run `flask db migrate -m "Add SportsScheduleSavedQuery"` and `flask db upgrade`

**Manual Testing Phase 1:**
- [x] Migration applies cleanly
- [x] Can create/query records in Flask shell

---

### Phase 2: Sample Queries & Config Serialization

- [x] Create sample queries config
  - [x] Add `app/projects/sports_schedules/core/sample_queries.py`
  - [x] Define 2 `SAMPLE_QUERIES` as list of dicts: `id`, `name`, `config`
  - [x] Sample 1: "Games in New Jersey this weekend" — filters `home_state: ["NJ"]`, date_mode=this_weekend
  - [x] Sample 2: "Celtics games in the next month" — filters `either_team: ["Celtics"]`, date_mode=next_n, date_n=30
- [x] Implement config → params conversion in frontend (JavaScript)
  - [x] Helper to convert config dict to `URLSearchParams` for `ssApplyParamsFromUrl` (see Config ↔ URL mapping in §4)
  - [x] For relative date modes: fill `anchor_date` with today; compute `date_start`/`date_end` for this_weekend, `date_exact` for today, etc. — match existing frontend logic
- [x] Implement URL params → config conversion in frontend (JavaScript)
  - [x] Map `ssCollectParams` output to `_parse_query_params()` shape (e.g. `either_team_1`+`either_team_2` → `filters.either_team`)
  - [x] Serialize to JSON for storage

**Manual Testing Phase 2:**
- [x] Sample configs load correctly
- [x] Config → params produces valid query when passed to `build_sql`

---

### Phase 3: API Endpoints

- [x] GET `/sports-schedules/api/saved-queries`
  - [x] No auth required
  - [x] Return `{ samples: [...], user_queries: [...] }`
  - [x] `samples`: always include all from `SAMPLE_QUERIES`; each `{ id, name, config }` (id is string)
  - [x] `user_queries`: if `current_user.is_authenticated`, fetch `SportsScheduleSavedQuery.query.filter_by(user_id=current_user.id).order_by(SportsScheduleSavedQuery.created_at.desc())`; else `[]`
  - [x] Each user query: `{ id, name, config, created_at }` (id is integer)
  - [x] Apply per-user limit check (`SAVED_QUERY_LIMIT`) when returning count or for client use
- [x] POST `/sports-schedules/api/saved-queries`
  - [x] `@login_required` or equivalent check; return 401 if not authenticated
  - [x] Accept JSON body: `{ name: string, config: object }`
  - [x] Validate: name non-empty, len ≤ 100; config required; config JSON ≤ 2KB
  - [x] Check user's saved query count; return 400 if at limit
  - [x] Create `SportsScheduleSavedQuery(user_id=current_user.id, name=..., config=json.dumps(config))`
  - [x] Return `{ id, name, config, created_at }` with 201
- [x] DELETE `/sports-schedules/api/saved-queries/<int:id>`
  - [x] `@login_required`; 401 if not authenticated
  - [x] Fetch by id; 404 if not found
  - [x] Verify `query.user_id == current_user.id`; 403 if not
  - [x] Delete and return 204

**Manual Testing Phase 3:**
- [x] GET returns samples for anonymous user; samples + user_queries for logged-in
- [x] POST creates saved query; 401 when anonymous
- [x] POST returns 400 when at limit
- [x] DELETE removes only own queries; 403 for others

---

### Phase 4: UI — Saved Queries Section & Save Button

- [x] Add collapsible "Saved Queries" section above filter bar (in `ss-main`)
  - [x] Structure similar to `ss-section` / `ss-filter-bar`: header with toggle, content area
  - [x] Use `ss-` prefixed classes (e.g. `ss-saved-queries`, `ss-saved-queries-header`, `ss-saved-queries-list`)
  - [x] Default: collapsed when only samples; expanded when user has saved queries
- [x] Render sample queries as clickable items
  - [x] Each sample: button or link with name and "Sample" badge
  - [x] Click handler: load config into form (via `ssLoadQueryAndRun` → `ssApplyParamsFromUrl`), update URL, call `ssRunQuery()`
- [x] Render user saved queries (when logged in)
  - [x] Same click behavior as samples
  - [x] Each item: name + delete button (trash icon or "×")
  - [x] Delete: call DELETE API, remove from DOM, show "Removed" toast if desired
- [x] Add Save button
  - [x] Placement: in `ss-results-actions` alongside Copy, Copy URL, Download CSV
  - [x] Visible only after a query has been run; enabled when query is runnable (≥1 dimension or count)
  - [x] Click handler: if not logged in → redirect to login URL with `next` = current full URL + `&prompt_save=1`
  - [x] If logged in → open Save modal
- [x] Save modal
  - [x] Overlay + modal with input for query name, Cancel and Save buttons
  - [x] Save: collect current params via `ssCollectParams`; convert to config dict; POST to API with name + config
  - [x] On success: close modal, refresh list or append to DOM, show "Saved as 'X'" toast
  - [x] On error: show message in modal (limit reached, network error, validation error)
- [x] Handle `prompt_save=1` on page load
  - [x] After `ssApplyParamsFromUrl` runs, if `prompt_save=1` in URL and user is logged in, open Save modal; use `history.replaceState()` to strip `prompt_save` from URL
  - [x] Template passes auth state (e.g. `data-is-authenticated`) so JS can check

**Manual Testing Phase 4:**
- [x] Anonymous: sees samples; click loads and runs
- [x] Anonymous: run query, then click Save → redirects to login with correct `next` URL
- [x] Logged in: after login with `next` containing query params + `prompt_save=1` → lands on page, form populated, Save modal opens
- [x] Logged in: Save modal works; new query appears in list
- [x] Delete removes query from list

---

### Phase 5: JavaScript Integration & Polish

- [x] Fetch saved queries on load
  - [x] Call GET `/sports-schedules/api/saved-queries` on page init
  - [x] Show loading state until fetch completes, then populate `ss-saved-queries-list` with samples + user_queries
  - [x] Wire click handlers for load+run and delete
- [x] Implement `ssLoadQueryAndRun(config)` (or equivalent)
  - [x] Accept config object; convert to URLSearchParams (see Config ↔ URL mapping)
  - [x] Update URL via `history.replaceState` or `ssUpdateUrlFromParams` so `ssApplyParamsFromUrl` can read it
  - [x] Call `ssApplyParamsFromUrl()` to populate form from URL
  - [x] Call `ssRunQuery()`
- [x] Ensure config format matches API
  - [x] `ssCollectParams` returns structure compatible with `_parse_query_params` / `build_sql`
  - [x] When saving, serialize filters correctly (e.g. `league: ["NBA"]` not `league: "NBA"`)
- [x] UX polish
  - [ ] Loading indicator when clicking saved query (optional)
  - [ ] Toast for save success / delete (optional)
  - [ ] Truncate long names with ellipsis (optional)
  - [x] Empty state message when no user queries: "Save your current query to quickly access it later" (optional)

**Manual Testing Phase 5:**
- [x] Full flow: run query → Save → see in list → click → loads and runs
- [x] Full flow: anonymous Save → login → return → modal opens → save
- [x] Delete works; list updates
- [x] Sample queries work for all users

---

### Relevant Files (Saved Queries)

- `app/projects/sports_schedules/models.py` — Add `SportsScheduleSavedQuery`
- `app/projects/sports_schedules/core/sample_queries.py` — Sample configs
- `app/projects/sports_schedules/routes.py` — API routes; index route renders template (Flask-Login provides `current_user` for `{% if current_user.is_authenticated %}`)
- `app/projects/sports_schedules/templates/sports_schedules/index.html` — Saved queries section, Save button, Save modal
- `app/projects/sports_schedules/static/css/sports_schedules.css` — Styles for saved queries, modal
