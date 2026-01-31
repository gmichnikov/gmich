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

## Phase 3: Bet Placement [IN PROGRESS]

### 3.1 Bet Placement UI

- [ ] Create `GET /bet/<int:outcome_id>` route
  - [ ] Get outcome by ID
  - [ ] Get associated market and game
  - [ ] Verify game is bettable (commence_time in future)
  - [ ] Get user's accounts
  - [ ] Pass all data to template
- [ ] Create `betfake/bet.html` template
  - [ ] Page header "Place Bet"
  - [ ] Display game information
    - [ ] Matchup or futures title
    - [ ] Game date/time
  - [ ] Display bet details
    - [ ] Outcome name (e.g., "Lakers", "Over 225.5")
    - [ ] Odds (formatted)
    - [ ] Point value if applicable
  - [ ] Bet placement form
    - [ ] Account selector dropdown
    - [ ] Wager amount input (type=number, step=0.01, min=0.01)
    - [ ] Display current account balance
    - [ ] Calculate and display "To Win" amount (live update with JS)
    - [ ] Calculate and display "Potential Return" (wager + to_win)
    - [ ] "Place Bet" submit button
    - [ ] "Cancel" button back to sports page
  - [ ] Validation messages area
  - [ ] Use `bf-` CSS prefix

**Manual Testing 3.1:**
- [ ] Click odds button on sports page
- [ ] Bet page loads with correct game and outcome
- [ ] Account dropdown shows user's accounts with balances
- [ ] Enter wager amount, verify "To Win" calculates correctly
- [ ] Test with positive odds (+150): $10 bet should show $15 to win
- [ ] Test with negative odds (-110): $11 bet should show $10 to win
- [ ] Test on mobile (form easy to use)

---

### 3.2 Bet Placement Backend

- [ ] Implement `POST /bet/<int:outcome_id>/place` route
  - [ ] Get outcome and verify it's active
  - [ ] Get market and verify it's active
  - [ ] Get game and verify it's bettable (commence_time > now)
  - [ ] Validate wager amount:
    - [ ] Not empty, > 0
    - [ ] Max 2 decimal places
    - [ ] Does not exceed account balance
  - [ ] Get selected account and verify ownership
  - [ ] Calculate potential payout
  - [ ] Begin database transaction:
    - [ ] Create BetfakeBet record
      - [ ] Set outcome_id, account_id, user_id
      - [ ] Set wager_amount
      - [ ] Snapshot: odds_at_time, line_at_time, outcome_name_at_time
      - [ ] Set potential_payout
      - [ ] Set status=Pending
    - [ ] Deduct wager from account balance
    - [ ] Create BetfakeTransaction record (type=Wager, amount=-wager)
    - [ ] Commit transaction
  - [ ] Flash success message "Bet placed successfully"
  - [ ] Redirect to dashboard or bet details page
- [ ] Add error handling
  - [ ] Insufficient balance: flash error, redirect back
  - [ ] Invalid wager: flash error, redirect back
  - [ ] Game already started: flash error, redirect back
  - [ ] Market/outcome inactive: flash error, redirect back

**Manual Testing 3.2:**
- [ ] Place valid bet, verify bet record created
- [ ] Verify balance deducted correctly
- [ ] Verify transaction record created
- [ ] Verify bet shows on dashboard pending bets
- [ ] Test insufficient balance error
- [ ] Test betting after game started error
- [ ] Test betting on inactive market error
- [ ] Test decimal precision (bet $10.99, verify works)
- [ ] Test over-balance bet ($1000 on $100 account, verify rejected)

---

### 3.3 Bet History Page

- [ ] Implement `GET /history` route
  - [ ] Query user's bets (all statuses)
  - [ ] Join with outcomes, markets, games for display data
  - [ ] Order by placed_at DESC
  - [ ] Paginate if needed (20 per page)
  - [ ] Pass to template
