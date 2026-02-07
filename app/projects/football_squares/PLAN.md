# Football Squares - Implementation Plan

This plan breaks down the development of the Football Squares project into testable phases. All CSS classes must use the `fs-` prefix.

---

## Phase 1: Database Models & Migrations
Create the core data structures for grids, participants, squares, and quarters.

- [x] 1.1 Create `models.py` in `app/projects/football_squares/`
    - [x] Define `FootballSquaresGrid` model
        - [x] Fields for `team1_digits` and `team2_digits` (JSON strings)
        - [x] `share_slug` for public access
    - [x] Define `FootballSquaresParticipant` model
        - [x] `square_count`: Target number of squares (Integer)
    - [x] Define `FootballSquaresSquare` model
        - [x] (x, y) coordinates and foreign key to participant
    - [x] Define `FootballSquaresQuarter` model
        - [x] Periods 1-4 (Q1-Q4) and Period 5 (OT)
- [x] 1.2 Register models in `app/__init__.py`

**Manual Testing 1:**
- [x] Run `flask db migrate -m "Add football_squares models"`
- [x] Verify migration file contains all 4 tables and correct fields.
- [x] Run `flask db upgrade`
- [x] Verify tables exist in the database (e.g., via `psql` or a DB explorer).

---

## Phase 2: Project Structure & Basic Management
Set up the blueprint, routes for the grid dashboard, and grid creation.

- [x] 2.1 Update `app/projects/football_squares/__init__.py` (already done, but verify).
- [x] 2.2 Implement basic routes in `routes.py`:
    - [x] `GET /` - List all grids for the current user.
    - [x] `GET /create` - Form to create a new grid.
    - [x] `POST /create` - Handle grid creation (generate `share_slug`).
    - [x] `GET /<grid_id>` - Dashboard for a specific grid.
    - [x] `GET /<grid_id>/edit` - Form to edit grid name/teams/colors.
    - [x] `POST /<grid_id>/delete` - Route to delete a grid.
- [x] 2.3 Create templates:
    - [x] `football_squares/list.html` - Show all grids with "Delete" buttons.
    - [x] `football_squares/create_edit.html` - Unified form for new/edit grid.
    - [x] `football_squares/dashboard.html` - Main control center for a specific grid.

**Manual Testing 2:**
- [x] Navigate to `/football-squares/`.
- [x] Create a new grid and verify it redirects to the grid dashboard.
- [x] Verify the grid appears in the list view.

---

## Phase 3: Participant & Configuration UI
Add participants, set allocations, and configure the axis.

- [x] 3.1 Participant management:
    - [x] Add/Delete participants on the grid dashboard.
    - [x] Form to set/update `square_count` for each participant.
    - [x] **Square Counter**: Real-time display of "Total Squares Assigned (X/100)".
    - [x] Implement "Lock" logic: Disable adding/removing participants once a square is assigned.
- [x] 3.2 Axis configuration:
    - [x] Toggle between "Draft Order" (0-9) and "Random" (shuffled).
    - [x] Initialize digits on grid creation based on this setting.
    - [x] Add "Re-shuffle Digits" button (only for Random mode).

**Manual Testing 3:**
- [x] Add 3 participants with different square allocations (e.g., 20, 30, 50).
- [x] Toggle the axis to "Random" and verify digits are shuffled in the DB.
- [x] Verify you can't add/remove participants after a square is manually assigned.

---

## Phase 4: The 10x10 Grid & Filling Logic
Build the interactive grid and randomization algorithms.

- [x] 4.1 Grid Visualization:
    - [x] Render a 10x10 HTML table with axis labels.
    - [x] Highlight squares that are already assigned.
- [x] 4.2 Filling Logic:
    - [x] Manual assignment: Click a square, select a participant from a dropdown.
    - [x] AJAX/Fetch endpoint to update `FootballSquaresSquare` in real-time.
    - [x] "Randomize All": Clear all squares and distribute based on participant `square_count`.
    - [x] "Fill Remaining Randomly": Only fill empty squares using remaining `square_count` balances.
    - [x] Validation: Ensure total assigned squares does not exceed 100.

**Manual Testing 4:**
- [x] Manually assign 5 squares.
- [x] Click "Fill Remaining Randomly" and verify all 100 squares are filled.
- [x] Verify the final count of squares matches the participant's `square_count`.

---

## Phase 5: Scoring, Winners & Public Sharing
Enter scores, calculate winners, and provide the shareable link.

- [x] 5.1 Scoring UI:
    - [x] Form to enter scores for Q1, Q2, Q3, Q4, and OT.
    - [x] Fields for "Payout Description" (points/prizes) for each period.
- [x] 5.2 Winner Calculation & Summary:
    - [x] Logic to find the winning square based on the last digits of the scores.
    - [x] **Winner Summary Table**: Show each participant and the total points/prizes they won across all periods.
    - [x] Display the winner's name prominently on the grid for each completed period.
- [x] 5.3 Public View:
    - [x] Implement `GET /view/<share_slug>` route (No login required).
    - [x] Create `football_squares/public_view.html` (Read-only version of the grid).

**Manual Testing 5:**
- [x] Enter a score of 17-14 for Q1.
- [x] Verify the square at (7, 4) is highlighted as the winner.
- [x] Open the public view URL in an Incognito window and verify the grid is visible but not editable.

---

## Phase 6: Styling & Polish
Apply team colors and ensure responsive design.

- [x] 6.1 Dynamic Styling:
    - [x] Inject team colors into the CSS for the grid axes and headers.
    - [x] Ensure the `fs-` prefix is used for all custom styles in `static/football_squares/style.css`.
- [x] 6.2 Responsive Design:
    - [x] Optimize the grid for mobile (may require horizontal scrolling or smaller cells).
    - [x] Clean up forms and navigation.

**Manual Testing 6:**
- [x] Change a team's primary color to Green and verify the axis label changes color.
- [x] View the grid on a mobile device/emulator and verify it's usable.
- [x] Run a final sweep for any missing `fs-` prefixes.
