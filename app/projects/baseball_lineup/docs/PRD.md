# Baseball Lineup — Product Requirements (v1)

## 1. Overview

**Vision:** Replace the coach’s spreadsheet for youth baseball lineups with a focused web app inside the gmich hub. A logged-in user manages one or more **teams**, each with a **roster** and **games**. For each game, mark who is present, then assign every attending player a **position for each inning** (typically 6). Each game carries its own **lineup structure** — how many of each position are expected in each inning — and the app warns when the grid diverges from it.

**Origin:** Today this is tracked in a sheet — rows are players, columns are innings, cells are position codes. Summary columns track how many innings each kid spends in outfield, bench, infield, etc.

**Design principle:** *Spreadsheet familiarity, app smarts* — the primary UI matches the sheet coaches already use. The app surfaces warnings while editing; the coach copies the final lineup by hand to a physical display for game day.

A **team** means one team in one season (e.g. “10U Tigers — Spring 2026”). Next season is a new team.

### Example (Greg’s team — 15 roster kids, 10 field spots, 6 innings)

| Player | 1st | 2nd | 3rd | 4th | 5th | 6th | OF | Bench | IF | Blank |
|--------|-----|-----|-----|-----|-----|-----|----|-------|----|-------|
| Chris  | Bench | CF | LF | Bench | SS | … | 2 | 2 | 2 | 0 |
| … | … | … | … | … | … | … | … | … | … | … |

- **Bench** = not on field that inning (code `Bench` in app; was “Ben” in the sheet).
- **PH** = pitcher’s helper; **P** = pitcher. Greg’s default expects **PH in innings 1/2/5/6** and **P in innings 3/4** — but this is just a default, fully editable per game.
- **P and PH innings count toward Infield** in the summary columns, matching how the coach adds it up by hand. So OF + Bench + IF + Blank always equals the inning count.
- **10 field spots** per inning by default (5 infield + 4 outfield incl. **2 CF** + 1 battery). Remaining present players are on bench.

---

## 2. Resolved product decisions

| Topic | Decision |
|-------|----------|
| **Auth & ownership** | Hub login required. One coach user per team. No sharing, no parent access. Many independent coaches may use the app. Every route checks `team.user_id == current_user.id` and 404s otherwise. |
| **Teams** | A team = one squad for one season. Fully separate from each other, no cross-team player identity. Optional: **duplicate roster** when creating a new team (backlog). |
| **Player identity** | **First name + last name** only. |
| **Roster changes** | Add players anytime. No mid-season special handling and no deactivate/archive for v1. New players appear on **all** games automatically (see attendance). |
| **Game metadata** | **Date + opponent** only. |
| **Attendance** | All roster players **present by default**; coach marks individuals absent. No mid-game / late-arrival modeling. |
| **Lineup structure config** | Lives on the **game** — the game is the source of truth. The team stores **defaults** that are copied into each new game at creation. No override/inheritance logic to reason about. Editing team defaults never changes existing games. |
| **Structure shape** | For each inning, an **expected count for every position code** (fully configurable). Nothing about position counts is hardcoded; the app only ships an initial default template. |
| **Lineup UI** | **Spreadsheet grid** — rows = present players, columns = innings. Blank starting point for each new game. |
| **Bench** | Explicit position code **`Bench`**. Not part of expected counts — bench is whoever is left over. |
| **Position codes (v1)** | `C, 1B, 2B, 3B, SS, LF, CF, RF, P, PH, Bench` — fixed catalog, defined in code, not per team. |
| **Validation** | **Warnings only**, never blocks save. **Inning-level only** in v1 (wrong position counts, unassigned players). |
| **Per-player numbers** | Show **Outfield / Bench / Infield / Blank** inning counts per player so the coach can eyeball fairness and adjust. **P and PH count as Infield**; the four columns sum to the inning count. **No per-player warnings** in v1. |
| **Repeat positions** | A player filling the same position in more than one inning is **highlighted in the grid** (not a warning, not blocked) so the coach can see it and decide. Bench excluded. |
| **Batting order** | Per-game ordered list of present players. Simple integer per player; no warnings. |
| **Save workflow** | Save, edit, view — no draft vs. final states. |
| **Export / display** | Viewable in app only; coach copies by hand. No print/PDF v1. |
| **Copy from last game** | Not v1 — blank grid each time. |
| **Device** | Laptop/desktop for planning in advance. |
| **Player constraints** | Later (never catcher, max P innings, etc.). |

