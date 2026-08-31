# Baseball Lineup — Product Requirements (v1)

## 1. Overview

**Vision:** Replace the coach’s spreadsheet for youth baseball lineups with a focused web app inside the gmich hub. A logged-in user manages one or more **teams**, each with a **roster** and **games**. For each game, mark who is present, then assign every attending player a **position for each inning** (typically 6). Team-level defaults describe what the lineup structure should look like each inning; the app warns when the grid violates those expectations or when a player’s distribution looks off.

**Origin:** Today this is tracked in a sheet — rows are players, columns are innings, cells are position codes. Summary columns track how many innings each kid spends in outfield, bench, infield, etc.

**Design principle:** *Spreadsheet familiarity, app smarts* — the primary UI matches the sheet coaches already use. The app surfaces warnings (wrong counts, blanks, uneven playing time) while editing; the coach copies the final lineup by hand to a physical display for game day.

### Example (Greg’s team — 15 roster kids, 10 field spots, 6 innings)

| Player | 1st | 2nd | 3rd | 4th | 5th | 6th | OF | Bench | IF | Blank |
|--------|-----|-----|-----|-----|-----|-----|----|-------|----|-------|
| Chris  | Bench | CF | LF | Bench | SS | … | 2 | 2 | 2 | 0 |
| … | … | … | … | … | … | … | … | … | … | … |

- **Bench** = not on field that inning (code `Bench` in app; was “Ben” in the sheet).
- **PH** = pitcher’s helper; **P** = pitcher — team config expects **PH in innings 1/2/5/6** and **P in innings 3/4**.
- **4 outfielders**, **2 CF every inning** (team-configurable; another coach might default to 1 CF).
- **10 field spots** per inning; remaining present players are on bench.

---

## 2. Resolved product decisions

| Topic | Decision |
|-------|----------|
| **Auth & ownership** | Hub login required. One coach user per team. No sharing, no parent access. Many independent coaches may use the app. |
| **Teams** | Fully separate from each other. No cross-team player identity. Optional: **duplicate roster** when creating a new team (nice-to-have, not v1). |
| **Player identity** | **First name + last name** only. |
| **Roster changes** | Add players anytime. No special mid-season handling — a new player simply wasn’t on earlier games; a departed player wasn’t on later ones. No need to deactivate/archive for v1. |
| **Game metadata** | **Date + opponent** only. |
| **Attendance** | All roster players **present by default**; coach removes absent players. No mid-game / late-arrival modeling. |
| **Lineup UI** | **Spreadsheet grid** — rows = present players, columns = innings. Blank starting point for each new game. |
| **Bench** | Explicit position code **`Bench`**. |
| **Position codes (v1)** | `C, 1B, 2B, 3B, SS, LF, CF, RF, P, PH, Bench` — fixed set for now. |
| **Inning structure** | Team config defines **what to expect each inning** (e.g. P in 3/4, PH in 1/2/5/6; 2× CF; 4 OF; 10 field spots). App **warns** when actual lineup diverges (too many or too few). |
| **Per-game overrides** | Not required for v1 — games inherit team config. |
| **Validation** | **Warnings only** (never hard-block save). Per-inning (wrong position counts) and per-player (bad distribution, blanks). |
| **Summary stats** | Compute **Outfield / Bench / Infield / Blank** per player while editing. Blank = cell not set. Completed lineup should have **zero blanks** for present players. Distribution warnings help spot too much/little of a category. |
| **Save workflow** | Save, edit, view — no draft vs. final states. |
| **Export / display** | Viewable in app only; coach copies by hand. No print/PDF v1. |
| **Copy from last game** | Not v1 — blank grid each time. |
| **Device** | Laptop/desktop for planning in advance. |
| **Player constraints** | Later (never catcher, max P innings, etc.). |

---

## 3. Core entities

| Entity | Purpose |
|--------|---------|
| **Team** | Named group owned by a hub user. Holds roster + lineup structure config. |
| **Player** | Roster member (first name, last name, sort order). |
| **Game** | Date + opponent. Links to attendance + lineup. Inherits team config. |
| **Game roster entry** | Per game: is this player present? |
| **Lineup cell** | `(game, player, inning) → position_code`. One assignment per player per inning. |
| **Team settings (JSON)** | Inning count, field spots, position catalog categories, **per-inning expected counts** (see §6). |

See [`DATA_MODEL.md`](DATA_MODEL.md) for schema.

---

## 4. Team setup

### 4.1 Create team

