# Kids Words – Implementation Plan

This plan follows the PRD and breaks the work into smaller, testable chunks. **Vanilla JS only.** All CSS classes use the **kw-** prefix to avoid collisions with other projects.

---

## Relevant Files

- `app/projects/kids_words/routes.py` – Blueprint, index route, data API routes
- `app/projects/kids_words/templates/kids_words/index.html` – Main template (setup + game UI)
- `app/projects/kids_words/static/css/kids_words.css` – All styles (kw- prefix)
- `app/projects/kids_words/static/js/kids_words.js` – Game logic (vanilla JS)
- `app/projects/kids_words/data/grade2_words.json` – Grade 2 answer set
- `app/projects/kids_words/data/grade4_words.json` – Grade 4 answer set
- `app/projects/kids_words/data/wordle_guesses.txt` – Valid guess list

---

## Phase 1: Foundations & Data Loading

### 1.1 Blueprint & Static Setup
- [x] Add `static_folder="static"` to the kids_words blueprint in `routes.py`
- [x] Create `app/projects/kids_words/static/` directory
- [x] Create `app/projects/kids_words/static/css/kids_words.css` with base `kw-wrapper` styles
- [x] Create `app/projects/kids_words/static/js/kids_words.js` (empty placeholder)
- [x] Link CSS and JS in `templates/kids_words/index.html` via `url_for('kids_words.static', ...)`

**Manual Testing 1.1:**
- [x] Visit `/kids-words` and verify no 404s for CSS/JS; `kw-wrapper` is visible

### 1.2 Data API Routes
- [x] Add `GET /kids-words/api/words/grade2` – returns `data/grade2_words.json`
- [x] Add `GET /kids-words/api/words/grade4` – returns `data/grade4_words.json`
- [x] Add `GET /kids-words/api/words/guesses` – returns `data/wordle_guesses.txt` as JSON array (one word per line)
- [x] Use `send_from_directory` or read files from `data/` relative to project root

**Manual Testing 1.2:**
- [x] Fetch each API URL and verify valid JSON / array format
- [x] Confirm grade2/grade4 return objects with `"yes"`/`"no"` values
- [x] Confirm guesses returns an array of 5-letter strings

### 1.3 Client-Side Data Loading (Vanilla JS)
- [x] On page load, fetch all three data sources via `fetch()`
- [x] Build `validGuesses` = union of JSON keys + guesses array
- [x] Build `answerSets`: `{ grade2: [...], grade4: [...], adult: [...] }` from JSON files
- [x] Store in module-level variables for use by game logic
- [x] Disable Start button (or show loading state) until all three fetches succeed

**Manual Testing 1.3:**
- [x] Open console, verify no fetch errors; log `validGuesses.length` and `answerSets` keys

---

## Phase 2: Setup Screen

### 2.1 Setup UI (Difficulty & Word Count)
- [x] Add `kw-setup` section to template (visible by default)
- [x] Add three difficulty buttons: Grade 2, Grade 4, Adult (kw-difficulty-btn, kw-selected)
- [x] Add word-count selector: 1–8 (buttons or slider) with `kw-word-count` classes
- [x] Add "Start Game" button (`kw-start-btn`)
- [x] Style with kw- prefix; layout for mobile (stacked) and desktop

**Manual Testing 2.1:**
- [x] See setup screen on load; select difficulty and word count; Start disabled until both chosen

### 2.2 Start Game Logic
- [x] On Start click: validate difficulty + word count are selected
- [x] Select N random answers from the correct answer set (no duplicates)
- [x] Compute max guesses = N + 5
- [x] Hide `kw-setup`, show `kw-game` section
- [x] Initialize game state (answers, guesses used, solved words)

**Manual Testing 2.2:**
- [x] Start game; setup hides, game area appears
- [x] Verify N word slots shown and max guesses = N + 5

---

## Phase 3: Game Board & Guess Logic

### 3.1 Game Grid Layout
- [ ] Add `kw-game` section with `kw-board` container
- [ ] Render N word grids (each 5 columns × (N+5) rows; row count = max guesses)
- [ ] Each grid: `kw-word-grid`, cells: `kw-cell`, `kw-cell-correct`, `kw-cell-present`, `kw-cell-absent`
- [ ] Single shared input row: `kw-input-row` with 5 `kw-input-cell` elements
- [ ] Display all letters on screen in uppercase (input cells, grid cells, revealed answers); word lists stay lowercase for validation
- [ ] Responsive: desktop grid (e.g. 2×4 for 8 words); mobile stacked, max 2 per row

**Manual Testing 3.1:**
- [ ] Start 4-word game; see 4 grids in 2×2; input row at top or bottom

