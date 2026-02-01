# Plan: Dynamic Sport Management & Admin Controls

## Goal
Transform the Betfake project from a hardcoded 3-sport system into a dynamic, data-driven system. This will allow for easy addition of new sports (like NHL or MLB) and granular control over API usage by toggling syncs for specific sports.

---

## 1. Database Model: `BetfakeSport`
We will create a new table to serve as the master registry for all sports supported by the app.

### Fields:
- `id` (Primary Key)
- `sport_key` (String, Unique): e.g., `basketball_nba`, `basketball_nba_championship_winner`.
- `sport_title` (String): The display name (e.g., "NBA", "NFL"). **This replaces the hardcoded label logic.**
- `has_spreads` (Boolean): If true, the UI and sync will look for Spreads/Totals.
- `sync_scores` (Boolean): If true, `sync-scores` command will fetch results for this sport.
- `sync_odds` (Boolean): If true, `sync-odds` command will fetch upcoming games and lines.
- `show_in_nav` (Boolean): If true, the sport appears in the Dashboard and navigation tabs.

### Note on Collisions & Futures:
Futures (e.g., `basketball_nba_championship_winner`) are treated as **separate rows**. Because we use the unique `sport_key` from the API as our identifier, there is no risk of colliding a future with a regular game.

---

## 2. Refactoring Logic (The "Sport-Agnostic" Shift)

### A. Navigation & UI
- Remove hardcoded links for NBA, NFL, and Soccer from all templates.
- Update the `index` route to fetch all sports where `show_in_nav=True`.
- **Labels**: Instead of stripping "americanfootball_" from keys, we will simply display the `sport_title` stored in the database.
- **Dashboard**: Update the "Browse NBA Games" button on the dashboard to dynamically link to the first active sport.

### B. Sync Commands & Services
- Update `sync-scores` and `sync-odds` in `commands.py` to loop through sports defined in the database where the respective sync flag is `True`.
- Update `DataImportService` to use the `has_spreads` flag from the database instead of checking if the key is `soccer_epl`.

---

## 3. Admin Management UI
A new section on the **BetFake Admin Sync** page:

### Features:
- **Registry Table**: List all sports in the DB with toggle switches for Scores, Odds, and Nav.
- **Clutter Management**:
    - **Active vs. Available Tabs**: Separate sports with any toggle enabled from the hundreds of inactive ones.
    - **Instant Search/Filter**: A search box to quickly find sports by title or key (e.g., "NHL").
- **"Refresh Sport List" Button**: 
    - Calls the Odds API `/sports` endpoint.
    - **New Sports**: Automatically adds them to the DB (all toggles set to `OFF`).
    - **Existing Sports**: Updates the `sport_title` if it has changed.
- **Manual Add**: Option to add a specific `sport_key` manually if needed.

---

## 4. Implementation Phases (Re-ordered to avoid empty nav)

### Phase 1: Database & Model
1. Define the `BetfakeSport` model in `models.py`. (**Done**)
2. **User Action**: Run `flask db migrate` and `upgrade`.

### Phase 2: Admin UI (The Control Panel)
1. Build the management table on the Admin page.
2. Implement the "Refresh Sport List" API integration.
3. Add the toggle submission logic.
4. **User Action**: Refresh the list and turn "ON" NBA, NFL, and Soccer so they exist in the DB.

### Phase 3: Refactor Navigation
1. Create a context processor or update routes to provide the dynamic `active_sports` list to templates.
2. Update all navigation templates to loop through this list.
3. Update the Dashboard "Browse" button.

### Phase 4: Refactor Sync Logic
1. Update `DataImportService` and `commands.py` to query the `BetfakeSport` table.
2. Update the `admin_sync_trigger` to respect these dynamic settings.