---

## 3. Core entities

| Entity | Purpose |
|--------|---------|
| **Team** | Named squad + season owned by a hub user. Holds roster + **default** lineup structure. |
| **Player** | Roster member (first name, last name, sort order). |
| **Game** | Date + opponent + **its own** inning count and expected position counts. |
| **Game roster entry** | Per game, per player: absence flag and batting order. Only exists when one of those is set. |
| **Lineup cell** | `(game, player, inning) → position_code`. One assignment per player per inning. |

See [`DATA_MODEL.md`](DATA_MODEL.md) for schema.

---

## 4. Team setup

### 4.1 Create team

- Name + optional season label.
- Default lineup structure (§4.3), pre-filled with the shipped template; editable immediately.

### 4.2 Roster

- Add / edit / reorder / remove players (first + last name).
- Removing a player deletes their lineup cells in **all** games, including past ones — confirm with a count of affected games.
- **Duplicate roster on team create:** optional dropdown on the new-team form copies names and sort order from another of your teams (not games or lineup settings).

### 4.3 Lineup structure (team defaults, and per game)

The same editor is used for team defaults and for a single game. It is a small grid:

- **Inning count** (number).
- **Rows = position codes** (all except `Bench`), **columns = innings**, each cell an expected count.

| Position | 1 | 2 | 3 | 4 | 5 | 6 |
|----------|---|---|---|---|---|---|
| C | 1 | 1 | 1 | 1 | 1 | 1 |
| 1B | 1 | 1 | 1 | 1 | 1 | 1 |
| 2B | 1 | 1 | 1 | 1 | 1 | 1 |
| 3B | 1 | 1 | 1 | 1 | 1 | 1 |
| SS | 1 | 1 | 1 | 1 | 1 | 1 |
| LF | 1 | 1 | 1 | 1 | 1 | 1 |
| CF | 2 | 2 | 2 | 2 | 2 | 2 |
| RF | 1 | 1 | 1 | 1 | 1 | 1 |
| P | 0 | 0 | 1 | 1 | 0 | 0 |
| PH | 1 | 1 | 0 | 0 | 1 | 1 |
| **Field spots** | **10** | **10** | **10** | **10** | **10** | **10** |

Notes on this design:

- **Field spots per inning is derived** (the column sum), shown read-only under the grid. It is never stored separately, so it cannot disagree with the counts above it.
- The P-vs-PH rotation is not a special setting — it is just two rows of this grid. A coach who wants 1 CF, no PH, or a 9-player field edits numbers.
- Position **categories** (used only for the per-player summary columns) are fixed in code. There are three, and they cover every code so the summary always adds up:

| Category | Codes |
|----------|-------|
| Outfield | LF, CF, RF |
| Infield | C, 1B, 2B, 3B, SS, **P, PH** |
| Bench | Bench |

  P and PH sit in Infield deliberately — that is how the coach totals them on the sheet. The structure editor still groups them at the bottom as the battery rows, but they are not their own summary column.

- Convenience in the editor: “apply inning 1 to all innings” so the common case is a single column of edits.
- Changing inning count resizes every row: growing pads with the last inning’s value, shrinking drops from the end.

---

## 5. Game workflow

### 5.1 Create game

- Enter **date** and **opponent**.
- **Copy** the team’s default inning count + expected counts onto the new game.
- No attendance or lineup rows are written — everyone is present by default and the grid starts blank.

### 5.2 Game structure (optional edit)

- Same editor as §4.3, scoped to this game. Used when a game differs (short game, missing pitcher, borrowed player).
- Editing here never touches team defaults, and vice versa.

### 5.3 Set attendance

- Toggle players absent before or during lineup edit.
- Absent players are excluded from the grid and from validation. Their existing lineup cells are **kept**, so toggling back restores prior work.

### 5.4 Lineup editor (primary screen)

**Layout:** Spreadsheet — **rows = present players**, **columns = innings 1…N**.

