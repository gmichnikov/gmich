# Bowling Scorekeeper — Implementation Plan

Implementation order and checkpoints for Bowling v1.

**References:** All product behavior → [PRD.html](./PRD.html). If code and PRD disagree, update whichever is wrong — don’t let them drift silently.

Run **`flask db migrate`** and **`flask db upgrade`** yourself after Phase 1. Finish each phase’s **Manual checks** before starting the next one.

---

## How to use this document

- **Phases 1–6** are delivery milestones: complete one phase, run its checks, then move on.
- The **Tasks** section at the bottom is the same work broken into checkbox items (ai-dev-tasks style) for day-to-day tracking.
- **PRD §** references map to sections in `PRD.html` (Overview = §01, Screen Flow = §02, … UX Details = §12).

**Build priority:** **Models → scoring engine → API → Home/Setup → Active game UI → sync & lifecycle.** The scoring engine must be solid before UI work — clients never compute scores.

**PRD alignment:** Section **[PRD traceability](#prd-traceability)** maps every PRD section (§01–§12) to phases. If something is in the PRD but not listed there, it was missed — add it.

---

## At a glance: milestones

| Phase | Deliverable | PRD pointer |
| ----- | ----------- | ----------- |
| **1** | SQLAlchemy models, code generation, migration | §03, §10 |
| **2** | Server-side scoring + game-state logic (+ unit tests) | §04, §06, §07 |
| **3** | JSON API: create, read, setup, rolls, clear, complete | §03, §08, §09 |
| **4** | Home + Setup screens, join/share/rejoin | §02, §03, §12 |
| **5** | Active game UI: scorecard, pin input, correction | §05, §06, §07, §12 |
| **6** | Polling sync, lifecycle, completed state, polish | §08, §09, §11, §12 |

**Deferred from this lane:** user accounts, cross-game history, handicaps, rate limiting, admin tools, websockets.

---

## Repo conventions

- SQL tables prefixed **`bowling_*`**; Python classes like **`BowlingGame`**, **`BowlingPlayer`**, **`BowlingRoll`**.
- CSS classes prefixed **`bowling-*`** (scorecard sub-elements too: `bowling-frame-cell`, not bare `scorecard`).
- Blueprint already registered at **`/bowling`**; game URLs **`/bowling/<code>`** (6-digit string).
- Import **all** Bowling models in **`app/__init__.py`** for Flask-Migrate.
- **`log_project_visit('bowling', ...)`** on public **`GET /bowling/`** (already on index route).
- Public project — no **`@login_required`**. POST APIs use CSRF via **`meta[name="csrf-token"]`** + **`X-CSRFToken`** header from `base.html`.
- Share buttons: **`navigator.share()`** with absolute URL when available; copy-to-clipboard fallback.

---

## Likely modules

| File | Role |
| ---- | ---- |
| `models.py` | `BowlingGame`, `BowlingPlayer`, `BowlingRoll` |
| `code.py` | Generate unique 6-digit codes (never reused) |
| `scoring.py` | Frame scores, pending detection, totals from rolls |
| `game_state.py` | Actionable/clearable frame, turn player, setup locks, player-add lock |
| `routes.py` | Page routes + `/api/...` JSON endpoints |
| `static/bowling.css` | Prefixed styles |
| `static/bowling.js` | Client: render, poll, pin input, share, localStorage |
| `templates/bowling/index.html` | Home: create, join, rejoin |
| `templates/bowling/game.html` | Shell for `/bowling/<code>` (Setup / Active / Complete views driven by JS) |

Tests (repo root): **`tests/bowling/test_scoring.py`**, **`tests/bowling/test_game_state.py`**.

---

## Phase 1 — Models & migration

Match PRD §10 logical model; use FKs to `bowling_game.id` internally (expose `code` on reads).

### Schema sketch

| Table | Key columns |
| ----- | ----------- |
| `bowling_game` | `id`, `code` (unique, 6-char), `status` (`setup` \| `active` \| `complete`), `created_at`, `completed_at` |
| `bowling_player` | `id`, `game_id` FK, `name`, `order_index` |
| `bowling_roll` | `id`, `player_id` FK, `frame` (1–10), `roll` (1–3), `pins` (0–10) |

Unique constraint on **`(player_id, frame, roll)`** so last-write-wins is well-defined.

### `code.py`

- Random zero-padded 6-digit string not present in `bowling_game.code`.
- Retry on collision (extremely rare).
- Codes **never reused** — games are permanent (PRD §03, §09 No Expiry).

### Manual checks

1. Run **`flask db migrate`** — read the revision.
2. Run **`flask db upgrade`**.
3. **`flask shell`** — create a game with code, two players, a few rolls; confirm relationships.

---

## Phase 2 — Scoring & game-state logic

Pure Python — no HTTP yet. This is the core; get it right before building UI.

### `scoring.py` (PRD §04)

- Standard 10-pin rules: strike, spare, open, gutter display as `–` in API payload (not stored differently — `pins=0`, client/API shapes display).
- Frames 1–9 strike: display `X` in a **single** roll box (no second box filled).
- Frame 10: 2 vs 3 rolls, third box locked/hidden when open.
- Frame 10 score = sum of rolls taken (no extra bonus beyond earned rolls).
- Pending frames (`…`) when bonus rolls missing; cumulative total stops at last non-pending frame.
- Return per-player: rolls, per-frame scores, frame statuses, totals, display hints (`X`, `/`, `–`).

### `game_state.py` (PRD §05–07)

- **Actionable frame** for input (leading edge).
- **Clearable frame** (in-progress or most recently completed if nothing in progress).
- **Current turn player** (fewest completed frames; tiebreak `order_index`). Advisory only — never blocks API writes to other players.
- **Player add lock:** any roll in anyone’s frame 2 (first roll of frame 2, not “frame 2 complete”).
- **Setup locks:** no rename/reorder/remove after `active`; remove only during `setup`.
- **Late-added player** (Active, before lock): starts at frame 1 with blank frames; others unaffected.
- **Mark complete eligible:** all players finished all 10 frames, no pending scores remain.

### Unit tests

Cover at minimum:

- Open frame, strike, spare, consecutive strikes.
- Frame 10: strike-strike-X, strike-7-2, spare-roll3, open (2 rolls only; roll 3 locked).
- Pending until bonus rolls entered (cross-frame lookahead).
- Clear frame N → frame N−1 reverts to pending if it depended on N’s rolls (PRD §11).
- Actionable / clearable frame edge case (Alice frames 1–4 done, frame 5 blank).
- Turn indicator tiebreak.
- Single-player game (turn always that player).

Run: **`pytest tests/bowling/`**

### Manual checks

- Tests pass.
- Shell snippet: build roll list from PRD scorecard example → scores match (Alice 44 partial, Bob 8 with pending frame 2).

---

## Phase 3 — JSON API

All validation and score computation **server-side** (PRD §08 Server Authority). Poll/read endpoints return full computed state.

Suggested routes (under `/bowling` prefix):

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `POST` | `/api/games` | Create game → `{ code, url }` |
| `GET` | `/api/games/<code>` | Full game state (poll target) |
| `POST` | `/api/games/<code>/players` | Add player `{ name }` (Setup; Active until frame-2 lock) |
| `PUT` | `/api/games/<code>/players/<id>` | Update player name (Setup only) |
| `DELETE` | `/api/games/<code>/players/<id>` | Remove player (Setup only) |
| `PUT` | `/api/games/<code>/players/order` | Reorder (Setup only) `{ player_ids: [...] }` |
| `POST` | `/api/games/<code>/start` | Setup → Active |
| `POST` | `/api/games/<code>/rolls` | Submit roll `{ player_id, frame, roll, pins }` |
| `POST` | `/api/games/<code>/clear` | Clear frame `{ player_id, frame }` |
| `POST` | `/api/games/<code>/complete` | Mark complete |

Error shape: **`jsonify({"error": "..."}), 4xx`**. Invalid code → 404.

Page routes:

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `GET` | `/bowling/` | Home |
| `GET` | `/bowling/<code>` | Game shell (Setup / Active / Complete) |

Validate: game status, roll legality (PRD §05 pin table), actionable frame only for rolls, clearable frame only for clear, no writes when `complete`.

Reject writes with consistent JSON errors. Invalid game code → **404**. Invalid roll → **400**.

### Access model (PRD §08)

- No host or permission levels — any holder of the code can read/write (except completed = read-only).
- Turn indicator is **not** enforced server-side.

### Manual checks

Use **`curl`** or browser devtools (with CSRF token):

1. Create game → get code.
2. Add 2 players, reorder, start.
3. Submit rolls out of order across players → poll shows correct pending/scores.
4. Clear frame → scores rewind correctly.
5. Invalid roll (e.g. 5 pins on second roll after 7) → 400.
6. Mark complete when eligible → status `complete`; further writes rejected.
7. Update player name on Setup OK; rename blocked after start.
8. Add player mid-Active (before frame-2 lock) → new player at frame 1 with blank scorecard.

---

## Phase 4 — Home & Setup UI

Replace placeholder templates. Mobile-first; extend **`base.html`**. Consider **`viewport-fit=cover`** on game templates (matches other hub game projects).

### Home (`GET /bowling/`) — PRD §02

- **Create New Game** → `POST /api/games` → redirect to `/bowling/<code>`.
- Code field + **Join** → navigate to `/bowling/<code>` only after validating code exists (or navigate and show error on game page — either way, invalid code shows **"No game found with that code."** and user is not left on a broken active game).
- **Rejoin** link from **`localStorage`** (`bowling_last_code`) when set; include completed games (PRD §02).

### Setup view (game status `setup`) — PRD §03

- Show code + **Share** (Web Share API + copy fallback, **absolute URL**).
- **Add Player** button → new empty name row; **Remove** per row (≥1 row remains).
- Edit names inline before start (calls update player API).
- Reorder via **up/down buttons** (preferred on mobile over drag).
- **Start Game** enabled when ≥1 non-empty name; **any scorer** on Setup may tap it (no host).
- **Poll** game state on Setup too (same 3–5s interval) so late joiners see player list updates without refresh.

### Manual checks

1. Create game on phone-width viewport; add 3 named players; edit a name; reorder; share copies/opens absolute URL.
2. Second browser joins Setup URL — both see player list update via poll; either browser can Start Game.
3. Start game → status Active.
4. Refresh Home → Rejoin link appears; Rejoin returns to game.
5. Join with bad code on Home → exact error message, no broken state.

---

## Phase 5 — Active game UI

Single **`game.html`** shell; JS renders by **`status`** (Setup / Active / Complete) — PRD §02 navigation note.

PRD §05 layout: **scrollable scorecard top, fixed pin panel bottom** (not a modal).

### Scorecard

- Horizontal scroll; all players; **Total** column (rightmost).
- Frame 10 always shows **3 roll boxes**; third locked/hidden when open frame.
- Frames 1–9 strike: **one** roll box shows `X`.
- **Turn indicator** on current player row — e.g. `▶` or left border (§06); advisory only.
- **Actionable frame highlight** per player (§05).
- Tap actionable frame → open pin panel for that player.
- Tap **current player’s row** anywhere → open their actionable frame; other players require tapping actionable cell.
- Tap non-actionable frame → no-op (§11).
- Pending frame scores as `…`; gutter as `–`.

### Pin input panel

- Opens when a frame is selected; stays visible while scoring (user may dismiss).
- Label: `"Alice — Frame 5, Roll 1"`.
- Pin grid: **6 columns**, min **48px** tall; disabled pins visually struck through.
- Roll 1: `0`–`10` with **`10 / Strike`** combined button.
- Roll 2 after partial: valid range only; spare option styled (e.g. **`/ (3)`**).
- **Multi-roll flow:** stay open across consecutive rolls for same player (§05).
- **Clear Frame** in panel and/or small icon on clearable frame cell (§07); no confirm dialog.
- Brief save feedback after server confirms (§08); **no optimistic UI**.

### Active-only

- **Add Player** (with name) until frame-2 lock (§03).
- Code + Share visible.
- **New Game** → confirm: *"Start a new game? This game will remain accessible via its code."* → Home; existing game unchanged (§09).
- **Mark Complete** shown when eligible (prominent); confirm: *"Are you sure? This will lock the game and it cannot be edited again."* (§09). Not mandatory while still Active — game stays editable until confirmed.

### Manual checks

1. Score a full 1- and 2-player game on mobile — strikes, spares, frame 10 variants.
2. Clear and re-enter a frame; confirm pending scores update (including clear affecting prior pending frame).
3. Two browsers: score from each; rolls appear after poll/submit; last-write-wins acceptable.
4. Add player after start (before frame 2) → starts at frame 1 with blanks; after frame-2 lock, control hidden.
5. All frames complete but don’t Mark Complete → still editable.

---

## Phase 6 — Sync, lifecycle & polish

### Polling (PRD §08)

- Interval 3–5s while tab visible; slow/pause in background.
- **Immediate poll** after successful roll or clear.
- Subtle connection indicator on failure; auto-retry.

### Lifecycle (PRD §09)

- **Mark Complete** prominent when eligible; confirm dialog; read-only after.
- Game with all frames done but not marked complete → **still editable** (clear + re-entry).
- **Completed** view: winner highlight including ties (e.g. *"Alice & Bob win"*), **Copy Scores** plain text, Share link.
- Join completed URL → read-only scorecard, no input.

### Edge cases (PRD §11)

- Invalid `/bowling/999999` → friendly **"No game found with that code."** (or equivalent 404 page).
- Non-actionable frame tap → no-op.
- Completed game: no input/clear.
- Simultaneous roll submit → last-write-wins (server unique constraint on roll slot).

### Manual checks

1. Full game end-to-end with 2 phones syncing.
2. Mark complete → verify locked; Copy Scores text correct; tie wording if applicable.
3. Airplane mode briefly → connection indicator; recovers on reconnect; failed submit shows indicator, retries.
4. Rejoin + deep link work for completed game.
5. Single-player game: turn indicator always on that player.

---

## Explicitly deferred

From PRD Out of Scope: accounts, profiles, cross-game history, handicaps, animations, theme toggle, perfect-game callout, randomizer, dedicated undo, rate limiting, admin CRUD, websockets, auto-generated names.

---

## PRD cheat sheet

| Topic | Phase |
| ----- | ----- |
| §01 Overview, mobile-first, flexible entry | **4**, **5** |
| §02 Home, join, rejoin, URLs, state routing | **4** |
| §03 Setup, Add/Remove/rename, late player lock | **3**, **4**, **5** |
| §04 Scoring rules | **2**, **5** |
| §05 Pin input, layout, actionable frame | **2**, **5** |
| §06 Turn indicator | **2**, **5** |
| §07 Clear frame | **2**, **3**, **5** |
| §08 Sync, server authority, save feedback | **3**, **4**, **6** |
| §09 Lifecycle, Mark Complete, Copy Scores, New Game | **3**, **5**, **6** |
| §10 Data model | **1** |
| §11 Edge cases | **2**, **4**, **6** |
| §12 UX details summary | **4**, **5**, **6** |

---

## PRD traceability

Every PRD section mapped to implementation. **Deferred** = explicitly out of scope in PRD.

| PRD | Requirement | Phase | Notes |
| --- | ----------- | ----- | ----- |
| §01 | Mobile-first, thumb-friendly, dim lighting | 4–5 | `bowling.css` contrast, 48px targets, `viewport-fit=cover` |
| §01 | No login, no cross-game memory | — | Registry + no auth on routes |
| §01 | Flexible entry (any player's next roll) | 2–3 | Actionable frame validation; turn not enforced |
| §01 | Polling sync, small user base | 6 | No websockets |
| §02 | Four screens by game status | 4–6 | `game.html` renders Setup/Active/Complete |
| §02 | `/bowling/<code>` deep link | 3–4 | |
| §02 | Home Join + invalid code message | 4 | Exact copy from PRD |
| §02 | Rejoin via localStorage | 4 | Include completed games |
| §02 | Share on Setup/Active/Complete | 4–6 | Web Share + absolute URL fallback |
| §03 | Create game → immediate code | 1, 3 | |
| §03 | Codes never reused | 1 | |
| §03 | Add Player / Remove / rename on Setup | 3–4 | PUT player name |
| §03 | Reorder Setup only | 3–4 | Up/down buttons |
| §03 | Any scorer can Start Game | 3–4 | |
| §03 | Late Add Player until frame-2 roll | 3, 5 | New player at frame 1 |
| §04 | Strike/spare/open/gutter display | 2, 5 | X, /, – |
| §04 | Frame 10 rules + 3 boxes | 2, 5 | |
| §04 | Pending scores + cumulative Total | 2, 5 | |
| §05 | Scorecard top + fixed pin panel | 5 | |
| §05 | Pin grid 6-col, validation table | 2–3, 5 | Server validates all rows |
| §05 | Actionable frame + highlight | 2, 5 | |
| §05 | Multi-roll panel stay open | 5 | |
| §05 | Current row tap vs other players | 5 | |
| §06 | Turn algorithm + advisory display | 2, 5 | |
| §07 | Clear stack unwind, no confirm | 2–3, 5 | Panel and/or frame icon |
| §07 | Clear affects pending bonuses | 2 | Test coverage |
| §08 | Server authority | 2–3 | |
| §08 | Poll 3–5s + poll on write | 4, 6 | Setup polls too |
| §08 | No optimistic UI, save feedback | 5–6 | |
| §08 | Connection indicator + retry | 6 | |
| §08 | Last-write-wins | 3 | Unique roll constraint |
| §09 | Mark Complete confirm + prominent | 5–6 | |
| §09 | Not mandatory until tapped | 5–6 | |
| §09 | Completed read-only + Copy Scores + ties | 6 | |
| §09 | New Game confirm, game persists | 5 | |
| §09 | Games never expire | 1 | No delete/TTL |
| §10 | Game/Player/Roll entities | 1 | FKs internally |
| §10 | Scores computed not stored | 2 | |
| §11 | All edge-case table rows | 2, 4, 6 | See Phase 2 tests + Phase 6 |
| §12 | UX details table (11 rows) | 4–6 | |
| — | Out of scope items | Deferred | See below |

---

## Relevant Files

- `app/projects/bowling/models.py` — SQLAlchemy models for game, player, roll.
- `app/projects/bowling/code.py` — Unique 6-digit code generation.
- `app/projects/bowling/scoring.py` — Score computation from rolls (server authority).
- `app/projects/bowling/game_state.py` — Actionable/clearable frame, turn player, locks.
- `app/projects/bowling/routes.py` — Page routes and JSON API endpoints.
- `app/projects/bowling/static/bowling.css` — Prefixed mobile-first styles.
- `app/projects/bowling/static/bowling.js` — Client render, poll, pin input, share, localStorage.
- `app/projects/bowling/templates/bowling/index.html` — Home screen.
- `app/projects/bowling/templates/bowling/game.html` — Game shell for `/bowling/<code>`.
- `app/__init__.py` — Import Bowling models for migrations.
- `tests/bowling/test_scoring.py` — Unit tests for scoring engine.
- `tests/bowling/test_game_state.py` — Unit tests for actionable frame, turn, locks.

### Notes

- Scoring/game-state tests are high value; skip trivial route smoke tests unless you want them.
- Run tests: **`pytest tests/bowling/`**
- User runs migrations; do not commit auto-generated migration files without user review.

---

## Tasks

- [ ] **1.0 Models, code generation & migration**
  - [ ] 1.1 Add `BowlingGame`, `BowlingPlayer`, `BowlingRoll` in `models.py` with `bowling_*` table names and FK relationships.
  - [ ] 1.2 Add unique constraints: `bowling_game.code`, `(player_id, frame, roll)` on rolls.
  - [ ] 1.3 Implement `code.py` — random unused 6-digit zero-padded code.
  - [ ] 1.4 Import models in `app/__init__.py`.
  - [ ] 1.5 User runs `flask db migrate` / `flask db upgrade`; verify in shell.

- [ ] **2.0 Scoring engine & game-state logic**
  - [ ] 2.1 Implement `scoring.py` — strike/spare/open, frame 10, pending, cumulative totals.
  - [ ] 2.2 Implement `game_state.py` — actionable frame, clearable frame, current turn player.
  - [ ] 2.3 Implement lock helpers — setup rename/reorder, player-add-after-frame-2, mark-complete eligibility.
  - [ ] 2.4 Add `tests/bowling/test_scoring.py` covering PRD §04 examples and frame-10 variants.
  - [ ] 2.5 Add `tests/bowling/test_game_state.py` covering actionable/clearable and turn tiebreak.

- [ ] **3.0 JSON API**
  - [ ] 3.1 `POST /api/games` — create game, return code + url.
  - [ ] 3.2 `GET /api/games/<code>` — full computed state for polling.
  - [ ] 3.3 Player endpoints — add, update name (setup), remove (setup), reorder (setup).
  - [ ] 3.4 `POST .../start`, `POST .../rolls`, `POST .../clear`, `POST .../complete` with server validation.
  - [ ] 3.5 Reject writes on `complete` games; enforce actionable/clearable frame rules.
  - [ ] 3.6 `GET /bowling/<code>` page route serving `game.html`.
  - [ ] 3.7 CSRF on POST via `X-CSRFToken`; 404 for bad code; exact error messages per PRD.

- [ ] **4.0 Home & Setup UI**
  - [ ] 4.1 Build `index.html` — Create, Join (invalid code message), Rejoin, mobile layout.
  - [ ] 4.2 Build Setup view — Add Player, Remove, inline rename, reorder, any-scorer Start.
  - [ ] 4.3 Share button — `navigator.share()` absolute URL, clipboard fallback.
  - [ ] 4.4 Poll on Setup; persist last code to localStorage on game visit.

- [ ] **5.0 Active game UI**
  - [ ] 5.1 Scorecard — scroll, Total column, frame 10 layout, X///– display, pending.
  - [ ] 5.2 Turn indicator + actionable highlight + row tap rules.
  - [ ] 5.3 Pin panel — 6-col grid, 10/Strike button, spare styling, multi-roll, dismiss.
  - [ ] 5.4 Clear Frame in panel and/or frame icon; save feedback; Add Player until lock.
  - [ ] 5.5 New Game + Mark Complete dialogs (exact PRD copy); Mark Complete optional until tapped.
  - [ ] 5.6 Styles — prefixed classes, 48px+ targets, readable in dim light.

- [ ] **6.0 Sync, lifecycle & polish**
  - [ ] 6.1 Polling (3–5s) on Active + Setup; immediate poll after write; background slow-down.
  - [ ] 6.2 Connection indicator + retry on poll/submit failure.
  - [ ] 6.3 Completed view — read-only, winners/ties, Copy Scores, Share.
  - [ ] 6.4 Edge cases — single player, all-frames-done-but-not-locked, simultaneous writes.
  - [ ] 6.5 Manual end-to-end pass on two devices.