### 3.2 Guess Input (Keyboard)
- [ ] Focus on input row; capture keydown for A–Z, Backspace, Enter
- [ ] Type letters: fill cells left-to-right; Backspace: clear last
- [ ] Enter: submit guess if 5 letters
- [ ] Normalize guess to lowercase before validation
- [ ] On submit: check if guess is in `validGuesses`; if not, show "Not in word list" (e.g. `kw-toast`)

**Manual Testing 3.2:**
- [ ] Type a word; press Enter; invalid guess shows message
- [ ] Valid guess advances game

### 3.3 Guess Evaluation
- [ ] For each target word, compute feedback: correct (green), present (yellow), absent (gray)
- [ ] Standard Wordle rules: green = right letter right spot; yellow = letter in word, wrong spot; gray = not in word
- [ ] Handle duplicate letters per Wordle rules: letter counts matter (e.g. if answer has one P, only one P can be green/yellow)
- [ ] Apply feedback to each word grid; fill the current row for each unsolved word
- [ ] Mark words solved when feedback is all green

**Manual Testing 3.3:**
- [ ] Submit a guess; each grid updates with correct colors
- [ ] Correct guess for a word marks that word solved

### 3.4 Win / Lose Logic
- [ ] Win: all N words solved → show `kw-win` message
- [ ] Lose: guesses exhausted with unsolved words → show `kw-lose` message, reveal all answers
- [ ] Add "New Game" button; returns to setup screen

**Manual Testing 3.4:**
- [ ] Solve all words → win message
- [ ] Exhaust guesses → lose message + revealed answers
- [ ] New Game → back to setup

---

## Phase 4: Virtual Keyboard

### 4.1 Keyboard UI
- [ ] Add `kw-keyboard` below game board
- [ ] Rows: QWERTY... , ASDF... , ZXCV... + Enter/Backspace
- [ ] Each key: `kw-key`; layout with flexbox/grid
- [ ] Mobile-friendly sizing

**Manual Testing 4.1:**
- [ ] Keyboard visible; keys clickable

### 4.2 Keyboard Input & Feedback
- [ ] Click key: type letter or Backspace/Enter (same as physical keyboard)
- [ ] After each guess: update key colors (best status across all words)
- [ ] Green > yellow > gray; disabled keys stay gray

**Manual Testing 4.2:**
- [ ] Use virtual keyboard to type and submit
- [ ] Keys turn green/yellow/gray as guesses are made

---

## Phase 5: localStorage Persistence

### 5.1 Save Game State
- [ ] On each guess: save `{ difficulty, wordCount, answers, guesses, solved }` to localStorage
- [ ] Use a stable key, e.g. `kids_words_game`
- [ ] On page load: if saved game exists, restore game view directly (as if mid-game refresh)

**Manual Testing 5.1:**
- [ ] Start game, make a guess, refresh → game restores with correct state

### 5.2 Clear on New Game
- [ ] When user starts new game from setup: clear `kids_words_game` from localStorage

**Manual Testing 5.2:**
- [ ] New Game clears saved state; no resume option on next load

---

## Phase 6: Stats

### 6.1 Stats Storage
- [ ] Track: games played, games won
- [ ] Store in localStorage under `kids_words_stats`: `{ played, won }`
- [ ] Update on game end (win or lose)

**Manual Testing 6.1:**
- [ ] Win/lose a few games; check localStorage for stats

### 6.2 Stats Display
- [ ] Add `kw-stats` section (e.g. on setup screen or small footer)
- [ ] Show "X / Y" (wins / played) and win rate %
- [ ] Style with kw- prefix

**Manual Testing 6.2:**
- [ ] Stats visible and accurate after multiple games

---

## Phase 7: Polish & Audit

### 7.1 CSS Audit
- [ ] Confirm every class in `kids_words.css` uses `kw-` prefix
- [ ] No global selectors (e.g. `button`, `input`) without kw- scope
- [ ] Responsive: 375px mobile, 768px+ desktop

**Manual Testing 7.1:**
- [ ] Resize to mobile; layout stacks, 2 words per row max
- [ ] No style bleed from other projects

### 7.2 Accessibility & UX
- [ ] Input row / cells focusable; tab order sane
- [ ] "Not in word list" visible and dismissible
- [ ] Win/lose messages readable

**Manual Testing 7.2:**
- [ ] Tab through game; screen reader or keyboard-only usage works

### 7.3 Data Path Audit
- [ ] Verify all data paths resolve correctly in dev and production
- [ ] API routes 404 gracefully if files missing

---

## Summary

| Phase | Focus |
|-------|-------|
| 1 | Blueprint, static, data API, client data load |
| 2 | Setup UI, difficulty, word count, start game |
| 3 | Game board, guess input, evaluation, win/lose |
| 4 | Virtual keyboard with colored feedback |
| 5 | localStorage game state |
| 6 | Stats tracking and display |
| 7 | CSS audit, a11y, polish |
