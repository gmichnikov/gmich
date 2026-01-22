# Basketball Tracker PRD

## Overview
A mobile-first basketball game tracking app that allows users to log game events in real-time and view statistics for youth basketball games.

## Project Details
- **Project name:** `basketball_tracker`
- **Route prefix:** `/basketball-tracker`
- **CSS prefix:** `bbt-` (all classes must use this prefix)
- **Database tables:** Prefixed with `basketball_` to avoid collisions
- **Authentication:** Required (uses existing Flask app auth)
- **Data ownership:** Private to user who creates it
- **Primary platform:** Mobile (mobile-first design)

## Data Model

### BasketballTeam
- **Purpose:** User creates/manages their own teams for use across multiple games
- **Fields:**
  - `id` (primary key)
  - `user_id` (foreign key to User)
  - `name` (string, required)
  - `created_at` (timestamp)
- **Notes:** Teams are used to enable aggregation of stats across games

### BasketballGame
- **Purpose:** Represents a single game between two teams on a specific date
- **Fields:**
  - `id` (primary key)
  - `user_id` (foreign key to User)
  - `team1_id` (foreign key to BasketballTeam)
  - `team2_id` (foreign key to BasketballTeam)
  - `game_date` (date, required)
  - `current_period` (integer, default=1, values: 1-4 for quarters/halves, 5+ for OT)
  - `created_at` (timestamp)
- **Constraints:**
  - Once created (teams + date selected), teams and date cannot be changed
  - Can be deleted
  - Can be reopened for editing at any time

### BasketballEvent
- **Purpose:** Individual game events (shots, turnovers, rebounds)
- **Fields:**
  - `id` (primary key)
  - `game_id` (foreign key to BasketballGame)
  - `team_id` (foreign key to BasketballTeam)
  - `period` (integer, which period the event occurred in)
  - `event_category` (string: 'make', 'miss', 'turnover', 'rebound')
  - `event_subcategory` (string: shot type, turnover type, or rebound type, required)
  - `created_at` (timestamp)
- **Event Categories and Subcategories:**
  - **Make Shot** (category='make') → Layup, Close 2, Far 2, 3-Pointer, Free Throw
  - **Miss Shot** (category='miss') → Layup, Close 2, Far 2, 3-Pointer, Free Throw
  - **Turnover** (category='turnover') → Traveling, Steal, Other
  - **Rebound** (category='rebound') → Offensive (defensive can be added later)
- **Aggregation Logic:**
  - All makes/misses with subcategory in {Layup, Close 2, Far 2} = Field Goals (2-point attempts)
  - All makes/misses with subcategory "3-Pointer" = 3-Point attempts
  - All makes/misses with subcategory "Free Throw" = Free Throw attempts
  - All turnovers aggregate as turnovers regardless of subcategory
  - All rebounds with subcategory "Offensive" = Offensive rebounds
- **Behavior:**
  - Saved immediately after each submission
  - Support unlimited undo (delete most recent event)
  - Period selector does not auto-revert when undoing events - user manually controls period

## Pages & Navigation

### Internal Navigation
Each page in the basketball_tracker project should have internal navigation between:
- **Games** (home page)
- **Teams** (team management)

Each page should also allow navigation back to the site's main navigation.