- Name (and optional season label for display).
- Lineup structure config (§6) — required before lineups make sense; sensible defaults on create.

### 4.2 Roster

- Add / edit / reorder / remove players (first + last name).
- Duplicate roster from another team — **backlog**, not v1.

### 4.3 Lineup structure config (team level)

Applied to all games on this team unless we add per-game overrides later:

| Setting | Example (Greg) | Notes |
|---------|----------------|-------|
| Inning count | 6 | |
| Field spots per inning | 10 | Players on field, not bench |
| Outfield count | 4 | Category warning |
| CF count per inning | 2 | Position-specific; another team might use 1 |
| Battery per inning | `{1: PH, 2: PH, 3: P, 4: P, 5: PH, 6: PH}` | Expected battery role each inning |

Position **categories** for summary + warnings:

| Category | Codes |
|----------|-------|
| Outfield | LF, CF, RF |
| Infield | C, 1B, 2B, 3B, SS |
| Bench | Bench |
| Battery | P, PH (count toward field spots) |

---

## 5. Game workflow

### 5.1 Create game

- Enter **date** and **opponent**.
- Seed attendance: all roster players **present**.
- Empty lineup grid (no cells).

### 5.2 Set attendance

- Toggle players absent before/during lineup edit.
- Absent players: excluded from grid and validation.

### 5.3 Lineup editor (primary screen)

**Layout:** Spreadsheet — **rows = present players** (roster sort order), **columns = innings 1…N**.

- Each cell: dropdown of position codes.
- Trailing columns (computed, read-only): **OF | Bench | IF | Blank** inning counts for that player.
- **Warnings panel** (or inline highlights):
  - **Per inning:** e.g. “Inning 3: 1 P expected, 0 found” / “Inning 2: 3 CF, expected 2” / “Inning 4: 11 on field, expected 10”.
  - **Per player:** e.g. “Alex: 4 bench innings” / “Jordan: 2 blank cells”.
- Save anytime; warnings persist until fixed but do not block save.

### 5.4 View game

- Same grid, read-only or editable via edit action.

---

## 6. Validation rules (v1)

All rules produce **warnings** only.

### 6.1 Completeness

- Each **present** player must have a position in every inning (no blanks when lineup is “done”).
- Warn on any blank cell while editing.

### 6.2 Per-inning structure (from team config)

For each inning, compare actual assignments vs. expected:

- Count on **field** (all codes except `Bench`) vs. `field_spots`.
- Count per **position** (e.g. CF min/max).
- Count per **category** (e.g. outfield total).
- Expected **battery** role for that inning (P vs PH) — warn if wrong count.

Warn when actual is **over or under** expected (coach asked for both directions).

### 6.3 Per-player distribution

- Show OF / Bench / IF totals (like spreadsheet columns).
- Warn when a player’s split looks imbalanced — thresholds TBD in implementation (e.g. flag if bench innings ≥ N or outfield ≥ N). Start with visible counts; tune warning thresholds after dogfooding.

---

## 7. Non-goals (v1)

- Co-coach / parent sharing
- Per-game config overrides
- Copy lineup from previous game
- Print / PDF / export
- CSV import
- Auto-generate fair lineup
- Player-specific constraints (no catcher, etc.)
- Live in-game display, scoring, stats
- League schedule sync

---

## 8. Technical notes

- **Stack:** Flask, Postgres, existing hub auth.
- **Tables:** `blu_*` prefix.
- **CSS:** `blu-` class prefix.
- **URL:** `/baseball-lineup`
- **Migrations:** Run `flask db migrate` / `upgrade` after schema review (coach runs commands).

---

## 9. Implementation phases

### Phase 1 — Foundation ← **start here**

- Migrations for locked schema.
- Team CRUD + lineup structure config UI.
- Roster CRUD (first/last name, reorder).
- Game list, create game (date + opponent), attendance toggles.

**Manual test:** Create team, set config (6 innings, 2 CF, P in 3/4), add roster, create game, mark one player absent.

### Phase 2 — Lineup editor

- Spreadsheet grid, save/load lineup cells.
- Computed summary columns (OF / Bench / IF / Blank).
- Warning panel: blanks, per-inning counts, basic per-player flags.

**Manual test:** Fill a full lineup for a game; verify warnings fire when CF count wrong or cells blank; save and re-open.

### Phase 3 — Polish (post-v1 backlog)

- Duplicate roster on team create
- Per-game config overrides
- Tunable distribution warning thresholds
- Print-friendly view
- Copy from last game