- Each cell: dropdown of position codes.
- Trailing columns (computed, read-only): **OF | Bench | IF | Blank** inning counts for that player. Informational — the coach uses these to rebalance manually. P and PH innings land in IF, so the four columns sum to the inning count and a row that doesn’t add up means something is off.
- **Repeat highlight:** when a player fills the same position in more than one inning, every cell in that repeat gets a shaded background and a tooltip like “CF — 3 innings this game”. Bench is never highlighted. This is a visual cue only: repeats are often unavoidable, so nothing is blocked and nothing appears in the warnings panel.
- **Fill blanks with Bench** button (whole grid and per inning) so the coach isn’t hand-selecting Bench dozens of times.
- **Warnings panel**, inning-level only (§6).
- Small **legend** under the grid explaining the repeat shading and the warning highlight, so the colors are self-explanatory.
- One **Save** button posts the whole grid; warnings never block save.

### 5.5 Batting order

- Ordered list of present players for this game, edited on the game page.
- Stored as an integer per player; rows sort by it, falling back to roster order when unset.
- No validation — gaps and ties are allowed and simply sort stably.

### 5.6 View game

- Same grid, read-only, with warnings recomputed server-side. Edit action switches to the editor.

---

## 6. Validation rules (v1)

All rules produce **warnings** only, and all are **inning-level**.

For each inning, over **present** players only:

| Check | Example warning |
|-------|-----------------|
| Actual count per position ≠ expected count | “Inning 3: expected 1 SS, found 3” / “Inning 3: expected 1 1B, found none” |
| Present players with no cell assigned | “Inning 4: 2 players unassigned” |
| Expected field spots > present players | “Inning 2: 10 field spots but only 9 players present” |

That’s the whole rule set. Because every position has an expected count and bench is the remainder, “11 players on the field” and “nobody at first base” both surface as position-count mismatches — there is no separate field-total or category check to keep in sync.

**Not in v1:** per-player distribution warnings. The OF/Bench/IF/Blank columns are shown so the coach can judge fairness; the app does not opine on them yet.

**Deliberately not a warning:** a player repeating a position across innings. It’s shaded in the grid (§5.4) rather than listed here, because on a 15-kid roster some repeats are forced and a panel entry per occurrence would drown out the real problems.

---

## 7. Non-goals (v1)

- Co-coach / parent sharing
- Per-player fairness or distribution warnings
- Player-specific constraints (no catcher, max P innings, etc.)
- Copy lineup from previous game
- Print / PDF / export
- CSV import
- Auto-generate fair lineup
- Live in-game display, scoring, stats
- League schedule sync
- Cross-season player identity

---

## 8. Technical notes

- **Stack:** Flask, Postgres, existing hub auth.
- **Tables:** `blu_*` prefix. **CSS:** `blu-` class prefix. **URL:** `/baseball-lineup`.
- **Grid save:** JS holds grid state, computes summary columns and warnings live, and posts the full grid as JSON on Save. Server replaces that game’s cells in one transaction. Server recomputes warnings independently for the read-only view.
- **Position catalog** is a Python constant, not per-team data, so adding a code later applies everywhere at once.
- **Migrations:** Coach runs `flask db migrate` / `flask db upgrade` after schema review.

---

## 9. Implementation phases

Each phase ends at a manually testable point.

### Phase 1 — Teams & roster ← **start here**

- Migration for the v1 schema.
- Team CRUD, including the default structure editor (§4.3).
- Roster CRUD with reorder and delete confirmation.

**Manual test:** Create “10U Tigers / Spring 2026”, confirm the default grid shows P in innings 3/4 and 2 CF, change CF to 1 and back, add 15 players, reorder two, delete one.

### Phase 2 — Games & attendance

- Game list, create game (date + opponent) copying team defaults.
- Per-game structure editor.
- Attendance toggles.

**Manual test:** Create a game, verify its structure matches team defaults, change the game to 5 innings and confirm team defaults are untouched, mark two players absent.

### Phase 3 — Lineup editor

- Grid, save/load cells, fill-blanks-with-Bench.
- Computed OF / Bench / IF / Blank columns.
- Repeat-position highlighting + legend.
- Inning-level warnings panel.

**Manual test:** Fill a full lineup; verify warnings fire for 3 SS in an inning, a missing 1B, and unassigned players; verify each player’s four counts sum to 6 with pitcher innings landing in IF; put one kid at CF in two innings and confirm both cells shade while a kid with two bench innings does not; save, reload, and confirm everything persists.

### Phase 4 — Batting order

- Per-game order editing and display.

**Manual test:** Set a batting order, reload, confirm rows sort by it.

### Backlog (post-v1)

- Copy lineup from last game
- Per-player fairness warnings and thresholds
- Player constraints
- Print-friendly view
