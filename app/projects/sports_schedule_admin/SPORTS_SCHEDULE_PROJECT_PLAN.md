# Sports Schedule Admin - Project Plan

## Project Overview

This project is the **administrative engine** for the Sports Schedule system. Its purpose is to:
1.  **Collect & Sync Data**: Fetch professional sports schedules from the ESPN API.
2.  **Manage DoltHub**: Serve as the write-layer for the `combined-schedule` table in DoltHub.
3.  **Monitor**: Offer an admin-only dashboard to track sync health and data coverage.
4.  **Action**: Provide a UI to trigger syncs or clear data manually.

**Note:** This project handles *data acquisition and storage*. User-facing features (browsing, searching, NL query) will be built in a separate, public-facing project.

---

## 1. Data Population Strategy (Immediate Goals)

We need to populate upcoming/active schedules into DoltHub:

| League | Season | Status |
| :--- | :--- | :--- |
| **NBA** | 2025-26 | [x] Completed (Manual CLI) |
| **NHL** | 2025-26 | [x] Completed (Manual CLI) |
| **MLB** | 2026 | [x] Completed (Manual CLI) |
| **MLS** | 2026 | [ ] Pending (Use Admin UI) |
| **Soccer** | 2025-26 | [ ] Pending (Use Admin UI) |

---

## 2. Architecture & Responsibilities

### In Scope for THIS Project (Admin)
- [x] **DoltHub Write-Layer**: SQL API client for pushing data to `combined-schedule`.
- [x] **ESPN Data Scrapers**: Specialized logic for mapping ESPN JSON to your schema.
- [x] **Sync Engine**: Logic to handle `INSERT INTO ... ON DUPLICATE KEY UPDATE` to avoid duplicates.
- [x] **Normalization**: All data converted to **Eastern Time (ET)**.
- [x] **Admin Dashboard**: Web interface for manual control and visibility.
- [x] **Activity Logging**: Integrate with the app's `LogEntry` system for audit trails.

### OUT of Scope (User-Facing Project)
- **Public Search Interface**: Browsing games by team, date, or city.
- **Natural Language Query**: The AI interface for asking "When do the Red Sox play?"
- **API Endpoints**: JSON endpoints for mobile/frontend consumption.

---

## 3. Implementation Plan (Admin Project)

### Phase 1: Core Connectivity & CLI [x]
**Goal:** Establish the bridge between ESPN and DoltHub.

1.  [x] **DoltHub Client**: SQL API wrapper with polling support for write operations.
2.  [x] **ESPN Client**: Parser for 15+ leagues with ET normalization and slugified PKs.
3.  [x] **CLI Commands**: `sync` and `clear-league` commands registered in Flask.

### Phase 2: Admin Dashboard & Coverage [x]
**Goal:** Build the "Command Center" to see what's in DoltHub.

1.  [x] **DoltHub Health Check**: Visual indicator of API connectivity.
2.  [x] **Coverage Table (Auto-loading)**: 
    *   Dynamic summary fetched from DoltHub: `SELECT league, MIN(date), MAX(date), COUNT(*) FROM combined-schedule GROUP BY league`.
    *   Shows exactly which leagues are synced and their date ranges.
3.  [x] **Data Preview (Auto-loading)**: Show the most recent 10-20 games inserted into DoltHub across all leagues.
4.  [x] **Snappy Performance**: Use **Lazy Loading** (fetch DoltHub data via background AJAX calls) to ensure the initial dashboard page loads instantly without waiting for the remote API.

### Phase 3: Web-Based Actions [x]
**Goal:** Move the CLI power into the browser.

1.  [x] **Manual Sync Form**: 
    *   Dropdown for League selection.
    *   Start date picker + number of days (max 30).
    *   Live command preview.
    *   "Run Sync" button that triggers the process via AJAX.
2.  [x] **Clear League Tool**: 
    *   League dropdown + optional start date.
    *   "Type league code to confirm" input to enable the Clear Data button.
3.  [ ] **Sync Console**: A live log area on the page showing progress (e.g., "Processing 2026-04-01... Done").
4.  [x] **Activity Log**: Display the most recent `LogEntry` records filtered for the "sports_admin" project.

### Phase 4: Expansion & Maintenance [future]
1.  [ ] **Automation**: Re-evaluate Heroku Scheduler for daily updates once UI is stable.
2.  [ ] **Tournament Support**: Add logic for brackets (March Madness, World Cup Knockouts).
3.  [ ] **Custom SQL Runner**: A read-only interface to run analytics queries against DoltHub.

---

## 4. Configuration (DoltHub)

**Table Name**: `` `combined-schedule` ``
**Env Vars**:
*   `DOLTHUB_API_TOKEN`
*   `DOLTHUB_OWNER`
*   `DOLTHUB_REPO`
*   `DOLTHUB_BRANCH`

---

## 5. Summary of UI Requirements

### Dashboard Tabs/Sections:
*   **Overview**: Coverage stats (Date ranges per league) and Connectivity status.
*   **Operations**: Sync Form and Clear League tool.
*   **Logs**: Audit trail of who ran what and when.
*   **Preview**: Recent raw data from the DB.
