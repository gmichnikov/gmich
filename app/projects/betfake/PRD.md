# BetFake Project - Product Requirements Document

## Overview
BetFake is a sports betting simulator that allows users to place wagers on real sporting events using entirely fake money. The app integrates with the Odds API to provide real-time odds for major sports and markets.

## Project Details
- **Project name:** `betfake`
- **Route prefix:** `/betfake`
- **CSS prefix:** `bf-` (all classes must use this prefix)
- **Database tables:** Prefixed with `betfake_`
- **Authentication:** Required
- **Data ownership:** Private wagers, but public leaderboards (V2)
- **Primary data source:** The Odds API

## Goals
1. Provide a risk-free environment for users to learn about sports betting.
2. Maintain high accuracy by using real-time odds from a professional API.
3. Track user performance over time (balance, win/loss ratio).
4. Support major betting markets: Moneyline, Point Spreads, Over/Under, and Futures.

## User Stories
1. **As a user**, I want to see a list of upcoming games and their real-time odds.
2. **As a user**, I want to place a bet (Moneyline, Spread, or Total) using my fake money balance.
3. **As a user**, I want to bet on future outcomes (like "Who will win the NBA Championship").
4. **As a user**, I want to see my open bets and my betting history.
5. **As a user**, I want to see my current balance and how much I've won/lost.

## Functional Requirements

### 1. Account & Balance
- Users can create multiple "Betting Accounts" within the BetFake project.
- Each new account starts with a fixed balance of $100 fake money.
- These balances are entirely separate from the "Credits" used in other projects (e.g., Ask Many LLMs).
- Users can choose which account to use when placing a bet.
- Balance is updated immediately when a bet is placed (deduction).
- Balance is updated when a bet is settled (payout).
- **Transaction History**: Users can view a log of all balance changes (wagers, payouts, account creation) for each account.

### 2. Market Support
- **American Odds Only**: All odds are displayed and stored in American format (e.g., -110, +150).
- **Moneyline (h2h)**: Betting on the winner.
  - For basketball/American sports: 2 outcomes (home/away)
  - For soccer: 3 outcomes (home/away/draw) - **Soccer is h2h only in V1.**
- **Point Spreads**: Betting on the margin of victory (mainly available for US sports like NBA, NFL).
- **Over/Under (Totals)**: Betting on the combined score (mainly available for US sports).
- **Futures (outrights)**: Long-term bets on outcomes like "Who will win the NBA Championship". These are markets not necessarily tied to a specific game.

**V1 Sport-Specific Support:**
- **Basketball (NBA)**: h2h, spreads, totals, futures (championship winner)
- **Football (NFL)**: h2h, spreads, totals
- **Soccer (EPL)**: h2h only (no spreads or totals)

### 3. Odds API Integration
- **Auto-Sync**: Daily fetching of odds and scores via automated task (e.g., Heroku Scheduler).
- **Manual Admin Fetch**: Admins must have the ability to manually trigger a sync (odds and scores) via an admin-only dashboard page.
- Storing games and markets locally to minimize API calls and ensure performance.
- **Bookmaker Selection**: Fetch odds from 1-2 major bookmakers (e.g., FanDuel, DraftKings) to minimize data volume while maintaining competitive odds.
- **Market Update Logic**:
    - **Immutability**: Once a `BetfakeMarket` and its `BetfakeOutcome` records are created, they are never updated.
    - If **anything** changes (odds move, spread points move, or total points move), the existing market is marked `is_active=False` and a **new** `BetfakeMarket` with new `BetfakeOutcome` records is created.
    - This maintains a full historical record of every line and price offered for every event.
- **Automated Settlement**: The Odds API provides event results (scores as strings, need conversion to integers). We will use these results to automatically grade bets once the events are concluded.

### 4. Bet Placement & Settlement
- Bets must be placed before the event start time (except for futures which have their own closing times).
- **Betting Restriction**: Users are prevented from betting on a game if the current time is after the `commence_time` (no "live betting" in V1).
- **Bet Validation Rules**:
    - Maximum bet: Entire account balance
    - Minimum bet: None (can bet any amount > $0)
    - Decimal precision: Up to 2 decimal places (like dollars and cents)
- **Snapshot Capture**: When a user places a bet, we capture a snapshot of the market at that exact moment on the `BetfakeBet` record:
    - `odds_at_time`: The American odds (e.g., -110).
    - `line_at_time`: The point value (for spreads and totals).
    - `outcome_name_at_time`: The name of the outcome (for display).
