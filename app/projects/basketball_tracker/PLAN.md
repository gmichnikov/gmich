# Basketball Tracker - Implementation Plan

This document outlines the detailed implementation plan for the Basketball Tracker project, broken down into phases with specific tasks.

---

## Phase 1: Core Structure & Teams Management

### [ ] 1.1 Database Migration
- [ ] Run `flask db migrate -m "Add basketball tracker models"`
- [ ] Review generated migration file
- [ ] Run `flask db upgrade`
- [ ] Verify tables created: `basketball_team`, `basketball_game`, `basketball_event`

### [ ] 1.2 Base CSS Setup
- [ ] Create base mobile-first CSS structure in `static/basketball_tracker/style.css`
- [ ] Define CSS variables for colors, spacing, button sizes
- [ ] Create `.bbt-container` base styles
- [ ] Create `.bbt-button` base styles (minimum 44px height for touch)
- [ ] Create `.bbt-nav` styles for internal navigation

### [ ] 1.3 Internal Navigation Component
- [ ] Create navigation partial/macro for "Games | Teams" navigation
- [ ] Style navigation for mobile (prominent, easy to tap)
- [ ] Ensure navigation appears on all three pages (index, teams, game)

### [ ] 1.4 Teams Page - Backend
- [ ] Create POST route `/teams/create` to add new team
  - [ ] Validate team name is not empty
  - [ ] Associate team with current_user
  - [ ] Save to database
  - [ ] Flash success message
  - [ ] Redirect back to teams page
- [ ] Create POST route `/teams/<int:team_id>/delete` to delete team
  - [ ] Verify team belongs to current_user
  - [ ] Check if team is used in any games (team1_id or team2_id in BasketballGame)
  - [ ] If team has games: flash error message "Cannot delete team with existing games" and redirect
  - [ ] If team has no games: delete team from database, flash success message, redirect
- [ ] Update GET route `/teams` to fetch and pass user's teams to template

### [ ] 1.5 Teams Page - Frontend
- [ ] Update `templates/basketball_tracker/teams.html`
- [ ] Add internal navigation (Games | Teams)
- [ ] Create "Add Team" form
  - [ ] Text input for team name (with proper label)
  - [ ] Submit button
  - [ ] Form styling for mobile
- [ ] Display list of user's teams
  - [ ] Show team name
  - [ ] Add delete button for each team
  - [ ] Style as mobile-friendly list
- [ ] Add confirmation dialog for delete (JavaScript)
- [ ] Test: Create team, view team, delete team

---

## Phase 2: Game Creation & List

### [ ] 2.1 Home Page - Backend
- [ ] Create POST route `/games/create` to create new game
  - [ ] Validate both teams are selected
  - [ ] Validate date is provided
  - [ ] Verify both teams belong to current_user
  - [ ] Create game with team1_id, team2_id, game_date, current_period=1
  - [ ] Associate with current_user
  - [ ] Save to database
  - [ ] Redirect to game page (edit view)
- [ ] Update GET route `/` to fetch and pass:
  - [ ] User's teams (for dropdown)
  - [ ] User's games (ordered by date desc, then created_at desc)