- [ ] Create `betfake/history.html` template
  - [ ] Page header "Bet History"
  - [ ] Navigation back to dashboard
  - [ ] Table/list of bets
    - [ ] Game/event name
    - [ ] Outcome bet on
    - [ ] Wager amount
    - [ ] Odds at time
    - [ ] Status (Pending/Won/Lost/Push) with color coding
    - [ ] Payout amount (for settled bets)
    - [ ] Date placed
  - [ ] Summary stats
    - [ ] Total bets placed
    - [ ] Wins / Losses / Pushes / Pending
    - [ ] Total wagered
    - [ ] Total won/lost
  - [ ] Empty state: "No bets yet"
  - [ ] Use `bf-` CSS prefix

**Manual Testing 3.3:**
- [ ] Navigate to /betfake/history
- [ ] Verify all placed bets appear
- [ ] Verify bet details are correct
- [ ] Verify pending bets show "Pending"
- [ ] Test with no bets (empty state)

---

### 3.4 Transaction Log Page

- [ ] Implement `GET /transactions/<int:account_id>` route
  - [ ] Query all transactions for the specific account
  - [ ] Join with bets for detailed context
  - [ ] Order by created_at DESC
  - [ ] Pass to template
- [ ] Create `betfake/transactions.html` template
  - [ ] Display account name and current balance
  - [ ] List of transactions:
    - [ ] Type (Wager, Payout, Creation)
    - [ ] Amount (+/-)
    - [ ] Date
    - [ ] Related bet details (if any)
  - [ ] Link back to dashboard
  - [ ] Use `bf-` CSS prefix

**Manual Testing 3.4:**
- [ ] Navigate to transactions page for an account
- [ ] Verify account creation transaction exists ($100)
- [ ] Place a bet, verify wager transaction appears
- [ ] Verify amounts and types are correct

---

## Phase 4: Bet Settlement

### 4.1 Score Import

- [ ] Create function `import_scores_for_sport(sport_key)` in data_import.py
  - [ ] Fetch scores from API
  - [ ] For each event with completed=true:
    - [ ] Find BetfakeGame by external_id
    - [ ] Update status=Completed
    - [ ] Update home_score and away_score (convert from string to int)
    - [ ] Update last_update timestamp
  - [ ] Return count of games updated

**Manual Testing 4.1:**
- [ ] Run import_scores_for_sport('basketball_nba')
- [ ] Verify completed games have scores in database
- [ ] Verify scores are integers not strings
- [ ] Run again, verify idempotency

---

### 4.2 Bet Grading Logic

- [ ] Create `services/bet_grader.py` module
- [ ] Create function `grade_h2h_bet(bet, game)`
  - [ ] For 2-outcome sports (NBA, NFL):
    - [ ] Determine winner based on scores
    - [ ] Return Won if bet outcome matches winner
    - [ ] Return Lost otherwise
  - [ ] For 3-outcome sports (EPL):
    - [ ] Check if outcome is home/away/draw
    - [ ] Compare scores to determine result
    - [ ] Return Won/Lost
- [ ] Create function `grade_spread_bet(bet, game)`
  - [ ] Get line_at_time from bet
  - [ ] Calculate point differential (home_score - away_score)
  - [ ] Determine if bet outcome covers spread
  - [ ] Return Won/Lost/Push
- [ ] Create function `grade_total_bet(bet, game)`
  - [ ] Get line_at_time from bet
  - [ ] Calculate total score (home_score + away_score)
  - [ ] Determine if bet outcome (Over/Under) is correct
  - [ ] Return Won/Lost/Push
- [ ] Create function `grade_bet(bet)` - main grader
  - [ ] Get bet's outcome, market, and game
  - [ ] Verify game is completed
  - [ ] Call appropriate grading function based on market type
  - [ ] Return status (Won/Lost/Push)

**Manual Testing 4.2:**
- [ ] Test grade_h2h_bet with sample data (home win, away win)
- [ ] Test grade_spread_bet with sample data (cover, not cover, push)
- [ ] Test grade_total_bet with sample data (over, under, push)
- [ ] Test with EPL draws
- [ ] Test edge cases (exact spread match = push)

---

### 4.3 Bet Settlement Process