### 1. Home Page - Games List (`/basketball-tracker/`)
- **Purpose:** View all games and create new games
- **Layout:**
  - Internal navigation: Games | Teams
  - "Create Game" section at top with form:
    - Team 1 dropdown (from user's teams)
    - Team 2 dropdown (from user's teams)
    - Date picker (defaults to today)
    - Submit button → creates game and navigates to game edit view
  - Compact list of user's games:
    - Display: Date, "Team1 vs Team2"
    - Click to open game
  - Mobile-optimized layout

### 2. Teams Page (`/basketball-tracker/teams`)
- **Purpose:** Manage teams
- **Layout:**
  - Internal navigation: Games | Teams
  - "Add Team" form with name input
  - List of user's teams with delete option
- **Delete Restriction:** Teams that are used in any games cannot be deleted (prevent foreign key errors and orphaned data). Show error message if user attempts to delete a team that has games.
- **Future consideration:** Add ability to delete teams with games (cascade delete or require manual game deletion first)

### 3. Game Page (`/basketball-tracker/game/<id>`)
Three view modes (toggled): **Edit**, **Stats**, **Log**

#### Edit View (Default)
- **Live Score Display:** Prominent display showing current score for both teams (e.g., "Team A: 45 - Team B: 38"). Score is calculated on the fly from make events, not stored in database. Updates automatically when events are added/undone.
  - Free Throw make = 1 point
  - Layup/Close 2/Far 2 make = 2 points
  - 3-Pointer make = 3 points
- **Team Switcher:** Toggle/segmented control at top to select which team (Team 1 or Team 2) the next event applies to. Must clearly show both team names.
- **Period Selector:** Small, always-visible selector showing current period (1, 2, 3, 4, OT). Can only move forward, not backward. User can change before submitting events.
- **Primary Action Buttons** (large, touch-friendly):
  - **Make Shot** → inline expansion shows: Layup | Close 2 | Far 2 | 3-Pointer | Free Throw → select one → saves
  - **Miss Shot** → inline expansion shows: Layup | Close 2 | Far 2 | 3-Pointer | Free Throw → select one → saves
  - **Turnover** → inline expansion shows: Traveling | Steal | Other → select one → saves
  - **Offensive Rebound** → saves immediately (no subcategory needed)
- **Undo Button:** Always visible (or visible when events exist). Clicking undo deletes the most recent event. Support unlimited undo levels.
- **Event Log** (on same page):
  - Most recent 10 events
  - Newest first (reverse chronological)
  - Display: Team name, event category/subcategory, period
  - Period format: "1st", "2nd", "3rd", "4th", "OT" (5th period = "OT")
- **Delete Game Option:** Hidden in settings menu or similar on game page (not on home page list)
- **Interaction Flow:**
  1. User selects team (via team switcher)
  2. User ensures correct period is selected
  3. User clicks primary button (Make Shot, Miss Shot, Turnover, or Offensive Rebound)
  4. If needed, secondary buttons appear inline (shot type or turnover type)
  5. Event is saved immediately
  6. **Auto-Switch Logic:** If the event was a **Made Shot** (2 or 3 pointer, but NOT a free throw) or a **Turnover**, the active team automatically switches to the other team.
  7. Event log updates
  8. If mistake, user clicks Undo to remove last event
  9. User can undo multiple times if needed

#### Stats View
- **Purpose:** Summary statistics for the current game
- **Display:**
  - For each team, show totals:
    - Made shots by type (Layup, Close 2, Far 2, 3-Pointer, Free Throw)
    - Missed shots by type
    - Field Goal % (2-pointers: Layup, Close 2, Far 2)
    - 3-Point %
    - Free Throw %
    - Total Points
    - Turnovers by type
    - Offensive Rebounds
- **Percentage Calculations:** Handle division by zero gracefully. If no attempts of a type, show "0/0" or "-" instead of percentage, don't crash.
- **Toggle:** Button to switch back to Edit or Log view

#### Log View
- **Purpose:** Full event log for the game
- **Display:**
  - All events (not just most recent 10)
  - Newest first (reverse chronological, same as Edit view event log)
  - Team name, event category/subcategory, period, timestamp
  - Period format: "1st", "2nd", "3rd", "4th", "OT"
- **Toggle:** Button to switch back to Edit or Stats view

## UI/UX Requirements

### Mobile-First Design
- All pages optimized for mobile screens
- Large, touch-friendly buttons (minimum 44px height)
- Minimal chrome/navigation
- Fast, responsive interactions
- Works well on phones held in portrait mode

### CSS Namespacing
- **All CSS classes must use `bbt-` prefix**
- Examples: `.bbt-button`, `.bbt-team-switcher`, `.bbt-event-log`
- This prevents collisions with other projects in the Flask app

### Inline Expansion for Secondary Actions
- Use vanilla JavaScript for inline expansions (no heavy frameworks)
- Smooth, simple transitions
- Clear visual feedback for selected team and period

### Period Management
- Cannot change period retroactively (can only move forward: 1→2→3→4→OT)
- However, user can undo events, change period, then re-enter events
- Period selector should be small but always visible
- Period selector does NOT automatically revert when undoing events - user has manual control
- Period display format: "1st", "2nd", "3rd", "4th", "OT" (for 5th period and beyond)

### Auto-Save
- Every event saves immediately to database
- No "Save" button needed
- Provide visual feedback when event is saved (subtle animation or confirmation)

## Future Enhancements (Not in V1)

### Team Stats Across Games
- Team detail page showing aggregated stats for a team across all games
- Shooting percentages, turnover rates, etc.

### Advanced Stats
- Player-level tracking
- Plus/minus
- Time tracking within games

### Defensive Rebounds
- Currently only tracking offensive rebounds
- Could add defensive rebounds later

### Multi-User Collaboration
- Currently single-user only
- Could allow multiple users to track same game simultaneously

### Quarters vs Halves Configuration
- Could add game settings to specify whether game has quarters (4) or halves (2)
- Currently just using generic "period" label

## Implementation Phases

### Phase 1: Core Structure & Teams
- Set up project structure
- Create database models
- Implement team management (create, list, delete teams)
- Basic navigation between Games and Teams pages

### Phase 2: Game Creation & List
- Create game form with team selection and date
- Display games list on home page
- Basic game page (no events yet)

### Phase 3: Event Tracking (Edit View)
- Team switcher
- Period selector
- Primary action buttons with inline expansion
- Save events to database
- Event log display (most recent 10)
- Undo functionality

### Phase 4: Stats & Log Views
- Stats summary view with calculations
- Full event log view
- Toggle between Edit/Stats/Log

### Phase 5: Polish & Mobile Optimization
- CSS refinement for mobile
- Touch-friendly interactions
- Visual feedback and animations
- Delete game functionality

## Technical Notes

### JavaScript Approach
- Use vanilla JavaScript (no React, Vue, etc.)
- Keep it simple and fast
- Inline expansions for secondary buttons
- AJAX for saving events (no page reload)

### Database Considerations
- Events are never updated, only created or deleted (via undo)
- Consider indexing on `game_id` and `team_id` for event queries
- Consider soft-delete for games if we want to preserve history
- Score is NOT stored in database - always calculated on the fly from make events
  - This ensures score stays in sync with events and simplifies undo logic

### Mobile Performance
- Minimize JavaScript bundle size
- Optimize for touch interactions
- Fast initial page load
- Consider offline support (future)
