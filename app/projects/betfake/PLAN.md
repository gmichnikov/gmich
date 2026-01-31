# BetFake Project - Implementation Plan

This plan follows the PRD phases but breaks them into smaller, testable chunks. The plan is based on the betfake PRD and insights from API exploration.

---

## Phase 1: Core Data & Basic Dashboard [COMPLETED]

### 1.1 Database Model Setup [COMPLETED]

- [x] Create all enum classes in `models.py`
  - [x] `GameStatus` enum (Scheduled, Live, Completed)
  - [x] `MarketType` enum (h2h, spreads, totals, outrights)
  - [x] `BetStatus` enum (Pending, Won, Lost, Push)
  - [x] `TransactionType` enum (Wager, Payout, Account_Creation)
- [x] Create `BetfakeAccount` model
  - [x] Define fields: `id`, `user_id`, `name`, `balance`, `created_at`
  - [x] Set default balance to 100.0
  - [x] Add foreign key relationship to User model
  - [x] Add `__repr__` method
- [x] Create `BetfakeGame` model
  - [x] Define fields: `id`, `external_id`, `sport_key`, `sport_title`
  - [x] Add `home_team`, `away_team` (nullable for futures)
  - [x] Add `commence_time`, `status`, `home_score`, `away_score` (nullable)
  - [x] Add `last_update` timestamp
  - [x] Add `__repr__` method
- [x] Create `BetfakeMarket` model
  - [x] Define fields: `id`, `game_id` (nullable), `type`, `label` (nullable)
  - [x] Add `bookmaker_key`, `external_market_id` (nullable)
  - [x] Add `is_active`, `created_at`, `marked_inactive_at` (nullable)
  - [x] Add `last_update` (timestamp from API)
  - [x] Add foreign key to BetfakeGame
  - [x] Add `__repr__` method
- [x] Create `BetfakeOutcome` model
  - [x] Define fields: `id`, `market_id`, `outcome_name`
  - [x] Add `odds` (Integer), `point_value` (nullable Float)
  - [x] Add `is_active` (mirrors parent market)
  - [x] Add foreign key to BetfakeMarket
  - [x] Add `__repr__` method
- [x] Create `BetfakeBet` model
  - [x] Define fields: `id`, `user_id`, `account_id`, `outcome_id`
  - [x] Add `wager_amount`, `odds_at_time`, `line_at_time` (nullable)
  - [x] Add `outcome_name_at_time`, `potential_payout`
  - [x] Add `status`, `placed_at`, `settled_at` (nullable)
  - [x] Add foreign keys to User, BetfakeAccount, BetfakeOutcome
  - [x] Add `__repr__` method
- [x] Create `BetfakeTransaction` model
  - [x] Define fields: `id`, `user_id`, `account_id`, `bet_id` (nullable)
  - [x] Add `amount`, `type`, `created_at`
  - [x] Add foreign keys to User, BetfakeAccount, BetfakeBet
  - [x] Add `__repr__` method

**Manual Testing 1.1:**
- [x] Run `flask db migrate -m "Add betfake models"`
- [x] Review migration file for correctness (check all tables, enums, constraints)
- [x] Run `flask db upgrade`
- [x] Verify all 6 tables exist in database with correct schema
- [x] Verify enum types are created correctly
- [x] Verify foreign key relationships are correct

---

### 1.2 Blueprint and Route Structure [COMPLETED]

- [x] Update `__init__.py` to initialize blueprint properly
  - [x] Import Blueprint and register with url_prefix `/betfake`
- [x] Create `routes.py` with placeholder routes
  - [x] `GET /` - dashboard (placeholder)
  - [x] `GET /accounts` - list accounts (placeholder)
  - [x] `POST /accounts/create` - create account (placeholder)
  - [x] `GET /sports/<sport_key>` - browse games (placeholder)
  - [x] `GET /futures` - futures markets (placeholder)
  - [x] `GET /history` - bet history (placeholder)
- [x] Add `@login_required` decorator to all routes
- [x] Verify blueprint is registered in main app `__init__.py`
- [x] Create templates directory structure
  - [x] Create `templates/betfake/` directory
  - [x] Create `static/betfake/` directory for CSS/JS

**Manual Testing 1.2:**
- [x] Verify `/betfake/` route loads (even if empty)
- [x] Verify unauthenticated users are redirected to login
- [x] Verify 404 for non-existent routes under `/betfake`

