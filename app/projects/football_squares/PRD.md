# Football Squares - Product Requirements Document

## Overview
Football Squares is an app that allows a single user to create and manage multiple 10x10 "squares" grids for football games (like the Super Bowl). The user can configure teams, add participants, fill the grid manually or randomly, and track scores to determine winners for each quarter and potentially overtime.

## Project Details
- **Project name:** `football_squares`
- **Route prefix:** `/football-squares`
- **CSS prefix:** `fs-` (all classes must use this prefix)
- **Database tables:** Prefixed with `football_squares_`
- **Authentication:** Required for management; Read-only view available via shareable link.

## Goals
1. Allow users to manage multiple independent football square grids.
2. Provide flexible ways to fill the grid (manual entry, full randomization, or filling the remainder randomly).
3. Support two types of axis labeling: Draft Order (fixed 0-9) or Randomized.
4. Automatically calculate winners based on quarter/OT scores and assigned point values.
5. Provide a non-authenticated, read-only view of the grid for sharing with participants.

## User Stories
1. **As a user**, I want to create a new grid by giving it a name and specifying the two teams playing (with their colors).
2. **As a user**, I want to add a list of participants to my grid.
3. **As a user**, I want to choose whether the digits (0-9) on the axes are in draft order (0-9) or randomized.
4. **As a user**, I want to manually click a square and assign it to a participant.
5. **As a user**, I want to click a button to fill all remaining empty squares randomly from my participant list.
6. **As a user**, I want to assign different point values (prizes) to each of the four quarters and an optional overtime period.
7. **As a user**, I want to enter the score at the end of each quarter (and OT if applicable) and see which participant won.
8. **As a user**, I want to share a read-only link with my friends so they can see the grid without logging in.

## Functional Requirements

### 1. Grid Management
- Users can view a list of all their created grids.
- Users can create, edit (name/teams), and delete grids.
- Each grid is a 10x10 matrix (100 squares).
- **Shareable Link**: Each grid has a unique, non-guessable slug (e.g., UUID) that allows anyone with the link to view the grid and winners in read-only mode.

### 2. Team & Axis Configuration
- **Teams**: Each grid has two teams. Each team has a name and two colors (primary/secondary) used for UI styling of their respective axis.
- **Axis Digits**: 
    - **Draft Order**: The digits 0-9 are placed in sequence.
    - **Random**: The digits 0-9 are shuffled for each axis.
    - This choice is made during grid setup or configuration.

### 3. Participant Management
- Users can add/remove participants to a specific grid.
- Participants are just names for this project (not linked to system users).

### 4. Grid Filling Logic
- **Manual Fill**: The user can click any square and select a participant from a dropdown to assign it.
- **Auto-Fill Remainder**: A feature to take all participants and distribute the remaining empty squares among them as evenly as possible.
- **Full Randomization**: A feature to clear the grid and assign all 100 squares randomly to the list of participants.

### 5. Scoring & Winners
- **Point Values**: Users can enter a "points" or "prize" value for Quarter 1, Quarter 2, Quarter 3, Quarter 4 (End of Regulation), and an optional Overtime/Final Score.
- **Score Entry**: Users can enter the score for each team at the end of each quarter.
- **Overtime Handling**: 
    - The app should provide a specific field for the Final Score (including OT).
    - If the game ends in regulation, the Quarter 4 score and Final Score are identical.
    - If the game goes to OT, the user enters the OT final score separately to determine the OT winner.
- **Winner Calculation**: 
    - The app takes the last digit of each team's score for the given period.
    - It finds the square at the intersection of those two digits on the axes.
    - It identifies the participant assigned to that square as the winner.

## Data Model

### FootballSquaresGrid
- `id`: Primary Key
- `user_id`: FK to User (Owner)
- `name`: String (e.g., "Super Bowl LIX")
- `share_slug`: String (Unique, non-guessable UUID/token)
- `team1_name`: String
- `team1_color_primary`: String (Hex)
- `team1_color_secondary`: String (Hex)
- `team2_name`: String
- `team2_color_primary`: String (Hex)
- `team2_color_secondary`: String (Hex)
- `axis_type`: Enum (Draft, Random)
- `team1_digits`: String/JSON (The sequence of 0-9 for Team 1 axis)
- `team2_digits`: String/JSON (The sequence of 0-9 for Team 2 axis)
- `created_at`: Timestamp

### FootballSquaresParticipant
- `id`: Primary Key
- `grid_id`: FK to FootballSquaresGrid
- `name`: String

### FootballSquaresSquare
- `id`: Primary Key
- `grid_id`: FK to FootballSquaresGrid
- `participant_id`: FK to FootballSquaresParticipant (Nullable)
- `x_coord`: Integer (0-9)
- `y_coord`: Integer (0-9)

### FootballSquaresQuarter
- `id`: Primary Key
- `grid_id`: FK to FootballSquaresGrid
- `quarter_number`: Integer (1-5, where 5 is OT/Final)
- `team1_score`: Integer (Nullable)
- `team2_score`: Integer (Nullable)
- `payout_description`: String (e.g., "$25" or "25 points")

## Implementation Phases

### Phase 1: Models & Basic List View
- Create database models.
- Implement the "My Grids" list page and "Create New Grid" form (including share slug generation).
- *Testing*: Create a grid and see it in the list.

### Phase 2: Grid Configuration & Participants
- Implement Team and Participant management for a specific grid.
- Add the ability to set the axis type and generate the 0-9 digits.
- *Testing*: Add participants and see them listed on the grid page.

### Phase 3: The 10x10 Grid & Filling
- Build the visual 10x10 grid with labeled axes.
- Implement manual square assignment (AJAX/Fetch for better UX).
- Implement the "Randomize Remaining" and "Randomize All" buttons.
- *Testing*: Fill the grid manually and via randomization. Verify 100 squares are filled.

### Phase 4: Scoring, Results & Sharing
- Add a section to manage Quarter scores and payouts (including OT).
- Implement the winner calculation logic.
- Highlight the winning square for each completed quarter.
- Implement the read-only public view page via `share_slug`.
- *Testing*: Enter scores and verify the correct participant is named winner. Verify public view works.

### Phase 5: Styling & Polish
- Apply team colors to the grid headers and axes.
- Ensure the `fs-` prefix is used consistently.
- Responsive design for mobile viewing.

## Success Criteria
- [ ] Users can create multiple grids.
- [ ] Grids can be filled manually or randomly.
- [ ] Axis digits can be sequential or randomized.
- [ ] The app correctly identifies winners based on entered scores.
- [ ] Friends can view the grid via a shareable link without logging in.