- [ ] Create function `settle_game_bets(game_id)` in bet_grader.py
  - [ ] Query all Pending bets for this game
  - [ ] For each bet:
    - [ ] Call grade_bet(bet) to determine status
    - [ ] Begin transaction:
      - [ ] Update bet status (Won/Lost/Push)
      - [ ] Set settled_at timestamp
      - [ ] If Won:
        - [ ] Add potential_payout to account balance
        - [ ] Create transaction (type=Payout, amount=+payout)
      - [ ] If Push:
        - [ ] Refund wager_amount to account balance
        - [ ] Create transaction (type=Payout, amount=+wager)
      - [ ] If Lost: no payout, no transaction
      - [ ] Commit transaction
  - [ ] Return count of settled bets
- [ ] Create Flask CLI command `flask betfake settle`
  - [ ] Get all completed games with pending bets
  - [ ] For each game, call settle_game_bets
  - [ ] Print summary
  - [ ] Add `--game-id` flag to settle specific game

**Manual Testing 4.3:**
- [ ] Place bets on a game
- [ ] Manually set game to completed with scores
- [ ] Run `flask betfake settle --game-id <id>`
- [ ] Verify bet status updated (Won/Lost/Push)
- [ ] Verify balance updated for won bets
- [ ] Verify refund for push bets
- [ ] Verify transaction records created
- [ ] Run settle again, verify no double-payout (already settled)

---

### 4.4 Auto-Settlement Integration

- [ ] Update `flask betfake sync` command
  - [ ] After importing scores, call settle on newly completed games
  - [ ] Print settlement summary
- [ ] Add settlement to data import workflow
  - [ ] In import_scores_for_sport, track games that just completed
  - [ ] Return list of game IDs to settle
  - [ ] Settle those games automatically

**Manual Testing 4.4:**
- [ ] Place bets on NBA game
- [ ] Wait for game to complete (or mock it)
- [ ] Run `flask betfake sync --sport nba`
- [ ] Verify scores imported and bets settled in one command
- [ ] Verify dashboard shows settled bets with correct status

---

## Phase 5: Futures & Polishing

### 5.1 Futures Page

- [ ] Implement `GET /futures` route
  - [ ] Query all games with type=outrights markets
  - [ ] Group by sport_key
  - [ ] Get active outcomes for each futures market
  - [ ] Order outcomes by odds (favorites first)
  - [ ] Pass to template
- [ ] Create `betfake/futures.html` template
  - [ ] Page header "Futures Markets"
  - [ ] Navigation back to dashboard
  - [ ] Group markets by sport
    - [ ] NBA Championship Winner
    - [ ] (Other futures as available)
  - [ ] For each market:
    - [ ] Display market label and end date
    - [ ] List all outcomes with odds
    - [ ] Make each outcome clickable to bet page
    - [ ] Format odds clearly
  - [ ] Use `bf-` CSS prefix
  - [ ] Mobile-friendly layout

**Manual Testing 5.1:**
- [ ] Navigate to /betfake/futures
- [ ] Verify NBA Championship market appears
- [ ] Verify all 30 teams listed with odds
- [ ] Verify odds formatted correctly
- [ ] Click outcome, verify bet page loads
- [ ] Place futures bet, verify works same as regular bet

---

### 5.2 Dashboard Enhancements

- [ ] Update dashboard to show recent activity
  - [ ] Add "Recent Bets" section (last 5 bets)
  - [ ] Add quick links to sports and futures
  - [ ] Add win/loss/push counts
- [ ] Add account management
  - [ ] Display all accounts with balances
  - [ ] Highlight default account
  - [ ] Show which account has pending bets
- [ ] Add visual polish
  - [ ] Color-code Won (green), Lost (red), Push (gray)
  - [ ] Format currency consistently ($X.XX)
  - [ ] Make pending bets prominent
- [ ] Add empty states
  - [ ] No accounts: prompt to create first account
  - [ ] No bets: prompt to browse games

**Manual Testing 5.2:**
- [ ] Dashboard shows recent bets
- [ ] Colors applied correctly
- [ ] Account balances display accurately
- [ ] Empty states display when appropriate
- [ ] Mobile layout works well

---

### 5.3 Mobile Responsiveness

- [ ] Review all pages on mobile viewport (375px)
- [ ] Sports page mobile optimization
  - [ ] Odds buttons stack vertically if needed
  - [ ] Touch targets minimum 44px
  - [ ] Game cards easy to read