---

### 1.3 Helper Functions & Utilities [COMPLETED]

- [x] Create `utils.py` for helper functions
  - [x] `get_account_by_id(account_id, user_id)` - fetch account with auth check
  - [x] `calculate_american_odds_payout(wager, odds)` - payout calculation (American odds only)
  - [x] `format_odds_display(odds)` - format odds for display (+150, -110)
  - [x] `is_game_bettable(game)` - check if betting window is open
- [x] Create date/time formatting helpers
  - [x] Convert UTC to user's timezone (use user.time_zone)
  - [x] Format as "Jan 31, 2026 3:45 PM"
  - [x] Register as Jinja filters if needed
- [x] Add CSS base styles in `static/betfake/style.css`
  - [x] Define CSS variables for colors, spacing
  - [x] All classes use `bf-` prefix
  - [x] Mobile-first responsive design
  - [x] Base button styles (min 44px height)

**Manual Testing 1.3:**
- [x] Test payout calculation with positive and negative odds
- [x] Test date formatting with different timezones
- [x] Test account authorization (try accessing another user's account)

---

### 1.4 Dashboard - Accounts Management [COMPLETED]

- [x] Implement `GET /` dashboard route
  - [x] Query user's accounts (ordered by created_at)
  - [x] Query pending bets for user
  - [x] Calculate total balance across accounts
  - [x] Calculate total profit/loss (sum of Won/Lost bet outcomes)
- [x] Implement `POST /accounts/create` route
  - [x] Validate account name is not empty
  - [x] Create new account with balance=100.0
  - [x] Create transaction record (type=Account_Creation, amount=100)
  - [x] Flash success message
  - [x] Redirect to dashboard
- [x] Create `betfake/index.html` template
  - [x] Page header "BetFake - Sports Betting Simulator"
  - [x] Accounts section
    - [x] Display each account with name and balance
    - [x] "Create New Account" button/form
  - [x] Quick stats section
    - [x] Total balance across all accounts
    - [x] Total profit/loss (placeholder if no bets)
  - [x] Pending bets section
    - [x] List of active bets with game, outcome, wager
    - [x] Empty state: "No active bets"
  - [x] Navigation to sports/futures/history
  - [x] Use `bf-` prefix for all CSS classes

**Manual Testing 1.4:**
- [x] Dashboard loads for authenticated user
- [x] Create an account, verify balance=$100
- [x] Verify transaction record created
- [x] Empty states display correctly
- [x] Navigation links work

---

## Phase 2: Odds API Integration (Read-only) [COMPLETED]

### 2.1 API Service Setup [COMPLETED]

- [x] Create `services/odds_api.py` module
  - [x] Add configuration (API key from environment)
  - [x] Add base URL and bookmaker settings (fanduel,draftkings)
  - [x] Create session with proper headers
- [x] Create function `fetch_sports_list()`
  - [x] GET /v4/sports endpoint
  - [x] Return list of active sports
- [x] Create function `fetch_events(sport_key)`
  - [x] GET /v4/sports/{sport}/events endpoint
  - [x] Return list of upcoming events
- [x] Create function `fetch_odds(sport_key, markets)`
  - [x] GET /v4/sports/{sport}/odds endpoint
  - [x] Use bookmakers parameter (not regions)
  - [x] Return list of events with odds
- [x] Create function `fetch_scores(sport_key)`
  - [x] GET /v4/sports/{sport}/scores endpoint
  - [x] Return list of completed/live games with scores
- [x] Add error handling and logging for all API calls

**Manual Testing 2.1:**
- [x] Test each function individually in Python shell
- [x] Verify API key works
- [x] Verify response structure matches expectations
- [x] Test error handling (invalid sport_key, network error)

---

### 2.2 Data Import - Games & Markets [COMPLETED]

- [x] Create `services/data_import.py` module
- [x] Create function `import_games_for_sport(sport_key)`
  - [x] Fetch events from API
  - [x] For each event:
    - [x] Check if game exists by external_id
    - [x] Create or update BetfakeGame record
    - [x] Convert commence_time string to datetime
    - [x] Set status to Scheduled
  - [x] Return count of imported/updated games
- [x] Create function `import_odds_for_sport(sport_key, markets)`
  - [x] Fetch odds from API for bookmakers: `draftkings,fanduel`
  - [x] For each event in response:
    - [x] Get or create corresponding BetfakeGame
    - [x] For each bookmaker (processed in order: draftkings, then fanduel):
      - [x] For each market:
        - [x] Check if active market exists for this game/type/bookmaker
        - [x] If odds changed: mark old market inactive, create new market
        - [x] Create BetfakeOutcome records for each outcome
        - [x] Store odds (American integers), point_value (if applicable)
  - [x] Return count of markets/outcomes created
- [x] Create function `import_futures(sport_key)`
  - [x] Fetch odds for futures sport (e.g., basketball_nba_championship_winner)
  - [x] Create BetfakeGame with null home/away teams
  - [x] Create BetfakeMarket with type=outrights
  - [x] Create BetfakeOutcome for each team/participant
  - [x] Return count of futures imported
- [x] Add logging for import operations

**Manual Testing 2.2:**
- [x] Run import_games_for_sport('basketball_nba')
- [x] Verify games appear in database
- [x] Run import_odds_for_sport('basketball_nba', 'h2h,spreads,totals')
- [x] Verify markets and outcomes in database
- [x] Check that outcomes link to correct games
- [x] Run import_futures('basketball_nba_championship_winner')
- [x] Verify futures market created with 30 outcomes
- [x] Run import again, verify no duplicates created

---

### 2.3 Management Command for Imports [COMPLETED]

- [x] Create Flask CLI command `flask betfake sync`
  - [x] Add command decorator in routes.py or commands.py
  - [x] Sync NBA: games, odds (h2h,spreads,totals), futures
  - [x] Sync NFL: games, odds (h2h,spreads,totals)
  - [x] Sync EPL: games, odds (h2h only - soccer is h2h only)
  - [x] Print summary of imported records
  - [x] Add `--sport` flag to sync specific sport only
- [x] Test command runs successfully
- [x] Document command in README or PLAN

**Manual Testing 2.3:**
- [x] Run `flask betfake sync`
- [x] Verify all sports imported
- [x] Check database has games and odds
- [x] Run again, verify idempotency (no duplicates)
- [x] Run `flask betfake sync --sport nba`
- [x] Verify only NBA data refreshed

---

### 2.4 Admin Manual Sync UI [COMPLETED]

- [x] Create `GET /admin/sync` route (restricted to admins)
  - [x] Display sync status and "Trigger Sync" button
- [x] Implement `POST /admin/sync/trigger`
  - [x] Call the sync logic (import games, odds, futures)
  - [x] Flash success message with summary
- [x] Create `betfake/admin_sync.html` template
- [x] Register this page in the main app Admin menu

**Manual Testing 2.4:**
- [x] Login as admin
- [x] Navigate to BetFake Admin Sync page
- [x] Click "Trigger Sync"
- [x] Verify data is imported into database

---

### 2.5 Browse Games UI [COMPLETED]

- [x] Implement `GET /sports/<sport_key>` route
  - [x] Query active games for sport (status=Scheduled, commence_time > now)
  - [x] For each game, select the "Best Available" market of each type:
    - [x] Priority 1: DraftKings (Primary)
    - [x] Priority 2: FanDuel (Fallback)
  - [x] Group outcomes by game and market type
  - [x] Order games by commence_time ASC
  - [x] Pass to template
- [x] Create `betfake/sports.html` template
  - [x] Page header with sport name
  - [x] Navigation back to dashboard
  - [x] Links to other sports (NBA, NFL, EPL)
  - [x] List of upcoming games
    - [x] Display game matchup (Team1 vs Team2)
    - [x] Display date/time in user's timezone
    - [x] Display "Betting closed" if game started
    - [x] For each bettable game, show odds buttons:
      - [x] Moneyline (h2h) outcomes with odds
      - [x] Spread outcomes with point value and odds (if available)
      - [x] Totals outcomes with point value and odds (if available)
    - [x] Each outcome button shows: outcome name, odds, point (if applicable)
    - [x] Clicking outcome button goes to bet placement page
  - [x] Empty state if no upcoming games
  - [x] Use `bf-` CSS prefix

**Manual Testing 2.5:**
- [x] Navigate to /betfake/sports/basketball_nba
- [x] Verify upcoming games display
- [x] Verify odds display correctly (formatted as +150, -110)
- [x] Verify spreads show point value (-7.5, +7.5)
- [x] Verify totals show point value (Over 225.5, Under 225.5)
- [x] Verify games past commence_time show "Betting closed"
- [x] Test on mobile viewport (odds readable, buttons tappable)

---

## Phase 3: Bet Placement [COMPLETED]

### 3.1 Bet Placement UI [COMPLETED]

- [x] Create `GET /bet/<int:outcome_id>` route
  - [x] Get outcome by ID
  - [x] Get associated market and game
  - [x] Verify game is bettable (commence_time in future)
  - [x] Get user's accounts
  - [x] Pass all data to template
- [x] Create `betfake/bet.html` template
  - [x] Page header "Place Bet"
  - [x] Display game information
    - [x] Matchup or futures title
    - [x] Game date/time
  - [x] Display bet details
    - [x] Outcome name (e.g., "Lakers", "Over 225.5")
    - [x] Odds (formatted)
    - [x] Point value if applicable
  - [x] Bet placement form
    - [x] Account selector dropdown
    - [x] Wager amount input (type=number, step=0.01, min=0.01)
    - [x] Display current account balance
    - [x] Calculate and display "To Win" amount (live update with JS)
    - [x] Calculate and display "Potential Return" (wager + to_win)
    - [x] "Place Bet" submit button
    - [x] "Cancel" button back to sports page
  - [x] Validation messages area
  - [x] Use `bf-` CSS prefix

**Manual Testing 3.1:**
- [x] Click odds button on sports page
- [x] Bet page loads with correct game and outcome
- [x] Account dropdown shows user's accounts with balances
- [x] Enter wager amount, verify "To Win" calculates correctly
- [x] Test with positive odds (+150): $10 bet should show $15 to win
- [x] Test with negative odds (-110): $11 bet should show $10 to win
- [x] Test on mobile (form easy to use)

---

### 3.2 Bet Placement Backend [COMPLETED]

- [x] Implement `POST /bet/<int:outcome_id>/place` route
  - [x] Get outcome and verify it's active
  - [x] Get market and verify it's active
  - [x] Get game and verify it's bettable (commence_time > now)
  - [x] Validate wager amount:
    - [x] Not empty, > 0
    - [x] Max 2 decimal places
    - [x] Does not exceed account balance
  - [x] Get selected account and verify ownership
  - [x] Calculate potential payout
  - [x] Begin database transaction:
    - [x] Create BetfakeBet record
      - [x] Set outcome_id, account_id, user_id
      - [x] Set wager_amount
      - [x] Snapshot: odds_at_time, line_at_time, outcome_name_at_time
      - [x] Set potential_payout
      - [x] Set status=Pending
    - [x] Deduct wager from account balance
    - [x] Create BetfakeTransaction record (type=Wager, amount=-wager)
    - [x] Commit transaction
  - [x] Flash success message "Bet placed successfully"
  - [x] Redirect to dashboard or bet details page
- [x] Add error handling
  - [x] Insufficient balance: flash error, redirect back
  - [x] Invalid wager: flash error, redirect back
  - [x] Game already started: flash error, redirect back
  - [x] Market/outcome inactive: flash error, redirect back

**Manual Testing 3.2:**
- [x] Place valid bet, verify bet record created
- [x] Verify balance deducted correctly
- [x] Verify transaction record created
- [x] Verify bet shows on dashboard pending bets
- [x] Test insufficient balance error
- [x] Test betting after game started error
- [x] Test betting on inactive market error
- [x] Test decimal precision (bet $10.99, verify works)
- [x] Test over-balance bet ($1000 on $100 account, verify rejected)

---

### 3.3 Bet History Page [COMPLETED]

- [x] Implement `GET /history` route
  - [x] Query user's bets (all statuses)
  - [x] Join with outcomes, markets, games for display data
  - [x] Order by placed_at DESC
  - [x] Paginate if needed (20 per page)
  - [x] Pass to template
- [x] Create `betfake/history.html` template
  - [x] Page header "Bet History"
  - [x] Navigation back to dashboard
  - [x] Table/list of bets
    - [x] Game/event name
    - [x] Outcome bet on
    - [x] Wager amount
    - [x] Odds at time
    - [x] Status (Pending/Won/Lost/Push) with color coding
    - [x] Payout amount (for settled bets)
    - [x] Date placed
  - [x] Summary stats
    - [x] Total bets placed
    - [x] Wins / Losses / Pushes / Pending
    - [x] Total wagered
    - [x] Total won/lost
  - [x] Empty state: "No bets yet"
  - [x] Use `bf-` CSS prefix

**Manual Testing 3.3:**
- [x] Navigate to /betfake/history
- [x] Verify all placed bets appear
- [x] Verify bet details are correct
- [x] Verify pending bets show "Pending"
- [x] Test with no bets (empty state)

---

### 3.4 Transaction Log Page [COMPLETED]

- [x] Implement `GET /transactions/<int:account_id>` route
  - [x] Query all transactions for the specific account
  - [x] Join with bets for detailed context
  - [x] Order by created_at DESC
  - [x] Pass to template
- [x] Create `betfake/transactions.html` template
  - [x] Display account name and current balance
  - [x] List of transactions:
    - [x] Type (Wager, Payout, Creation)
    - [x] Amount (+/-)
    - [x] Date
    - [x] Related bet details (if any)
  - [x] Link back to dashboard
  - [x] Use `bf-` CSS prefix

**Manual Testing 3.4:**
- [x] Navigate to transactions page for an account
- [x] Verify account creation transaction exists ($100)
- [x] Place a bet, verify wager transaction appears
- [x] Verify amounts and types are correct

---

## Phase 4: Bet Settlement [COMPLETED]

### 4.1 Score Import [COMPLETED]

- [x] Create function `import_scores_for_sport(sport_key)` in data_import.py
  - [x] Fetch scores from API
  - [x] For each event with completed=true:
    - [x] Find BetfakeGame by external_id
    - [x] Update status=Completed
    - [x] Update home_score and away_score (convert from string to int)
    - [x] Update last_update timestamp
  - [x] Return count of games updated

**Manual Testing 4.1:**
- [x] Run import_scores_for_sport('basketball_nba')
- [x] Verify completed games have scores in database
- [x] Verify scores are integers not strings
- [x] Run again, verify idempotency

---

### 4.2 Bet Grading Logic [COMPLETED]

- [x] Create `services/bet_grader.py` module
- [x] Create function `grade_h2h_bet(bet, game)`
  - [x] For 2-outcome sports (NBA, NFL):
    - [x] Determine winner based on scores
    - [x] Return Won if bet outcome matches winner
    - [x] Return Lost otherwise
  - [x] For 3-outcome sports (EPL):
    - [x] Check if outcome is home/away/draw
    - [x] Compare scores to determine result
    - [x] Return Won/Lost
- [x] Create function `grade_spread_bet(bet, game)`
  - [x] Get line_at_time from bet
  - [x] Calculate point differential (home_score - away_score)
  - [x] Determine if bet outcome covers spread
  - [x] Return Won/Lost/Push
- [x] Create function `grade_total_bet(bet, game)`
  - [x] Get line_at_time from bet
  - [x] Calculate total score (home_score + away_score)
  - [x] Determine if bet outcome (Over/Under) is correct
  - [x] Return Won/Lost/Push
- [x] Create function `grade_bet(bet)` - main grader
  - [x] Get bet's outcome, market, and game
  - [x] Verify game is completed
  - [x] Call appropriate grading function based on market type
  - [x] Return status (Won/Lost/Push)

**Manual Testing 4.2:**
- [x] Test grade_h2h_bet with sample data (home win, away win)
- [x] Test grade_spread_bet with sample data (cover, not cover, push)
- [x] Test grade_total_bet with sample data (over, under, push)
- [x] Test with EPL draws
- [x] Test edge cases (exact spread match = push)

---

### 4.3 Bet Settlement Process [COMPLETED]

- [x] Create function `settle_pending_bets(game_id)` in bet_grader.py
  - [x] Query all Pending bets for this game (or all games if None)
  - [x] For each bet:
    - [x] Call grade_bet(bet) to determine status
    - [x] Begin transaction:
      - [x] Update bet status (Won/Lost/Push)
      - [x] Set settled_at timestamp
      - [x] If Won:
        - [x] Add potential_payout to account balance
        - [x] Create transaction (type=Payout, amount=+payout)
      - [x] If Push:
        - [x] Refund wager_amount to account balance
        - [x] Create transaction (type=Payout, amount=+wager)
      - [x] If Lost: no payout, no transaction
      - [x] Commit transaction
  - [x] Return count of settled bets
- [x] Create Flask CLI command `flask betfake settle`
  - [x] Get all completed games with pending bets
  - [x] For each game, call settle_pending_bets
  - [x] Print summary
  - [x] Add `--game-id` flag to settle specific game

**Manual Testing 4.3:**
- [x] Place bets on a game
- [x] Manually set game to completed with scores
- [x] Run `flask betfake settle --game-id <id>`
- [x] Verify bet status updated (Won/Lost/Push)
- [x] Verify balance updated for won bets
- [x] Verify refund for push bets
- [x] Verify transaction records created
- [x] Run settle again, verify no double-payout (already settled)

---

### 4.4 Auto-Settlement Integration [COMPLETED]

- [x] Update `flask betfake sync` command
  - [x] After importing scores, call settle on newly completed games
  - [x] Print settlement summary
- [x] Add settlement to data import workflow
  - [x] In import_scores_for_sport, track games that just completed
  - [x] Return list of game IDs to settle
  - [x] Settle those games automatically

**Manual Testing 4.4:**
- [x] Place bets on NBA game
- [x] Wait for game to complete (or mock it)
- [x] Run `flask betfake sync --sport nba`
- [x] Verify scores imported and bets settled in one command
- [x] Verify dashboard shows settled bets with correct status

---

## Phase 5: Futures & Polishing [COMPLETED]

### 5.1 Futures Page [COMPLETED]

- [x] Implement `GET /futures` route
  - [x] Query all games with type=outrights markets
  - [x] Group by sport_key
  - [x] Get active outcomes for each futures market
  - [x] Order outcomes by odds (favorites first)
  - [x] Pass to template
- [x] Create `betfake/futures.html` template
  - [x] Page header "Futures Markets"
  - [x] Navigation back to dashboard
  - [x] Group markets by sport
    - [x] NBA Championship Winner
    - [x] (Other futures as available)
  - [x] For each market:
    - [x] Display market label and end date
    - [x] List all outcomes with odds
    - [x] Make each outcome clickable to bet page
    - [x] Format odds clearly
  - [x] Use `bf-` CSS prefix
  - [x] Mobile-friendly layout

**Manual Testing 5.1:**
- [x] Navigate to /betfake/futures
- [x] Verify NBA Championship market appears
- [x] Verify all 30 teams listed with odds
- [x] Verify odds formatted correctly
- [x] Click outcome, verify bet page loads
- [x] Place futures bet, verify works same as regular bet

---

### 5.2 Dashboard Enhancements [COMPLETED]

- [x] Update dashboard to show recent activity
  - [x] Add "Recent Bets" section (last 5 bets)
  - [x] Add quick links to sports and futures
  - [x] Add win/loss/push counts
- [x] Add account management
  - [x] Display all accounts with balances
  - [x] Highlight default account
  - [x] Show which account has pending bets
- [x] Add visual polish
  - [x] Color-code Won (green), Lost (red), Push (gray)
  - [x] Format currency consistently ($X.XX)
  - [x] Make pending bets prominent
- [x] Add empty states
  - [x] No accounts: prompt to create first account
  - [x] No bets: prompt to browse games

**Manual Testing 5.2:**
- [x] Dashboard shows recent bets
- [x] Colors applied correctly
- [x] Account balances display accurately
- [x] Empty states display when appropriate
- [x] Mobile layout works well

---

### 5.3 Mobile Responsiveness [COMPLETED]

- [x] Review all pages on mobile viewport (375px)
- [x] Sports page mobile optimization
  - [x] Odds buttons stack vertically if needed
  - [x] Touch targets minimum 44px
  - [x] Game cards easy to read
- [x] Bet placement page mobile optimization
  - [x] Form inputs full width on mobile
  - [x] Number keyboard for wager input
  - [x] Calculations visible above fold
- [x] Dashboard mobile optimization
  - [x] Accounts displayed as cards
  - [x] Pending bets scrollable
- [x] History page mobile optimization
  - [x] Table converts to cards
  - [x] Key info visible in compact view
- [x] Add viewport meta tag to base template if not present

**Manual Testing 5.3:**
- [x] Test all pages at 375px width
- [x] Verify no horizontal scrolling
- [x] Verify all buttons are tappable (44px min)
- [x] Verify text is readable (16px min)
- [x] Test on actual mobile device (iOS/Android)
- [x] Test in Chrome mobile emulator

---

### 5.4 Error Handling & Edge Cases [COMPLETED]

- [x] Add 404 page for invalid game/outcome/bet IDs
- [x] Add authorization checks
  - [x] Users can only see their own accounts
  - [x] Users can only see their own bets
  - [x] Return 404 for unauthorized access (not 403)
- [x] Handle API errors gracefully
  - [x] Log API failures
  - [x] Show user-friendly message
  - [x] Don't crash on missing data
- [x] Handle timezone edge cases
  - [x] Games starting soon (within 5 min)
  - [x] Games in different timezone from user
- [x] Handle concurrent betting
  - [x] Use database transactions for balance updates
  - [x] Prevent race conditions
- [x] Add CSRF protection (should be automatic with Flask-WTF)

**Manual Testing 5.4:**
- [x] Try to access another user's account ID
- [x] Try to bet with another user's account
- [x] Try to place bet with insufficient balance (concurrent)
- [x] Simulate API failure, verify app doesn't crash
- [x] Test betting window edge cases

---

### 5.5 Final Integration Testing [COMPLETED]

- [x] Complete user flow: Create account
  - [x] Login as new user
  - [x] Verify default account created
  - [x] Create second account
  - [x] Verify both accounts on dashboard
- [x] Complete user flow: Place bet
  - [x] Browse NBA games
  - [x] Select a game and outcome
  - [x] Enter wager amount
  - [x] Place bet
  - [x] Verify bet appears on dashboard
  - [x] Verify balance deducted
  - [x] Verify transaction created
- [x] Complete user flow: Bet settlement (winning)
  - [x] Place bet on completed game (or mock completion)
  - [x] Run settlement
  - [x] Verify bet marked Won
  - [x] Verify payout added to balance
  - [x] Verify transaction created
- [x] Complete user flow: Bet settlement (losing)
  - [x] Place bet that will lose
  - [x] Run settlement
  - [x] Verify bet marked Lost
  - [x] Verify no payout
  - [x] Balance remains unchanged
- [x] Complete user flow: Push
  - [x] Place spread bet that will push
  - [x] Run settlement
  - [x] Verify bet marked Push
  - [x] Verify wager refunded
- [x] Complete user flow: Futures bet
  - [x] Navigate to futures page
  - [x] Select NBA Championship winner
  - [x] Place bet
  - [x] Verify bet created correctly
- [x] Test bet history
  - [x] Verify all bet types appear
  - [x] Verify statuses correct
  - [x] Verify stats calculated correctly
- [x] Test multiple accounts
  - [x] Place bets from different accounts
  - [x] Verify balances tracked separately
  - [x] Verify bets associated with correct account

---

## Phase 6: Scheduled Tasks & Automation (Optional for V1)

### 6.1 Automated Sync Schedule

- [ ] Create cron job or scheduled task
  - [ ] Run `flask betfake sync` every 30 minutes
  - [ ] Run during peak betting hours (more frequent)
  - [ ] Log results
- [ ] Add monitoring/alerts
  - [ ] Alert if sync fails
  - [ ] Alert if settlement fails

**Note:** This can be manual for V1, automated later.

---

## Completion Checklist

Before considering Phase 1-5 complete:

- [x] All database models created and migrated
- [x] All routes return appropriate responses
- [x] All templates render correctly
- [x] CSRF protection enabled
- [x] User authorization checks in place
- [x] All forms validate input
- [ ] Mobile testing completed on real device
- [ ] No console errors in browser
- [x] All Phase 1-5 manual tests passed
- [x] Code follows existing project conventions
- [x] CSS uses `bf-` prefix throughout
- [x] Can complete full user flow: create account → place bet → settle bet
- [x] Bet grading works for all market types (h2h, spreads, totals)
- [x] Futures betting works
- [x] Multiple accounts work correctly

---

## Future Enhancements (Post-V1)

These are documented in PRD but not part of initial implementation:

- [ ] Leaderboards
- [ ] Live betting
- [ ] Parlays
- [ ] Daily bonus
- [ ] Bet slip preview
- [ ] Stats widgets
- [ ] Balance graphs
- [ ] Filters and favorites
- [ ] Odds format preference
- [ ] Account creation limits
