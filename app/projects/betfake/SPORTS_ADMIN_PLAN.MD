# Plan: Dynamic Sport Management & Admin Controls

## Goal
Transform the Betfake project from a hardcoded 3-sport system into a dynamic, data-driven system. This will allow for easy addition of new sports (like NHL or MLB) and granular control over API usage by toggling syncs for specific sports.

---

## 1. Database Model: `BetfakeSport`
We will create a new table to serve as the master registry for all sports supported by the app.

### Fields:
- `id` (Primary Key)
- `sport_key` (String, Unique): e.g., `basketball_nba`, `basketball_nba_championship_winner`.
- `sport_title` (String): e.g., "NBA", "NBA Championship Winner".
- `has_spreads` (Boolean): If true, the UI and sync will look for Spreads/Totals.
- `sync_scores` (Boolean): If true, `sync-scores` command will fetch results for this sport.
- `sync_odds` (Boolean): If true, `sync-odds` command will fetch upcoming games and lines.
- `show_in_nav` (Boolean): If true, the sport appears in the Dashboard and navigation tabs.

### Note on Futures:
Futures are treated as **separate sports rows** in the database (matching the Odds API structure). This allows independent control over syncing odds for a championship winner vs. scores for the actual season games.

---

## 2. Refactoring Logic (The "Sport-Agnostic" Shift)

### A. Navigation & UI
- Remove hardcoded links for NBA, NFL, and Soccer from all templates.
- Update the `index` route to fetch all sports where `show_in_nav=True`.
- **Sorting**: Active sports (sync or nav = True) will be sorted to the top, then alphabetically.

### B. Sync Commands & Services
- Update `sync-scores` and `sync-odds` in `commands.py` to loop through sports defined in the database where the respective sync flag is `True`.
- This automatically handles API quota management: simply toggle a sport "OFF" to stop making calls for it.

---

## 3. Admin Management UI
A new section on the **BetFake Admin Sync** page:

### Features:
- **Registry Table**: List all sports in the DB with toggle switches for Scores, Odds, and Nav.
- **Clutter Management**:
    - **Live vs. Available Tabs**: Separate "Active" (enabled) sports from the hundreds of "Inactive" ones.
    - **Instant Search/Filter**: A search box to quickly find sports by title or key (e.g., "NHL").
- **"Refresh Sport List" Button**: 
    - Calls the Odds API `/sports` endpoint.
    - **New Sports**: Automatically adds them to the DB (all toggles set to `OFF`).
    - **Existing Sports**: Updates the `sport_title` if it has changed.
    - **Missing Sports**: If a sport is in the DB but NOT in the API response (e.g., off-season), it is **preserved** so settings aren't lost.
- **Manual Add**: Option to add a specific `sport_key` manually if needed.

---

## 4. Implementation Phases

### Phase 1: Database & Seeding
1. Define the `BetfakeSport` model in `models.py`.
2. **User Action**: Run `flask db migrate` and `upgrade`.
3. Create a seed script to add the initial 3 sports (NBA, NFL, Soccer) plus NBA Futures into the table with their current settings.

### Phase 2: Refactor Navigation
1. Create a context processor or update routes to provide the dynamic `active_sports` list to templates.
2. Update all navigation templates to loop through this list.

### Phase 3: Refactor Sync Logic
1. Update `DataImportService` and `commands.py` to query the `BetfakeSport` table instead of using hardcoded lists.
2. Update the `admin_sync_trigger` to respect these dynamic settings.

### Phase 4: Admin UI
1. Build the management table on the Admin page.
2. Implement the "Refresh Sport List" API integration.
3. Add the toggle submission logic.