- [ ] Bet placement page mobile optimization
  - [ ] Form inputs full width on mobile
  - [ ] Number keyboard for wager input
  - [ ] Calculations visible above fold
- [ ] Dashboard mobile optimization
  - [ ] Accounts displayed as cards
  - [ ] Pending bets scrollable
- [ ] History page mobile optimization
  - [ ] Table converts to cards
  - [ ] Key info visible in compact view
- [ ] Add viewport meta tag to base template if not present

**Manual Testing 5.3:**
- [ ] Test all pages at 375px width
- [ ] Verify no horizontal scrolling
- [ ] Verify all buttons are tappable (44px min)
- [ ] Verify text is readable (16px min)
- [ ] Test on actual mobile device (iOS/Android)
- [ ] Test in Chrome mobile emulator

---

### 5.4 Error Handling & Edge Cases

- [ ] Add 404 page for invalid game/outcome/bet IDs
- [ ] Add authorization checks
  - [ ] Users can only see their own accounts
  - [ ] Users can only see their own bets
  - [ ] Return 404 for unauthorized access (not 403)
- [ ] Handle API errors gracefully
  - [ ] Log API failures
  - [ ] Show user-friendly message
  - [ ] Don't crash on missing data
- [ ] Handle timezone edge cases
  - [ ] Games starting soon (within 5 min)
  - [ ] Games in different timezone from user
- [ ] Handle concurrent betting
  - [ ] Use database transactions for balance updates
  - [ ] Prevent race conditions
- [ ] Add CSRF protection (should be automatic with Flask-WTF)

**Manual Testing 5.4:**
- [ ] Try to access another user's account ID
- [ ] Try to bet with another user's account
- [ ] Try to place bet with insufficient balance (concurrent)
- [ ] Simulate API failure, verify app doesn't crash
- [ ] Test betting window edge cases

---

### 5.5 Final Integration Testing

- [ ] Complete user flow: Create account
  - [ ] Login as new user
  - [ ] Verify default account created
  - [ ] Create second account
  - [ ] Verify both accounts on dashboard
- [ ] Complete user flow: Place bet
  - [ ] Browse NBA games
  - [ ] Select a game and outcome
  - [ ] Enter wager amount
  - [ ] Place bet
  - [ ] Verify bet appears on dashboard
  - [ ] Verify balance deducted
  - [ ] Verify transaction created
- [ ] Complete user flow: Bet settlement (winning)
  - [ ] Place bet on completed game (or mock completion)
  - [ ] Run settlement
  - [ ] Verify bet marked Won
  - [ ] Verify payout added to balance
  - [ ] Verify transaction created
- [ ] Complete user flow: Bet settlement (losing)
  - [ ] Place bet that will lose
  - [ ] Run settlement
  - [ ] Verify bet marked Lost
  - [ ] Verify no payout
  - [ ] Balance remains unchanged
- [ ] Complete user flow: Push
  - [ ] Place spread bet that will push
  - [ ] Run settlement
  - [ ] Verify bet marked Push
  - [ ] Verify wager refunded
- [ ] Complete user flow: Futures bet
  - [ ] Navigate to futures page
  - [ ] Select NBA Championship winner
  - [ ] Place bet
  - [ ] Verify bet created correctly
- [ ] Test bet history
  - [ ] Verify all bet types appear
  - [ ] Verify statuses correct
  - [ ] Verify stats calculated correctly
- [ ] Test multiple accounts
  - [ ] Place bets from different accounts
  - [ ] Verify balances tracked separately
  - [ ] Verify bets associated with correct account

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

- [ ] All database models created and migrated
- [ ] All routes return appropriate responses
- [ ] All templates render correctly
- [ ] CSRF protection enabled
- [ ] User authorization checks in place
- [ ] All forms validate input
- [ ] Mobile testing completed on real device
- [ ] No console errors in browser
- [ ] All Phase 1-5 manual tests passed
- [ ] Code follows existing project conventions
- [ ] CSS uses `bf-` prefix throughout
- [ ] Can complete full user flow: create account → place bet → settle bet
- [ ] Bet grading works for all market types (h2h, spreads, totals)
- [ ] Futures betting works
- [ ] Multiple accounts work correctly

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