### [ ] 2.2 Home Page - Frontend
- [ ] Update `templates/basketball_tracker/index.html`
- [ ] Add internal navigation (Games | Teams)
- [ ] Create "Create Game" form section
  - [ ] Team 1 dropdown (populated from user's teams)
  - [ ] Team 2 dropdown (populated from user's teams)
  - [ ] Date picker input (default to today's date)
  - [ ] Submit button
  - [ ] Style for mobile (large touch targets)
- [ ] Display games list
  - [ ] Show date (formatted nicely)
  - [ ] Show "Team1 vs Team2" format
  - [ ] Make entire game item clickable (link to game page)
  - [ ] Style as compact mobile list
- [ ] Handle empty states
  - [ ] Show message if no teams exist (link to teams page)
  - [ ] Show message if no games exist
- [ ] Test: Create game with two teams and date, verify redirect to game page

### [ ] 2.3 Game Page - Basic Structure
- [ ] Update GET route `/game/<int:game_id>`
  - [ ] Fetch game by ID
  - [ ] Verify game belongs to current_user (404 if not)
  - [ ] Fetch team1 and team2 objects
  - [ ] Pass game and team data to template
- [ ] Update `templates/basketball_tracker/game.html`
  - [ ] Add internal navigation (back to Games, link to Teams)
  - [ ] Display game header: "Team1 vs Team2" and date
  - [ ] Add placeholder for view toggle (Edit/Stats/Log)
  - [ ] Create three sections (hidden/shown based on active view)
  - [ ] Add basic "Edit View", "Stats View", "Log View" toggle buttons
  - [ ] Add JavaScript to toggle between views (show/hide sections)
- [ ] Test: Navigate to created game, see game header, toggle between empty views

---

## Phase 3: Event Tracking (Edit View)

### [ ] 3.1 Event Tracking - Backend
- [ ] Create POST route `/game/<int:game_id>/event` to add event
  - [ ] Accept JSON: team_id, period, event_category, event_subcategory
  - [ ] Verify game belongs to current_user
  - [ ] Verify team_id is either team1 or team2 of the game
  - [ ] Create BasketballEvent with all fields
  - [ ] Save to database
  - [ ] Return JSON success response with event details
- [ ] Create DELETE route `/game/<int:game_id>/event/undo` to undo last event
  - [ ] Verify game belongs to current_user
  - [ ] Find most recent event for this game (order by created_at desc)
  - [ ] Delete the event
  - [ ] Return JSON success response with deleted event_id
- [ ] Create GET route `/game/<int:game_id>/events` to fetch events
  - [ ] Verify game belongs to current_user
  - [ ] Fetch all events for game (ordered by created_at desc)
  - [ ] Return JSON array of events with all details
- [ ] Update GET route `/game/<int:game_id>` to pass initial events to template

### [ ] 3.2 Edit View - Team Switcher
- [ ] Add team switcher UI to edit view section
  - [ ] Toggle/segmented control showing both team names
  - [ ] Clear visual indication of selected team
  - [ ] Large touch target (44px min)
  - [ ] Style with `.bbt-team-switcher` class
- [ ] Add JavaScript to track selected team (store in variable)
- [ ] Test: Click between teams, verify selection updates visually

### [ ] 3.3 Edit View - Period Selector
- [ ] Add period selector UI to edit view section
  - [ ] Display current period (1st, 2nd, 3rd, 4th, or OT)
  - [ ] Small but visible selector (dropdown or buttons)
  - [ ] Only allow forward movement (1→2→3→4→OT)
  - [ ] Style with `.bbt-period-selector` class
- [ ] Add JavaScript to track current period
- [ ] Add JavaScript to prevent backward period changes
- [ ] Update period in game model when changed (AJAX call)
- [ ] Create POST route `/game/<int:game_id>/period` to update current_period
- [ ] Test: Change period forward, verify UI updates, verify persistence

### [ ] 3.4 Edit View - Primary Action Buttons
- [ ] Create HTML structure for four primary buttons
  - [ ] "Make Shot" button
  - [ ] "Miss Shot" button
  - [ ] "Turnover" button
  - [ ] "Offensive Rebound" button
- [ ] Style buttons with `.bbt-action-btn` class
  - [ ] Large (minimum 44px height)
  - [ ] Clear labels
  - [ ] Touch-friendly spacing
  - [ ] Mobile-optimized layout (stack vertically or 2x2 grid)

### [ ] 3.5 Edit View - Inline Expansion UI
- [ ] Create secondary button sets (hidden by default)
  - [ ] Shot types: Layup, Close 2, Far 2, 3-Pointer, Free Throw
  - [ ] Turnover types: Traveling, Steal, Other
- [ ] Style secondary buttons with `.bbt-secondary-btn` class
- [ ] Add JavaScript for inline expansion
  - [ ] Click "Make Shot" → show shot type buttons inline (category='make', subcategory=shot type)
  - [ ] Click "Miss Shot" → show shot type buttons inline (category='miss', subcategory=shot type)
  - [ ] Click "Turnover" → show turnover type buttons inline (category='turnover', subcategory=turnover type)
  - [ ] Click "Offensive Rebound" → save immediately with category='rebound', subcategory='Offensive' (no expansion needed)
  - [ ] Click secondary button → save event and collapse
  - [ ] Click outside or different primary → collapse current expansion

### [ ] 3.6 Edit View - Event Saving
- [ ] Add JavaScript function to save event via AJAX
  - [ ] Gather: selected team, current period, category, subcategory
  - [ ] POST to `/game/<int:game_id>/event`
  - [ ] Handle success: update UI, show confirmation
  - [ ] Handle error: show error message
- [ ] Add visual feedback for save success
  - [ ] Brief animation or color flash
  - [ ] Update event log immediately
  - [ ] Update live score immediately
- [ ] Test: Click each button combination, verify events save to database

### [ ] 3.7 Edit View - Live Score Display
- [ ] Add score display UI at top of edit view
  - [ ] Show both team names and scores
  - [ ] Format: "Team A: 45 - Team B: 38"
  - [ ] Prominent, easy to read
  - [ ] Style with `.bbt-score-display` class
- [ ] Add JavaScript function to calculate score
  - [ ] Iterate through events where category='make'
  - [ ] Free Throw = 1 point
  - [ ] Layup/Close 2/Far 2 = 2 points
  - [ ] 3-Pointer = 3 points
  - [ ] Sum by team_id
- [ ] Call calculate score function on:
  - [ ] Page load (from initial events)
  - [ ] After event is added
  - [ ] After event is undone
- [ ] Test: Add various make events, verify score updates correctly

### [ ] 3.8 Edit View - Event Log Display
- [ ] Add event log section to edit view
  - [ ] Title: "Recent Events" or similar
  - [ ] Show most recent 10 events
  - [ ] Style with `.bbt-event-log` class
- [ ] For each event, display:
  - [ ] Team name
  - [ ] Event category/subcategory (e.g., "Make - 3-Pointer")
  - [ ] Period (e.g., "2nd")
  - [ ] Timestamp or time ago (optional)
- [ ] Style as mobile-friendly list (compact but readable)
- [ ] Update log in JavaScript after:
  - [ ] Event is added (prepend to list, trim to 10)
  - [ ] Event is undone (remove from list)
- [ ] Test: Add multiple events, verify log shows newest first

### [ ] 3.9 Edit View - Undo Button
- [ ] Add undo button to edit view
  - [ ] Position prominently but not in the way
  - [ ] Label clearly ("Undo Last")
  - [ ] Style with `.bbt-undo-btn` class
  - [ ] Disable when no events exist
- [ ] Add JavaScript undo handler
  - [ ] DELETE to `/game/<int:game_id>/event/undo`
  - [ ] On success: remove event from log, recalculate score
  - [ ] On error: show error message
- [ ] Test: Add events, undo one, verify event removed and score updated
- [ ] Test: Undo multiple times, verify unlimited undo works

### [ ] 3.10 Edit View - Integration Testing
- [ ] Test full event tracking flow
  - [ ] Select team, select period, add various events
  - [ ] Verify score updates correctly
  - [ ] Verify event log updates correctly
  - [ ] Switch teams mid-game, add more events
  - [ ] Change period, add events in new period
  - [ ] Undo several events, verify everything updates
  - [ ] Refresh page, verify state persists
- [ ] Test edge cases
  - [ ] Undo all events (score should be 0-0)
  - [ ] Add events in OT period
  - [ ] Rapid clicking (ensure no duplicate events)

---

## Phase 4: Stats & Log Views

### [ ] 4.1 Stats View - Backend
- [ ] Create helper function to calculate game stats
  - [ ] Input: game_id
  - [ ] Output: dict with stats for both teams
  - [ ] For each team calculate:
    - [ ] Makes by type (Layup, Close 2, Far 2, 3-Pointer, Free Throw)
    - [ ] Misses by type
    - [ ] Field Goal % (2-pointers only) - handle division by zero (if no attempts, return None or 0)
    - [ ] 3-Point % - handle division by zero
    - [ ] Free Throw % - handle division by zero
    - [ ] Total Points
    - [ ] Turnovers by type (Traveling, Steal, Other)
    - [ ] Offensive Rebounds
  - [ ] Ensure all percentage calculations check for zero attempts before dividing
- [ ] Create API route `/game/<int:game_id>/stats` returning JSON stats
  - [ ] Verify game belongs to current_user
  - [ ] Call stats calculation function
  - [ ] Return JSON

### [ ] 4.2 Stats View - Frontend
- [ ] Add stats view section to game.html
- [ ] Create HTML structure for displaying stats
  - [ ] Two columns (one per team) or stacked for mobile
  - [ ] Section for shooting (FG%, 3P%, FT%)
  - [ ] Section for makes/misses breakdown
  - [ ] Section for turnovers
  - [ ] Section for rebounds
  - [ ] Total points prominent at top
  - [ ] Style with `.bbt-stats-view` class
- [ ] Add JavaScript to fetch and display stats
  - [ ] Fetch from `/game/<int:game_id>/stats` when view is shown
  - [ ] Populate HTML with returned data
  - [ ] Format percentages nicely (e.g., "45.5%" or "5/11")
  - [ ] Handle null/zero percentages: show "-" or "0/0" instead of "NaN%" or error
- [ ] Test: Add events, switch to stats view, verify calculations correct
- [ ] Test: View stats with no events (all percentages should show gracefully)

### [ ] 4.3 Log View - Frontend
- [ ] Add log view section to game.html
- [ ] Create HTML structure for full event log
  - [ ] Table or list showing all events (not just 10)
  - [ ] Columns: Team, Event, Period, Time
  - [ ] Newest first (reverse chronological)
  - [ ] Style with `.bbt-log-view` class
- [ ] Add JavaScript to display all events
  - [ ] Use events already loaded from page/API
  - [ ] Render all events (not just recent 10)
  - [ ] Format period as "1st", "2nd", "3rd", "4th", "OT"
  - [ ] Format timestamp nicely
- [ ] Test: Add many events, switch to log view, verify all show correctly

### [ ] 4.4 View Toggling - Polish
- [ ] Ensure view toggle buttons are styled consistently
  - [ ] Active view highlighted
  - [ ] Inactive views clickable
  - [ ] Mobile-friendly toggle (tabs or buttons)
- [ ] Add smooth transitions between views (optional fade/slide)
- [ ] Ensure stats/log refresh when switching to their views
- [ ] Test: Toggle between all three views multiple times

---

## Phase 5: Polish & Mobile Optimization

### [ ] 5.1 Delete Game Functionality
- [ ] Create DELETE route `/game/<int:game_id>/delete`
  - [ ] Verify game belongs to current_user
  - [ ] Delete game (cascade will delete events)
  - [ ] Return success response
- [ ] Add "Delete Game" button to game page
  - [ ] Hide in settings menu or at bottom of page
  - [ ] Style as destructive action (red color)
  - [ ] Add JavaScript confirmation dialog
  - [ ] On confirm: DELETE request, redirect to home page
- [ ] Test: Delete a game, verify events also deleted, verify redirect

### [ ] 5.2 Mobile CSS Refinement
- [ ] Review all pages on mobile viewport (375px width)
- [ ] Ensure all touch targets are minimum 44px
- [ ] Ensure text is readable (minimum 16px font size)
- [ ] Ensure spacing is comfortable for touch
- [ ] Ensure forms are easy to fill on mobile
- [ ] Test on actual mobile device if possible

### [ ] 5.3 Visual Feedback & Animations
- [ ] Add subtle animation for event save success
  - [ ] Brief color flash or checkmark
  - [ ] Don't interrupt user flow
- [ ] Add loading states for AJAX calls
  - [ ] Disable buttons during save
  - [ ] Show spinner if needed
- [ ] Add hover/active states for buttons
  - [ ] Clear visual feedback on tap
- [ ] Add smooth transitions where appropriate
  - [ ] View switching
  - [ ] Inline expansions
  - [ ] Event log updates

### [ ] 5.4 Error Handling
- [ ] Add error handling for all AJAX calls
  - [ ] Show user-friendly error messages
  - [ ] Don't lose user's current state
- [ ] Add validation messages for forms
  - [ ] Team name required
  - [ ] Both teams required for game creation
  - [ ] Date required for game creation
- [ ] Handle edge cases gracefully
  - [ ] No teams exist yet
  - [ ] No games exist yet
  - [ ] Network errors
  - [ ] Unauthorized access

### [ ] 5.5 User Experience Enhancements
- [ ] Add success messages/toasts for actions
  - [ ] Team created
  - [ ] Game created
  - [ ] Game deleted
- [ ] Improve loading states
  - [ ] Show loading on initial page load
  - [ ] Show loading when fetching stats
- [ ] Add empty states with helpful messages
  - [ ] No teams: "Create your first team to get started"
  - [ ] No games: "Create your first game to start tracking"
  - [ ] No events: "Start tracking by selecting a team and adding an event"

### [ ] 5.6 Accessibility
- [ ] Ensure all buttons have clear labels
- [ ] Ensure form inputs have labels
- [ ] Ensure sufficient color contrast
- [ ] Test keyboard navigation where applicable
- [ ] Test with screen reader (basic check)

### [ ] 5.7 Final Testing
- [ ] Full end-to-end test of all features
  - [ ] Create teams
  - [ ] Create game
  - [ ] Track full game (multiple quarters, many events)
  - [ ] Use undo multiple times
  - [ ] Switch between views
  - [ ] Verify stats calculations
  - [ ] Delete game
- [ ] Test on mobile device
  - [ ] Create and track a game
  - [ ] Verify all touch interactions work
  - [ ] Verify layout looks good
- [ ] Cross-browser testing (Safari, Chrome on mobile)
- [ ] Performance check (fast loading, smooth interactions)

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

- [ ] All Phase 1-5 tasks completed
- [ ] Database migrations applied successfully
- [ ] All routes return appropriate responses
- [ ] All templates render correctly
- [ ] All JavaScript functions work as expected
- [ ] Mobile testing completed
- [ ] No console errors
- [ ] All user flows tested end-to-end
- [ ] Code follows existing project conventions
- [ ] CSS uses `bbt-` prefix throughout
- [ ] Documentation updated (if needed)
