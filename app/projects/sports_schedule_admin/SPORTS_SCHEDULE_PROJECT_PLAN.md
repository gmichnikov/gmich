# Sports Schedule Admin - Project Plan

## Project Overview

This project is the **administrative engine** for the Sports Schedule system. Its purpose is to:
1.  **Collect & Sync Data**: Fetch professional sports schedules from the ESPN API.
2.  **Manage DoltHub**: Serve as the write-layer for the `combined-schedule` table in DoltHub.
3.  **Monitor**: Offer an admin-only dashboard to track sync health and data coverage.
4.  **Action**: Provide a UI to trigger syncs or clear data manually.

**Note:** This project handles *data acquisition and storage*. User-facing features (browsing, searching, NL query) live in `sports_schedules`.

**Need to backfill a new season?** See **[§1 Annual Season Sync Runbook](#1-annual-season-sync-runbook)** below.

---

## 1. Annual Season Sync Runbook

**Start here** when a new season's schedules are published and you need to backfill DoltHub. No code changes or DB migrations are required — just sync commands.

### Which sync mode?

```
Pro leagues (NBA, NHL, NFL, MLB, MLS…)     →  Date-range sync, split by month (~1 min/month)
College football (CFB)                     →  Scoreboard for TV games, then team sync for your schools
College basketball / hockey / soccer       →  Team sync only (scoreboard misses most games)
Your NJ/NYC schools (all sports)           →  See data/nj_nyc_college_school_ids.json + re-sync script below
```

| Sync type | CLI | Admin UI |
| :--- | :--- | :--- |
| Date range (day-by-day) | `flask sports-admin sync --league NBA --start … --end …` | Operations → Date Range |
| Single school | `flask sports-admin sync-team --league NCAAM --team-id 108` | Operations → By Team |
| All discovered schools | `flask sports-admin sync-bulk --league NCAAM` | Operations → Sync All |
| Your 32 NJ/NYC schools | Re-sync script in [§1.5](#15-njnyc-school-list-all-college-sports) | — |

**Timing:** Pro league month ≈ 1 minute. Full NBA/NHL season ≈ 9 minutes. NJ/NYC college re-sync ≈ 6 minutes. Running in background is fine — upserts are idempotent.

### Architecture reminder

- **`sports_schedule_admin`** (this project) writes to DoltHub via ESPN / MLB Stats API sync.
- **`sports_schedules`** (public UI at `/sports-schedules`) reads the same DoltHub `combined-schedule` table. Once data is synced, the public app picks it up automatically.

### Step 1: Check what's missing

**Admin UI:** `/sports-schedule-admin` → Overview → League Coverage (toggle Current season / All time).

**CLI:**
```bash
direnv exec . flask sports-admin check-coverage --league NBA --start 2026-10-01 --end 2027-06-30
```

**DoltHub SQL** (read-only, no auth for public repo):
```bash
curl -s "https://www.dolthub.com/api/v1alpha1/gmichnikov/sports-schedules/main?q=SELECT%20league%2C%20MIN(%60date%60)%2C%20MAX(%60date%60)%2C%20COUNT(*)%20FROM%20%60combined-schedule%60%20WHERE%20league%3D'NBA'%20GROUP%20BY%20league"
```

**Season date conventions:**
| Type | Leagues | Typical range |
| :--- | :--- | :--- |
| School year (Aug 1 – Jul 31) | NFL, NBA, NHL, WNBA, CFB, college, EPL/UEFA | e.g. NBA 2026-27 = Oct 2026 – Jun 2027 |
| Calendar year (Jan 1 – Dec 31) | MLB, MLS, NWSL, MiLB, World Cup | e.g. MLB 2027 = Mar – Nov 2027 |

### Step 2: Sync pro leagues (NBA, NHL, NFL, MLS, etc.)

Use **date-range sync** — one ESPN scoreboard call per day, upserted to DoltHub.

**Split by month**, not one giant range. Each month takes ~1 minute (most days have no games; days with games add a short DoltHub write). A full Oct–Jun pro season ≈ **9 minutes total**.

```bash
# Example: NBA 2026-27 (repeat for each month Oct–Jun)
direnv exec . flask sports-admin sync --league NBA --start 2026-10-01 --end 2026-10-31
direnv exec . flask sports-admin sync --league NBA --start 2026-11-01 --end 2026-11-30
# ... through June
```

**Batch script pattern** (run in background, log to `/tmp/`):
```bash
months=(
  "2026-10-01 2026-10-31"
  "2026-11-01 2026-11-30"
  # ... add remaining months
)
for range in "${months[@]}"; do
  start=${range%% *}; end=${range##* }
  direnv exec . flask sports-admin sync --league NBA --start "$start" --end "$end"
done
direnv exec . flask sports-admin check-coverage --league NBA --start 2026-10-01 --end 2027-06-30
```

Same pattern for **NHL**. **NFL** school-year season is Sep – Jan/Feb. **MLB** and **MLS** use calendar-year ranges (Mar–Sep, Feb–Nov).

**Ongoing maintenance:** `flask sports-admin daily-sync` only covers the next 7 days for MLB/NBA/NFL/NHL/MLS/NWSL/EPL — it does **not** backfill future seasons. Run the monthly backfill above once per year when schedules drop.

### Step 3: College football (CFB)

Three options depending on how much coverage you need:

| Approach | When to use | Command | Coverage |
| :--- | :--- | :--- | :--- |
| **Scoreboard (recommended default)** | Major/TV games are enough; don't need every FCS game | `sync --league CFB --start YYYY-08-25 --end YYYY+1-01-15` | ~50–70 games on Saturdays, few midweek; ~4 min for full season |
| **Specific teams** | You follow a handful of schools and want their full schedules | `sync-teams --league CFB` then `sync-team --league CFB --team-id <ID>` per team | Complete schedule for those teams only |
| **Bulk all teams** | Need comprehensive D1 coverage | `sync-teams` then `sync-bulk --league CFB` | ~500 teams, slow; see COLLEGE_SPORTS_PLAN.md |

For most use cases, **scoreboard sync** is the right tradeoff — same day-by-day approach as pro leagues, one command for the whole season.

**Scoreboard gaps:** FCS and Ivy schools rarely appear on the daily scoreboard. After scoreboard sync, team-sync your schools (see [§1.5](#15-njnyc-school-list-all-college-sports) — CFB IDs match basketball/hockey, not soccer).

Repeat CFB team sync each year when schedules publish (~30 sec for 32 schools).

### Step 3b: College basketball, hockey, soccer (NCAAM, NCAAW, NCHM, NCHW, NCSM, NCSW)

**Use team sync only** — do not rely on day-by-day scoreboard for these sports (see COLLEGE_SPORTS_PLAN.md).

League codes: `NCAAM`, `NCAAW`, `NCHM`, `NCHW`, `NCSM`, `NCSW`

**ESPN team IDs differ per sport.** See **`data/nj_nyc_college_school_ids.json`** for 32 NJ/NYC-area schools × all sports.

### 1.5 NJ/NYC school list (all college sports)

**32 schools:** 22 with football + 10 without (Seton Hall, St. John's, Saint Peter's, Manhattan, Iona, Rider, Quinnipiac, Fairfield, NJIT, Fairleigh Dickinson).

**Data file:** `data/nj_nyc_college_school_ids.json` — one row per school, ESPN team ID per league (`null` = no program).

**Re-sync all schools** (~6 min, safe to run in background):

```bash
python3 - <<'PY'
import json, subprocess
rows = json.load(open("app/projects/sports_schedule_admin/data/nj_nyc_college_school_ids.json"))
for league in ["NCAAM","NCAAW","NCHM","NCHW","NCSM","NCSW"]:
    for row in rows:
        tid = row.get(league)
        if tid:
            subprocess.run(
                f"direnv exec . flask sports-admin sync-team --league {league} --team-id {tid}",
                shell=True, check=False,
            )
PY
```

Also re-run CFB team IDs from the same JSON (`CFB` column) after the scoreboard sync each fall.

**When to re-run (annual checklist):**

| When | What |
| :--- | :--- |
| Aug/Sep | CFB scoreboard + CFB/NCSM/NCSW team re-sync from JSON |
| Oct/Nov | NCAAM team re-sync (ESPN often empty until ~6 weeks before season) |
| Oct | NCHM/NCHW team re-sync |
| Nov–Mar | NCAAW/NCAAM refresh optional mid-season |
| Oct–Jun | Pro leagues (NBA, NHL) monthly backfill |

**Aug 2026 sync results:**

| League | Teams | Games | Notes |
| :--- | ---: | ---: | :--- |
| NCAAW | 32 | 397 | Ready |
| NCHM | 11 | 325 | Only schools with men's hockey |
| NCHW | 8 | 250 | Subset |
| NCSM | 29 | 68 | Fall season; re-sync as schedules fill in |
| NCSW | 28 | 95 | Fall season; re-sync as schedules fill in |
| NCAAM | 32 | 0 | ESPN not published yet — re-run in Oct/Nov |

### Step 4: Verify

```bash
direnv exec . flask sports-admin check-coverage --league NBA --start 2026-10-01 --end 2027-06-30
direnv exec . flask sports-admin check-coverage --league NHL --start 2026-10-01 --end 2027-06-30
direnv exec . flask sports-admin check-coverage --league CFB --start 2026-08-25 --end 2027-01-15
```

Spot-check in `/sports-schedules` with league + date filters.

### Prerequisites

- DoltHub env vars set: `DOLTHUB_API_TOKEN`, `DOLTHUB_OWNER`, `DOLTHUB_REPO`, `DOLTHUB_BRANCH`
- Venv active (`direnv exec .` or `source venv/bin/activate`)

### Related docs

- **COLLEGE_SPORTS_PLAN.md** — team-based sync for NCAAM, NCB, etc. (not CFB scoreboard)
- **MILB_SYNC_NOTES.md** — MiLB chunked sync quirks

---

## 2. Sync History

*Operational log — update after each backfill.*

| League | Season | Status | Notes |
| :--- | :--- | :--- | :--- |
| **NBA** | 2025-26 | [x] Completed | Manual CLI |
| **NBA** | 2026-27 | [x] Completed | Monthly CLI sync, Aug 2026 |
| **NHL** | 2025-26 | [x] Completed | Manual CLI |
| **NHL** | 2026-27 | [x] Completed | Monthly CLI sync, Aug 2026 (1,023 games) |
| **NFL** | 2026 | [x] Completed | Already in DoltHub (278 games Sep 2026+) |
| **MLB** | 2026 | [x] Completed | Manual CLI |
| **MLS** | 2026 | [x] Completed | 510 games in DoltHub |
| **CFB** | 2026 | [x] Completed | Scoreboard + 32 NJ/NYC teams (842 games) |
| **NCAAW** | 2026-27 | [x] Completed | 32-school team sync, Aug 2026 |
| **NCHM / NCHW** | 2026-27 | [x] Partial | 32-school team sync; re-run Oct |
| **NCSM / NCSW** | 2026 | [x] Partial | 32-school team sync; re-run as fall fills in |
| **NCAAM** | 2026-27 | [ ] Pending | ESPN team API empty Aug 2026 — re-run Oct/Nov |
| **Soccer (pro)** | 2025-26 | [ ] Pending | EPL, CL, etc. |

---

## 3. Project Reference (historical)

*Implementation notes from building the admin project — not needed for routine syncs.*

### Architecture & Responsibilities

**In scope (admin):**
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

## 4. Implementation Plan (Admin Project)

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

### Phase 3.5: Data Quality – State Normalization [x]
1.  [x] **ESPN Client**: Normalize `home_state` to 2-letter US codes (California → CA) during sync.
2.  [x] **CLI Command**: `flask sports-admin normalize-states` to fix existing full-state-name rows in DoltHub.

### Phase 4: Expansion & Maintenance [future]
1.  [ ] **Automation**: Re-evaluate Heroku Scheduler for daily updates once UI is stable.
2.  [ ] **Tournament Support**: Add logic for brackets (March Madness, World Cup Knockouts).
3.  [ ] **Custom SQL Runner**: A read-only interface to run analytics queries against DoltHub.

---

## 5. MiLB Sync Notes

Minor league sync (AAA, AA, A+, A) uses the MLB Stats API. See **MILB_SYNC_NOTES.md** for known issues (API truncation on large date ranges, date handling) and troubleshooting.

---

## 6. Configuration (DoltHub)

**Table Name**: `` `combined-schedule` ``
**Env Vars**:
*   `DOLTHUB_API_TOKEN`
*   `DOLTHUB_OWNER`
*   `DOLTHUB_REPO`
*   `DOLTHUB_BRANCH`

---

## 7. Summary of UI Requirements

### Dashboard Tabs/Sections:
*   **Overview**: Coverage stats (Date ranges per league) and Connectivity status.
*   **Operations**: Sync Form and Clear League tool.
*   **Logs**: Audit trail of who ran what and when.
*   **Preview**: Recent raw data from the DB.
