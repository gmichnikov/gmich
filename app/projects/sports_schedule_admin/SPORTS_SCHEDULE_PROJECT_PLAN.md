# Sports Schedule Data Collection & Query System - Project Plan

## Project Overview

Build a comprehensive sports schedule data collection and query system that:
1. Collects schedules from multiple sports leagues (pro and college) via ESPN API.
2. Stores data in **DoltHub** (versioned database) using the DoltHub SQL API.
3. Provides an admin UI within the main web app for browsing schedules.
4. Offers a natural language query interface (Text-to-SQL for DoltHub).
5. Uses **Heroku Scheduler** to run automated updates via Flask CLI commands.

**Key Philosophy:** Use APIs (ESPN) for reliability. Store in DoltHub for versioning and historical tracking. Integrate seamlessly into the existing Flask Hub as an Admin-only project.

---

## Architecture Overview (Integrated)

The project lives within the existing Flask application as a blueprint.

```
app/projects/sports_schedule_admin/
├── core/                       # Core logic (Data collection & DoltHub)
│   ├── __init__.py
│   ├── dolthub_client.py       # DoltHub SQL API wrapper
│   ├── espn_client.py          # ESPN API client
│   ├── models.py               # Pydantic models for data validation
│   └── logic.py                # Business logic for sync and queries
├── templates/                  # Blueprint-specific templates
│   └── sports_schedule_admin/
│       ├── index.html          # Admin dashboard
│       ├── search.html         # Interactive search
│       └── nl_query.html       # Natural language interface
├── static/                     # Blueprint-specific assets
│   ├── css/
│   │   └── sports_admin.css
│   └── js/
│       └── sports_admin.js
├── routes.py                   # Blueprint routes (Admin only)
├── commands.py                 # Flask CLI commands for Heroku Scheduler
└── README.md
```

---

## Data Model (DoltHub)

The schema exists in DoltHub. The Python app interacts with it via SQL queries.

### Core Schema (Existing DoltHub)

The system will use your existing table schema:

```sql
CREATE TABLE games (
    primary_key VARCHAR(16383) NOT NULL PRIMARY KEY,
    sport VARCHAR(16383),
    level VARCHAR(16383),
    league VARCHAR(16383),
    date DATE,
    day VARCHAR(16383),
    time VARCHAR(16383),
    home_team VARCHAR(16383),
    road_team VARCHAR(16383),
    location VARCHAR(16383),
    home_city VARCHAR(16383),
    home_state VARCHAR(16383)
);
```

**Primary Key Strategy:** Since the `primary_key` is a required string, we will generate it by concatenating `league`, `date`, `home_team`, and `road_team` (slugified) to ensure uniqueness and prevent duplicates during sync.

---

## Implementation Plan

### Phase 1: DoltHub & ESPN Integration (Week 1)

**Goal:** Establish connectivity to DoltHub and fetch major league schedules.

#### Step 1.1: DoltHub Client Setup
Create `app/projects/sports_schedule_admin/core/dolthub_client.py`:
- Implement authentication using `DOLTHUB_API_TOKEN`.
- Create methods for executing SQL queries via POST to `https://www.dolthub.com/api/v1alpha1/{owner}/{repo}/{branch}`.
- Handle rate limiting and error response parsing.

#### Step 1.2: ESPN API Client
Create `app/projects/sports_schedule_admin/core/espn_client.py`:
- Fetch data from `site.api.espn.com`.
- Implement `parse_event` to map ESPN JSON to Pydantic models.
- Support major leagues: MLB, NBA, NFL, NHL, MLS.

#### Step 1.3: Data Synchronization Logic
Create `app/projects/sports_schedule_admin/core/logic.py`:
- Function `sync_league(league_code, days_ahead)`:
    1. Fetch from ESPN.
    2. Convert to SQL `INSERT ... ON DUPLICATE KEY UPDATE` statements.
    3. Push to DoltHub.
    4. Log the result in DoltHub's `data_collection_log`.

#### Step 1.4: Flask CLI Commands
Create `app/projects/sports_schedule_admin/commands.py`:
- `@app.cli.command("sports-sync-daily")`: Runs sync for all major leagues (7 days ahead).
- `@app.cli.command("sports-sync-deep")`: Runs deep sync (30 days ahead) for specific leagues.
- Register in `app/__init__.py`.

---

### Phase 2: Admin Interface (Week 2)

**Goal:** Build the UI for managing and viewing schedules.

#### Step 2.1: Admin Dashboard
Update `app/projects/sports_schedule_admin/templates/sports_schedule_admin/index.html`:
- Show sync status summary (from `data_collection_log`).
- Buttons to manually trigger sync (via AJAX to internal API).
- Links to search and query interfaces.

#### Step 2.2: Schedule Search
Create `search.html`:
- Interactive filters (League, Team, Date, Location).
- Results grid showing data fetched from DoltHub.

#### Step 2.3: Blueprint Routes
Update `app/projects/sports_schedule_admin/routes.py`:
- Ensure all routes are protected by `@admin_required`.
- Implement data fetching routes that proxy to DoltHub.

---

### Phase 3: Natural Language Query (Week 3)

**Goal:** Use AI to query DoltHub in plain English.

#### Step 3.1: Text-to-SQL for DoltHub
- Use the existing `anthropic` client (already in `requirements.txt`).
- Prompt Engineering: Provide DoltHub schema and rules for PostgreSQL/MySQL syntax compatibility.
- Execute the generated SQL directly on DoltHub.

#### Step 3.2: Query UI
Create `nl_query.html`:
- Simple text area for questions.
- Result table with "Show SQL" toggle for transparency.

---

### Phase 4: Automation & Deployment (Week 4)

**Goal:** Configure Heroku Scheduler and monitor.

#### Step 4.1: Heroku Scheduler Integration
- Add `flask sports-sync-daily` to Heroku Scheduler (daily at 6 AM).
- Add `flask sports-sync-hourly` (optional) for game status updates.

#### Step 4.2: Monitoring & Logging
- Ensure collection logs are visible in the Admin Dashboard.
- Set up email alerts for sync failures (using the app's existing `email_service`).

---

## Configuration

### Environment Variables (.env)
```bash
DOLTHUB_API_TOKEN=your_token_here
DOLTHUB_OWNER=your_username
DOLTHUB_REPO=your_repo_name
DOLTHUB_BRANCH=main
ANTHROPIC_API_KEY=your_key_here
```

### Dependencies (Main requirements.txt already has most)
- `requests` (for DoltHub/ESPN APIs)
- `pydantic` (for data validation)
- `anthropic` (for NL query)

---

## Success Metrics
1. ✅ **Zero-maintenance updates**: Heroku Scheduler keeps DoltHub current.
2. ✅ **Historical Integrity**: All changes are versioned in DoltHub.
3. ✅ **Admin Control**: Clear visibility into sync health within the hub.
4. ✅ **Flexible Access**: Search by team/city or ask natural language questions.

---

## Questions & Clarifications Needed

1. **DoltHub Repo**: Should I create a new repository or use an existing one? If existing, please provide the name.
2. **Rate Limits**: DoltHub API has limits. For high-volume NCAA data, we might need to batch or stagger requests.
3. **Historical Data**: Do we need to migrate the existing DoltHub data to a new schema, or should I adapt the code to your existing schema?
