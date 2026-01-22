# Basketball Tracker - Implementation Plan

This document outlines the detailed implementation plan for the Basketball Tracker project, broken down into phases with specific tasks.

---

## [x] Phase 1: Core Structure & Teams Management

### [x] 1.1 Database Migration
- [x] Run `flask db migrate -m "Add basketball tracker models"`
- [x] Review generated migration file
- [x] Run `flask db upgrade`
- [x] Verify tables created: `basketball_team`, `basketball_game`, `basketball_event`

### [x] 1.2 Base CSS Setup
- [x] Create base mobile-first CSS structure in `static/basketball_tracker/style.css`
- [x] Define CSS variables for colors, spacing, button sizes
- [x] Create `.bbt-container` base styles
- [x] Create `.bbt-button` base styles (minimum 44px height for touch)
- [x] Create `.bbt-nav` styles for internal navigation

### [x] 1.3 Internal Navigation Component
- [x] Create navigation partial/macro for "Games | Teams" navigation
- [x] Style navigation for mobile (prominent, easy to tap)
- [x] Ensure navigation appears on all three pages (index, teams, game)

### [x] 1.4 Teams Page - Backend
- [x] Create POST route `/teams/create` to add new team
  - [x] Validate team name is not empty
  - [x] Associate team with current_user
  - [x] Save to database
  - [x] Flash success message
  - [x] Redirect back to teams page
- [x] Create POST route `/teams/<int:team_id>/delete` to delete team
  - [x] Verify team belongs to current_user
  - [x] Check if team is used in any games (team1_id or team2_id in BasketballGame)
  - [x] If team has games: flash error message "Cannot delete team with existing games" and redirect
  - [x] If team has no games: delete team from database, flash success message, redirect
- [x] Update GET route `/teams` to fetch and pass user's teams to template

### [x] 1.5 Teams Page - Frontend
- [x] Update `templates/basketball_tracker/teams.html`
- [x] Add internal navigation (Games | Teams)
- [x] Create "Add Team" form
  - [x] Text input for team name (with proper label)
  - [x] Submit button
  - [x] Form styling for mobile
- [x] Display list of user's teams
  - [x] Show team name
  - [x] Add delete button for each team
  - [x] Style as mobile-friendly list
- [x] Add confirmation dialog for delete (JavaScript)
- [x] Test: Create team, view team, delete team

---

## [x] Phase 2: Game Creation & List

### [x] 2.1 Home Page - Backend
- [x] Create POST route `/games/create` to create new game
  - [x] Validate both teams are selected
  - [x] Validate date is provided
  - [x] Verify both teams belong to current_user
  - [x] Create game with team1_id, team2_id, game_date, current_period=1
  - [x] Associate with current_user
  - [x] Save to database
  - [x] Redirect to game page (edit view)
- [x] Update GET route `/` to fetch and pass:
  - [x] User's teams (for dropdown)
  - [x] User's games (ordered by date desc, then created_at desc)