- This ensures the user's payout and grading are based on the exact conditions when they placed the bet, even if that specific market record is later deactivated.
- Bets are "Pending" until the event is settled.
- **Settlement**: Automated grading based on scores/results fetched from the Odds API.
- **Push Logic**: If a bet results in a "Push" (e.g., final margin exactly equals the spread), the original `wager_amount` is returned to the user's account balance.

## Data Model (V1)

**Note on Enums**: Fields marked as `enum` should use Python Enum types to prevent typos and improve code maintainability.

**Note on Market Structure**: Markets can have multiple outcomes (e.g., soccer has home/away/draw). The `BetfakeMarket` represents the market container, while `BetfakeOutcome` represents each betting option within that market. When odds change, we deactivate the entire market and all its outcomes, then create new records.

### BetfakeAccount
- `id`
- `user_id` (FK to User)
- `name` (string, e.g., "My Main Account", "Risky Bets")
- `balance` (float, defaults to 100.0)
- `created_at`

### BetfakeGame
- `id`
- `external_id` (ID from Odds API)
- `sport_key` (e.g., 'americanfootball_nfl', 'basketball_nba')
- `sport_title` (e.g., 'NFL', 'NBA') - user-friendly display name
- `home_team`, `away_team` (nullable for futures markets which don't have games)
- `commence_time` (UTC, displayed to users in their account timezone. For futures, this is the championship end date)
- `status` (enum: Scheduled, Live, Completed)
- `home_score`, `away_score` (nullable, updated when game ends)

### BetfakeMarket
- `id`
- `game_id` (FK to BetfakeGame, nullable for futures)
- `type` (enum: h2h, spreads, totals, outrights)
- `label` (e.g., "NBA Championship Winner 2026", nullable for game-tied markets)
- `bookmaker_key` (string, e.g., "fanduel", "draftkings")
- `external_market_id` (string, nullable)
- `is_active` (boolean)
- `created_at` (timestamp)
- `marked_inactive_at` (timestamp, nullable - tracks when market was deactivated)

### BetfakeOutcome
- `id`
- `market_id` (FK to BetfakeMarket)
- `outcome_name` (e.g., "Lakers", "Draw", "Over", "Under")
- `odds` (Integer, American odds e.g. -110 or +150)
- `point_value` (Float, nullable - for spreads and totals, e.g., -7.5 or 210.5)
- `is_active` (boolean, mirrors parent market's is_active)

### BetfakeBet
- `id`
- `user_id` (FK to User)
- `account_id` (FK to BetfakeAccount)
- `outcome_id` (FK to BetfakeOutcome)
- `wager_amount` (Float)
- `odds_at_time` (Integer, American odds e.g. -110 or +150)
- `line_at_time` (Float, nullable, for spreads/totals e.g. -7.5 or 210.5)
- `outcome_name_at_time` (String, e.g. "Lakers", "Draw", "Over")
- `potential_payout` (Float)
- `status` (enum: Pending, Won, Lost, Push)
- `placed_at` (Timestamp)
- `settled_at` (Timestamp, nullable)

### BetfakeTransaction
- `id`
- `user_id` (FK to User)
- `account_id` (FK to BetfakeAccount)
- `bet_id` (FK to BetfakeBet, optional)
- `amount` (+/- change)
- `type` (enum: Wager, Payout, Account_Creation)
- `created_at`

## Pages & Navigation

### 1. Dashboard (`/betfake/`)
- Summary of current balance, total profit/loss.
- List of active/pending bets.
- Links to browse sports.

### 2. Browse Sports (`/betfake/sports/<sport_key>`)
- List of upcoming games for a specific sport.
- Quick-bet buttons for major markets (ML, Spread, Total).

### 3. Futures Page (`/betfake/futures`)
- Grouped by sport/competition.
- List of available futures bets.

### 4. Bet History (`/betfake/history`)
- Full list of settled bets with results.

## Implementation Phases

### Phase 1: Core Data & Basic Dashboard
- Implement all database models.
- Set up the initial $100 balance for new accounts.
- Create a basic dashboard showing balance and account list.
- *Testing*: Verify balance creation and database schema.

### Phase 2: Odds API Integration (Read-only)
- Set up a service to fetch data from the Odds API.
- Create a script/task to populate `BetfakeGame` and `BetfakeMarket`.
- **Planned Sync**: Daily refresh of odds and game data (can be adjusted later).
- *Testing*: Manually run fetch and check if games/odds appear in the DB.

### Phase 3: Bet Placement
- Build the UI for selecting odds and entering a wager.
- Implement the backend logic to validate balance, create `BetfakeBet`, and deduct funds.
- *Testing*: Place a bet and verify balance deduction and bet record.

### Phase 4: Bet Settlement
- Implement logic to fetch scores from the Odds API.
- Build the "Grader" that marks bets as Won/Lost/Push.
- Handle payouts and update balances.
- *Testing*: Mock a game result and verify bet settlement and payout.

### Phase 5: Futures & Polishing
- Implement the specific UI and logic for Futures markets.
- Add "Bet History" and "Profit/Loss" charts.
- Mobile UI optimizations (using `bf-` prefixes).
- *Testing*: Full end-to-end flow from betting to settlement.

## Success Criteria
- [ ] Users can reliably place bets on real-world games.
- [ ] Balances are accurately tracked and protected against over-betting.
- [ ] Odds are updated frequently from the Odds API.
- [ ] Bets are automatically (or easily) settled once games conclude.

## Out of Scope - Future Enhancements
- **Leaderboards**: Publicly visible "Top Accounts" to foster competition.
- **Live Betting**: Allowing bets on games that are currently in progress.
- **Parlays**: Combining multiple bets for a higher payout.
- **Daily Bonus**: Providing users with a daily refill of fake money instead of unlimited account creation.
- **Bet Slip Preview Component**: Before confirming, show a clear breakdown (Risk, To Win, Potential Return).
- **Quick Stats Widget**: Dashboard widget showing Win Rate %, Biggest Win, Longest Winning Streak, Favorite Sport.
- **Recent Bets Mini-List**: Show last 3-5 bets on dashboard for quick context.
- **Balance Over Time Graph**: Simple line chart showing balance history using transaction data.
- **Sport Filtering/Favorites**: Let users mark sports as favorites so they appear first in navigation.
- **Bet History Filters**: Filter by sport, status (Won/Lost/Push), and date range.
- **Popular Bets Section**: Show which games have the most betting action.
- **Account Descriptions**: Add optional description field to accounts for user notes like "Conservative Strategy".
- **Bet Confirmation Message**: After placing bet, show success message with reference number or link to view it.
- **Odds Format Preference**: Let users choose between different display themes (e.g., Dark/Light mode).
- **Account Creation Limits**: Implement restrictions to prevent exploitation through unlimited account creation.

## Technical Notes

### API Response Details (from exploration)
- **Bookmaker Count**: The Odds API returns ~9 bookmakers per region. We will fetch only 1-2 (FanDuel, DraftKings) to minimize data volume and API costs.
- **Bookmaker Variance**: Odds can vary significantly between bookmakers (e.g., Thunder +110 on FanDuel vs +130 on DraftKings for NBA Championship).
- **Event IDs**: Stable across all endpoints (events, odds, scores) - perfect for data linking.
- **Scores Format**: API returns scores as strings (e.g., `"113"`). Must convert to integers when storing.
- **Scores Structure**: Upcoming/future games have `completed: false` and `scores: null`. Completed games have `completed: true` and populated scores array.
- **Three-Way Markets**: Soccer h2h markets have 3 outcomes (home/away/draw). Basketball/football have 2 (home/away).
- **Futures Structure**: Futures are separate sport entries (e.g., `basketball_nba_championship_winner`) with null home/away teams, single "outrights" market, and many outcomes (30 teams for NBA).
- **Futures Commence Time**: Represents the championship end date (e.g., June 10 for NBA Finals), not individual game dates.
- **Market Availability**: Not all bookmakers support spreads/totals for soccer. Focus on h2h for soccer in V1.
- **Bookmaker Updates**: Each bookmaker updates independently, so timestamps vary within the same game.

## User TODOs & Open Questions
- [ ] **API Scope**: Define exactly which sports and leagues to fetch beyond NBA and EPL (e.g., NFL, MLB).
- [ ] **Sync Frequency**: Finalize the refresh timing (planned for daily, but might need adjustment for game starts).
- [ ] **Settlement Logic**: Decide if the settlement process (grading bets) should be combined with the odds fetching process or stay separate, based on how the API returns scores.
- [ ] **Futures Organization**: Decide how to display/organize futures markets in the UI (they're not tied to specific games).
