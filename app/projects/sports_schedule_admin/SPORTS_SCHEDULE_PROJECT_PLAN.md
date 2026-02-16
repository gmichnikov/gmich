# Sports Schedule Admin - Project Plan

## Project Overview

This project is the **administrative engine** for the Sports Schedule system. Its purpose is to:
1.  **Collect & Sync Data**: Fetch professional sports schedules from the ESPN API.
2.  **Manage DoltHub**: Serve as the write-layer for the `combined-schedule` table in DoltHub.
3.  **Automate**: Provide CLI commands for Heroku Scheduler to keep data fresh.
4.  **Monitor**: Offer an admin-only dashboard to track sync health and data coverage.

**Note:** This project handles *data acquisition and storage*. User-facing features (browsing, searching, NL query) will be built in a separate, public-facing project.

---

## 1. Data Population Strategy (Immediate Goals)

We need to populate the following upcoming/active schedules into DoltHub:

| League | Season | Strategy |
| :--- | :--- | :--- |
| **MLB** | 2026 | Deep sync (March - October 2026) via ESPN API |
| **MLS** | 2026 | Deep sync (February - December 2026) via ESPN API |
| **Premier League** | 2025-26 | Remainder of season (Now - May 2026) via ESPN API |
| **NBA / NHL** | 2025-26 | Maintenance sync (Ongoing updates/status changes) |

---

## 2. Architecture & Responsibilities

### In Scope for THIS Project (Admin)
- **DoltHub Write-Layer**: SQL API client for pushing data to `combined-schedule`.
- **ESPN Data Scrapers**: Specialized logic for mapping ESPN JSON to your schema.
- **Sync Engine**: Logic to handle `INSERT INTO ... ON DUPLICATE KEY UPDATE` to avoid duplicates.
- **Flask CLI Commands**: Automated triggers for daily and deep syncs.
- **Admin UI**: Web interface to manually trigger syncs for specific leagues/dates and monitor progress.

### OUT of Scope (User-Facing Project)
- **Public Search Interface**: Browsing games by team, date, or city.
- **Natural Language Query**: The AI interface for asking "When do the Red Sox play?"
- **API Endpoints**: JSON endpoints for mobile/frontend consumption.

---

## 3. Implementation Plan (Admin Project)

### Phase 1: Core Connectivity & CLI (Week 1)
**Goal:** Establish the bridge between ESPN and DoltHub.

1.  **DoltHub Client (`core/dolthub_client.py`)**:
    *   Uses `DOLTHUB_API_TOKEN`, `OWNER`, `REPO`, `BRANCH`.
    *   Executes raw SQL POST requests to DoltHub SQL API.
2.  **ESPN Client (`core/espn_client.py`)**:
    *   Maps ESPN events to your schema: `primary_key`, `road_team`, `home_city`, etc.
    *   **Primary Key Strategy**: Clean, slugified format: `{league}_{date}_{home_slug}_vs_{road_slug}` (e.g., `nba_2026-02-15_lakers_vs_warriors`).
3.  **Sync Logic (`core/logic.py`)**:
    *   `sync_league_range(league, start_date, end_date)`: The engine for both daily and deep syncs.

### Phase 2: Historical & Deep Population (Week 2)
**Goal:** Populate the missing 2026 schedules via CLI.

1.  **CLI Command: `deep-sync`**:
    *   Usage: `flask sports-admin deep-sync --league MLB --start 2026-03-01 --end 2026-10-31`.
    *   Task: Run this for MLB 2026, MLS 2026, and the remainder of the Premier League.
2.  **Validation**:
    *   Compare DoltHub counts against official league calendars to ensure coverage.

### Phase 3: Admin UI & Manual Sync (Week 3)
**Goal:** Provide a web interface for administrators to trigger and monitor syncs.

1.  **Manual Sync Interface**:
    *   A form on the Admin Dashboard with:
        *   **League Selection**: Dropdown (MLB, NBA, NFL, NHL, MLS, EPL).
        *   **Date Range**: Start and End date pickers.
        *   **Sync Button**: Triggers the sync process.
2.  **Sync Progress & Feedback**:
    *   Visual feedback showing sync status and number of games processed.
3.  **Sync Health Dashboard**:
    *   Summary of recent sync logs (Status, Games Found, Duration, Errors).
    *   "Coverage at a Glance": Total game counts per league for the current/upcoming season.

### Phase 4: Automation & Deployment (Week 4)
**Goal:** Configure Heroku Scheduler and finalize.

1.  **CLI Command: `daily-sync`**:
    *   Syncs all enabled leagues for the next 7 days.
    *   To be added to **Heroku Scheduler**.
2.  **Maintenance**:
    *   Ensure error logging and notifications are working for scheduled jobs.

---

## 4. Configuration (DoltHub)

**Table Name**: `` `combined-schedule` ``
**Schema**: Matches your existing columns (`primary_key`, `road_team`, etc.).
**Env Vars**:
*   `DOLTHUB_API_TOKEN`
*   `DOLTHUB_OWNER`
*   `DOLTHUB_REPO`
*   `DOLTHUB_BRANCH`

---

## 5. Next Steps

1.  **Initialize core modules**: Create the directory structure and empty `__init__.py` files.
2.  **Build DoltHub Client**: Implement the SQL API wrapper.
3.  **Build ESPN Client**: Implement parsing and PK generation logic.
4.  **Test one league**: Perform a test sync for a single date to verify the end-to-end flow.