### [x] 2.2 Home Page - Frontend
- [x] Update `templates/basketball_tracker/index.html`
- [x] Add internal navigation (Games | Teams)
- [x] Create "Create Game" form section
  - [x] Team 1 dropdown (populated from user's teams)
  - [x] Team 2 dropdown (populated from user's teams)
  - [x] Date picker input (default to today's date)
  - [x] Submit button
  - [x] Style for mobile (large touch targets)
- [x] Display games list
  - [x] Show date (formatted nicely)
  - [x] Show "Team1 vs Team2" format
  - [x] Make entire game item clickable (link to game page)
  - [x] Style as compact mobile list
- [x] Handle empty states
  - [x] Show message if no teams exist (link to teams page)
  - [x] Show message if no games exist
- [x] Test: Create game with two teams and date, verify redirect to game page

### [x] 2.3 Game Page - Basic Structure
- [x] Update GET route `/game/<int:game_id>`
  - [x] Fetch game by ID
  - [x] Verify game belongs to current_user (404 if not)
  - [x] Fetch team1 and team2 objects
  - [x] Pass game and team data to template
- [x] Update `templates/basketball_tracker/game.html`
  - [x] Add internal navigation (back to Games, link to Teams)
  - [x] Display game header: "Team1 vs Team2" and date
  - [x] Add placeholder for view toggle (Edit/Stats/Log)
  - [x] Create three sections (hidden/shown based on active view)
  - [x] Add basic "Edit View", "Stats View", "Log View" toggle buttons
  - [x] Add JavaScript to toggle between views (show/hide sections)
- [ ] Test: Navigate to created game, see game header, toggle between empty views

---

## [x] Phase 3: Event Tracking (Edit View)

**Design Reference:** Use `game-ui-option-c.html` as the UI design template. Key features:
- Sticky header with score always visible
- Clickable period badge in header that opens modal (not inline period strip)
- Compact action buttons (2x2 grid)
- Shot drawer for shot type selection
- Fixed bottom bar with undo button
- Mobile-first, minimal scrolling design

### [x] 3.1 Event Tracking - Backend
- [x] Create POST route `/game/<int:game_id>/event` to add event
  - [x] Accept JSON: team_id, period, event_category, event_subcategory
  - [x] Verify game belongs to current_user
  - [x] Verify team_id is either team1 or team2 of the game
  - [x] Create BasketballEvent with all fields
  - [x] Save to database
  - [x] Return JSON success response with event details
- [x] Create DELETE route `/game/<int:game_id>/event/undo` to undo last event
  - [x] Verify game belongs to current_user
  - [x] Find most recent event for this game (order by created_at desc)
  - [x] Delete the event
  - [x] Return JSON success response with deleted event_id
- [x] Create GET route `/game/<int:game_id>/events` to fetch events
  - [x] Verify game belongs to current_user
  - [x] Fetch all events for game (ordered by created_at desc)
  - [x] Return JSON array of events with all details
- [x] Update GET route `/game/<int:game_id>` to pass initial events to template

### [x] 3.2 Edit View - Team Switcher
- [x] Add team switcher UI to edit view section
  - [x] Toggle/segmented control showing both team names
  - [x] Clear visual indication of selected team
  - [x] Large touch target (44px min)
  - [x] Style with `.bbt-team-switcher` class
- [x] Add JavaScript to track selected team (store in variable)
- [x] Test: Click between teams, verify selection updates visually

### [x] 3.3 Edit View - Period Selector (Modal)
- [x] Add clickable period badge in sticky header
  - [x] Display current period (1st, 2nd, 3rd, 4th, or OT)
  - [x] Add down arrow indicator (▼) to show it's clickable
  - [x] Style with `.bbt-period-badge` class
- [x] Create period selection modal
  - [x] Modal overlay with centered content
  - [x] List of period options as large buttons (1st, 2nd, 3rd, 4th, Overtime)
  - [x] Show current period as highlighted/active
  - [x] Allow movement between any periods (forward or backward)
  - [x] Close modal on selection or cancel
  - [x] Style with `.bbt-period-modal` classes
- [x] Add JavaScript to track current period
- [x] Add JavaScript to open/close modal (click outside or close button)
- [x] Update period in game model when changed (AJAX call)
- [x] Create POST route `/game/<int:game_id>/period` to update current_period
- [x] Test: Click period badge, select new period, verify UI updates, verify persistence

### [x] 3.4 Edit View - Primary Action Buttons
- [x] Create HTML structure for four primary buttons
  - [x] "Make Shot" button
  - [x] "Miss Shot" button
  - [x] "Turnover" button
  - [x] "Offensive Rebound" button
- [x] Style buttons with `.bbt-action-btn` class
  - [x] Large (minimum 44px height)
  - [x] Clear labels
  - [x] Touch-friendly spacing
  - [x] Mobile-optimized layout (stack vertically or 2x2 grid)

### [x] 3.5 Edit View - Inline Expansion UI
- [x] Create secondary button sets (hidden by default)
  - [x] Shot types: Layup, Close 2, Far 2, 3-Pointer, Free Throw
  - [x] Turnover types: Traveling, Steal, Other
- [x] Style secondary buttons with `.bbt-secondary-btn` class
- [x] Add JavaScript for inline expansion
  - [x] Click "Make Shot" → show shot type buttons inline (category='make', subcategory=shot type)
  - [x] Click "Miss Shot" → show shot type buttons inline (category='miss', subcategory=shot type)
  - [x] Click "Turnover" → show turnover type buttons inline (category='turnover', subcategory=turnover type)
  - [x] Click "Offensive Rebound" → save immediately with category='rebound', subcategory='Offensive' (no expansion needed)
  - [x] Click secondary button → save event and collapse
  - [x] Click outside or different primary → collapse current expansion

### [x] 3.6 Edit View - Event Saving
- [x] Add JavaScript function to save event via AJAX
  - [x] Gather: selected team, current period, category, subcategory
  - [x] POST to `/game/<int:game_id>/event`
  - [x] Handle success: update UI, show confirmation
  - [x] Handle error: show error message
- [x] Add visual feedback for save success
  - [x] Brief animation or color flash
  - [x] Update event log immediately
  - [x] Update live score immediately
- [x] Test: Click each button combination, verify events save to database

### [x] 3.7 Edit View - Live Score Display (Sticky Header)
- [x] Add sticky header with score display (remains at top when scrolling)
  - [x] Show both team names and scores in compact format
  - [x] Display period badge (clickable) in center
  - [x] Format: Team names above scores, period in center
  - [x] Prominent, easy to read
  - [x] Style with `.bbt-score-header` class
- [x] Add JavaScript function to calculate score
  - [x] Iterate through events where category='make'
  - [x] Free Throw = 1 point
  - [x] Layup/Close 2/Far 2 = 2 points
  - [x] 3-Pointer = 3 points
  - [x] Sum by team_id
- [x] Call calculate score function on:
  - [x] Page load (from initial events)
  - [x] After event is added
  - [x] After event is undone
- [x] Test: Add various make events, verify score updates correctly

### [x] 3.8 Edit View - Event Log Display
- [x] Add event log section to edit view
  - [x] Title: "Recent Events" or similar
  - [x] Show most recent 10 events
  - [x] Style with `.bbt-event-log` class
- [x] For each event, display:
  - [x] Team name
  - [x] Event category/subcategory (e.g., "Make - 3-Pointer")
  - [x] Period (e.g., "2nd")
  - [x] Timestamp or time ago (optional)
- [x] Style as mobile-friendly list (compact but readable)
- [x] Update log in JavaScript after:
  - [x] Event is added (prepend to list, trim to 10)
  - [x] Event is undone (remove from list)
- [x] Test: Add multiple events, verify log shows newest first

### [x] 3.9 Edit View - Undo Button (Inline)
- [x] Add inline undo button under Recent Activity list
  - [x] Positioned directly after the most recent 10 events
  - [x] Small, secondary button style
  - [x] Label clearly ("↶ Undo Last Action")
  - [x] Style with `.bbt-undo-inline` and `.bbt-undo-button-small` classes
  - [x] Disable when no events exist
- [x] Add JavaScript undo handler
  - [x] DELETE to `/game/<int:game_id>/event/undo`
  - [x] On success: remove event from log, recalculate score
  - [x] On error: show error message
- [x] Test: Add events, undo one, verify event removed and score updated
- [x] Test: Undo multiple times, verify unlimited undo works

### [x] 3.10 Edit View - Integration Testing
- [x] Test full event tracking flow
  - [x] Select team, select period, add various events
  - [x] Verify score updates correctly
  - [x] Verify event log updates correctly
  - [x] Switch teams mid-game, add more events
  - [x] Change period, add events in new period
  - [x] Undo several events, verify everything updates
  - [x] Refresh page, verify state persists
- [x] Test edge cases
  - [x] Undo all events (score should be 0-0)
  - [x] Add events in OT period
  - [x] Rapid clicking (ensure no duplicate events)

---

## [x] Phase 4: Stats & Log Views

### [x] 4.1 Stats View - Backend
- [x] Create helper function to calculate game stats
  - [x] Input: game_id
  - [x] Output: dict with stats for both teams
  - [x] For each team calculate:
    - [x] Makes by type (Layup, Close 2, Far 2, 3-Pointer, Free Throw)
    - [x] Misses by type
    - [x] Field Goal % (2-pointers only) - handle division by zero (if no attempts, return None or 0)
    - [x] 3-Point % - handle division by zero
    - [x] Free Throw % - handle division by zero
    - [x] Total Points
    - [x] Turnovers by type (Traveling, Steal, Other)
    - [x] Offensive Rebounds
  - [x] Ensure all percentage calculations check for zero attempts before dividing
- [x] Create API route `/game/<int:game_id>/stats` returning JSON stats
  - [x] Verify game belongs to current_user
  - [x] Call stats calculation function
  - [x] Return JSON

### [x] 4.2 Stats View - Frontend
- [x] Add stats view section to game.html
- [x] Create HTML structure for displaying stats
  - [x] Two columns (one per team) or stacked for mobile
  - [x] Section for shooting (FG%, 3P%, FT%)
  - [x] Section for makes/misses breakdown
  - [x] Section for turnovers
  - [x] Section for rebounds
  - [x] Total points prominent at top
  - [x] Style with `.bbt-stats-view` class
- [x] Add JavaScript to fetch and display stats
  - [x] Fetch from `/game/<int:game_id>/stats` when view is shown
  - [x] Populate HTML with returned data
  - [x] Format percentages nicely (e.g., "45.5%" or "5/11")
  - [x] Handle null/zero percentages: show "-" or "0/0" instead of "NaN%" or error
- [x] Test: Add events, switch to stats view, verify calculations correct
- [x] Test: View stats with no events (all percentages should show gracefully)

### [x] 4.3 Log View - Frontend
- [x] Add log view section to game.html
- [x] Create HTML structure for full event log
  - [x] Table or list showing all events (not just 10)
  - [x] Columns: Team, Event, Period, Time
  - [x] Newest first (reverse chronological)
  - [x] Style with `.bbt-log-view` class
- [x] Add JavaScript to display all events
  - [x] Use events already loaded from page/API
  - [x] Render all events (not just recent 10)
  - [x] Format period as "1st", "2nd", "3rd", "4th", "OT"
  - [x] Format timestamp nicely
- [x] Test: Add many events, switch to log view, verify all show correctly

### [x] 4.4 View Toggling - Polish
- [x] Ensure view toggle buttons are styled consistently
  - [x] Active view highlighted
  - [x] Inactive views clickable
  - [x] Mobile-friendly toggle (tabs or buttons)
- [x] Add smooth transitions between views (optional fade/slide)
- [x] Ensure stats/log refresh when switching to their views
- [x] Test: Toggle between all three views multiple times

---

## Phase 5: Polish & Mobile Optimization

## [x] Phase 5: Polish & Mobile Optimization

### [x] 5.1 Delete Game Functionality
- [x] Create DELETE route `/game/<int:game_id>/delete`
  - [x] Verify game belongs to current_user
  - [x] Delete game (cascade will delete events)
  - [x] Return success response
- [x] Add "Delete Game" button to game page
  - [x] Hide in settings menu or at bottom of page
  - [x] Style as destructive action (red color)
  - [x] Add JavaScript confirmation dialog
  - [x] On confirm: DELETE request, redirect to home page
- [x] Test: Delete a game, verify events also deleted, verify redirect

### [x] 5.2 Mobile CSS Refinement
- [x] Review all pages on mobile viewport (375px width)
- [x] Ensure all touch targets are minimum 44px
- [x] Ensure text is readable (minimum 16px font size)
- [x] Ensure spacing is comfortable for touch
- [x] Ensure forms are easy to fill on mobile
- [x] Test on actual mobile device if possible

### [x] 5.3 Visual Feedback & Animations
- [x] Add subtle animation for event save success
  - [x] Brief color flash or checkmark
  - [x] Don't interrupt user flow
- [x] Add loading states for AJAX calls
  - [x] Disable buttons during save
  - [x] Show spinner if needed
- [x] Add hover/active states for buttons
  - [x] Clear visual feedback on tap
- [x] Add smooth transitions where appropriate
  - [x] View switching
  - [x] Inline expansions
  - [x] Event log updates

### [x] 5.4 Error Handling
- [x] Add error handling for all AJAX calls
  - [x] Show user-friendly error messages
  - [x] Don't lose user's current state
- [x] Add validation messages for forms
  - [x] Team name required
  - [x] Both teams required for game creation
  - [x] Date required for game creation
- [x] Handle edge cases gracefully
  - [x] No teams exist yet
  - [x] No games exist yet
  - [x] Network errors
  - [x] Unauthorized access

### [x] 5.5 User Experience Enhancements
- [x] Add success messages/toasts for actions
  - [x] Team created
  - [x] Game created
  - [x] Game deleted
- [x] Improve loading states
  - [x] Show loading on initial page load
  - [x] Show loading when fetching stats
- [x] Add empty states with helpful messages
  - [x] No teams: "Create your first team to get started"
  - [x] No games: "Create your first game to start tracking"
  - [x] No events: "Start tracking by selecting a team and adding an event"

### [x] 5.6 Accessibility
- [x] Ensure all buttons have clear labels
- [x] Ensure form inputs have labels
- [x] Ensure sufficient color contrast
- [x] Test keyboard navigation where applicable
- [x] Test with screen reader (basic check)

### [x] 5.7 Final Testing
- [x] Full end-to-end test of all features
  - [x] Create teams
  - [x] Create game
  - [x] Track full game (multiple quarters, many events)
  - [x] Use undo multiple times
  - [x] Switch between views
  - [x] Verify stats calculations
  - [x] Delete game
- [x] Test on mobile device
  - [x] Create and track a game
  - [x] Verify all touch interactions work
  - [x] Verify layout looks good
- [x] Cross-browser testing (Safari, Chrome on mobile)
- [x] Performance check (fast loading, smooth interactions)

---

## Phase 6: Future Enhancements (Not in Initial Implementation)

These are documented for future reference but not part of the initial build:

- [ ] Team stats across games (aggregated view)
- [ ] Player-level tracking
- [ ] Defensive rebounds
- [ ] Time tracking within games
- [ ] Multi-user collaboration
- [ ] Game configuration (quarters vs halves)
- [ ] Export game data (CSV, PDF)
- [ ] Offline support (PWA)

---

## Completion Checklist

Before considering the project complete:

- [x] All Phase 1-5 tasks completed
- [x] Database migrations applied successfully
- [x] All routes return appropriate responses
- [x] All templates render correctly
- [x] All JavaScript functions work as expected
- [x] Mobile testing completed
- [x] No console errors
- [x] All user flows tested end-to-end
- [x] Code follows existing project conventions
- [x] CSS uses `bbt-` prefix throughout
- [x] Documentation updated (if needed)

