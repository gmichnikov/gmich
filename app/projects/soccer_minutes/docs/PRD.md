# Soccer Minutes — Product Requirements (v1)

## 1. Overview

**Vision:** A sideline + recap tool inside the gmich hub for youth soccer. A logged-in coach manages one or more **teams**, each with a **roster**, a **formation**, and **games**. For each game, mark who is present, set who starts in each position, then record **substitutions** and **on-field swaps** with a game-clock time. The app derives **how many minutes each kid played at each position** (and in each group: GK / DEF / MID / FWD).

**Origin:** Separate from Baseball Lineup. That app is a pre-game inning grid. This one is continuous time: who is on the field *right now*, who came on for whom, and the resulting minutes. Teams / rosters / attendance are the overlap; the live game and minutes math are not.

**Design principle:** *Record what happened, don't coach for you.* Commercial apps (Pitch Planner, FairSub, SubTime, SubAssist) add auto-rotations, fairness engines, parent reports, and suggested next subs. This app does not. It remembers the field, stamps the time, and shows quiet minute totals.

**Primary device:** A phone in portrait on the sideline. Every screen must be usable there (large tap targets, no hover-only controls). Roster and formation *can* be done on a laptop; they still have to work on a phone. The live game screen is designed for one-handed-ish use at the field, not a spreadsheet.

A **team** means one squad in one season (e.g. “9U United — Fall 2026”). Next season is a new team. Greg has both a **9v9** and a **7v7** team; each team sets its own field size via formation counts.

### Example (7v7, formation 2-3-1)

Field slots: GK, LB, RB, LM, CM, RM, ST. Roster of 11. Game is two halves of whatever length the ref actually plays.

- Kickoff: seven kids in those slots, four on the bench.
- Around minute 8, two kids are waiting to come on. Coach edits a **pending copy** of the pitch (everyone else stays put): puts Alex on Sam’s slot, Priya on Chris’s slot. Clock still running. When the ref waves them on, **Go** — both changes stamp 8:xx together.
- Slide example: ABC on; D for A; E on, B slides to C, C off. Pending starts as ABC. Put D on A; send C to the bench; move B into C’s empty slot; put E in B’s empty slot. Unrelated kids are untouched. **Go** once.
- Later: swap two on-field kids on the pending pitch, tap Go when they actually switch.
- Halftime, then second half with the same field unless the coach changes it first.
- Recap: minutes follow the field as of each Go.

---

## 2. Resolved product decisions

| Topic | Decision |
|-------|----------|
| **Auth & ownership** | Hub login required. One coach user per team. No sharing, no parent access, no co-coach. Many independent coaches may use the app. Every route checks `team.user_id == current_user.id` and 404s otherwise. |
| **Teams** | A team = one squad for one season. Fully separate from each other and from Baseball Lineup tables. No cross-team player identity. |
| **Player identity** | **First name + last name**, plus optional **jersey number**. |
| **Roster changes** | Add / edit / reorder / remove players anytime. No deactivate/archive in v1. New players appear on **all** games automatically (see attendance). |
| **Game metadata** | **Date + opponent** only. No score. |
| **Attendance** | All roster players **present by default**; coach marks individuals absent for the whole game. No late-arrival / leave-early modeling in v1. |
| **Formation config** | Lives on the **game** — the game is the source of truth. The team stores a **default** that is copied into each new game at creation. Editing team defaults never changes existing games. **One formation per team** (and thus per game) in v1. No mid-game formation change. |
| **Formation shape** | Always **one GK slot**. Coach enters how many **DEF / MID / FWD** slots and a **name** for each slot. Field size is derived: `1 + DEF + MID + FWD` (7 or 9 for Greg’s teams; not limited to those). Slot order within a line is left-to-right on the pitch. |
| **Formation on the game after kickoff** | Editable **before** the first `period_start` event. Locked after kickoff so historical minutes stay attached to the slots they were recorded against. |
| **Pitch visualization** | Simple pitch with four bands (FWD, MID, DEF, GK). Not a full tactical diagram. Each slot shows its name (and jersey if set). |
| **Starting field** | Coach assigns present players to slots before kickoff. Unassigned present players are the bench. Empty slots at kickoff are allowed but should be visibly empty (coach’s problem, not blocked). |
| **In-game actions** | **Pending field, then Go.** The pending pitch **starts as a copy of who is on now**. You only change the kids who are moving; everyone else stays. The live field and minutes do not change until **Go**, which stamps one time and commits the pending picture. |
| **Time model** | **Game-clock time into the current period** is the source of truth (stored as milliseconds). Not wall-clock (10:23 AM). Optional running **count-up clock** stamps the current time on an action; the coach can always type or edit that time. |
| **Clock shape** | Count up from 0:00 **each period**. Pause / resume. Period ends when the coach taps end — **no required half length** (lengths are not consistent). Team sets **how many periods** (default 2); that copies onto the game and can be changed there before kickoff. |
| **Clock survival** | Persist elapsed + running/paused + last-resume wall time. Displayed elapsed uses wall-clock math, not a JS interval. Lock screen / pocket / refresh does **not** pause or zero the clock. Coach can **set/correct** the displayed clock (started late, forgot to pause). |
| **Fairness** | **Quiet minutes list** during and after the game (totals + by GK / DEF / MID / FWD, and by slot name). No color bars, no “short / over target” messaging, no suggested subs, no auto-rotation. |
| **Season totals** | On the team: sum of minutes by player by group and by slot name, across that team’s games. |
| **Save workflow** | Every live action (Start, Pause, Resume, End, Go, **each pending gesture**, Reset, set-clock) saves immediately to the server. Pending is not minutes until Go. If a save fails (no signal, session dead), show a clear error and do not pretend it worked. Undo last **event**. |
| **Export / display** | Viewable in app only. No print / PDF / CSV in v1. |
| **Copy last starting XI** | Not v1. |
| **Device** | **Mobile-first, portrait phone.** Live game is the critical screen. Team/roster/formation/recap must work on a phone too; laptop is optional for setup. Large tap targets (min 44px). No hover-only UI. Wake-lock while the live page is visible and the clock is running. **No offline mode in v1.** |
| **Related tools considered** | Pitch Planner, FairSub, SubTime, SubAssist, and similar. Copied: pauseable clock, pitch + recap, undo. **Not** copied: commit-on-tap or “re-enter the whole XI.” We edit a pending copy, then Go. Skipped: see §8. |

---

## 3. Core entities

| Entity | Purpose |
|--------|---------|
| **Team** | Named squad + season owned by a hub user. Holds roster, default formation, default period count. |
| **Player** | Roster member (first name, last name, optional jersey, sort order). |
| **Game** | Date + opponent + **its own** formation and period count + live clock fields + draft field assignments. |
| **Game roster entry** | Per game, per player: absence flag. Optional row; player is present unless `is_present = false`. |
| **Event** | Append-only log of `period_start`, `field_set` (new full field at one stamp), `period_end`. Minutes and the current field are **derived** by replaying events. |

See [`DATA_MODEL.md`](DATA_MODEL.md) for schema.

Pause / resume is **clock state on the game**, not an event. Pauses do not change who is on the field; they only stop the count-up clock so the next stamped time is right.

---

## 4. Team setup

### 4.1 Create team

- Name + optional season label.
- Default **period count** (default **2**).
- Default **formation** (§4.3), pre-filled with a shipped 7v7 2-3-1 template; editable immediately. A 9v9 team changes the DEF / MID / FWD counts (e.g. 3-3-2).

### 4.2 Roster

- Add / edit / reorder / remove players (first name, last name, optional jersey number).
- Jersey number is **not** unique and **not** required (youth numbers are messy). Shown on the pitch when present.
- Removing a player deletes their events / assignments in **all** games, including past ones — confirm with a count of affected games.

### 4.3 Formation (team defaults, and per game before kickoff)

The same editor is used for team defaults and for a single game (while still editable).

- **GK:** always exactly one slot. Default name `GK`; renameable. Not removable in v1.
- **DEF / MID / FWD:** integer counts, each ≥ 0. Changing a count adds or removes slots at the **end** of that line.
- Each slot has a **name** the coach types (e.g. LB, CB, RB, LM, CM, RM, ST).
- **Field size** is derived and shown read-only: `1 + DEF + MID + FWD`. Never stored separately.

Shipped default (7v7, 2-3-1):

| Group | Slots (left → right) |
|-------|----------------------|
| FWD | ST |
| MID | LM, CM, RM |
| DEF | LB, RB |
| GK | GK |

**Pitch preview** in this editor: four bands, slots spaced evenly in each band in the named order. Enough to see “this is a 2-3-1” without a real tactics board.

Convenience: no catalog of 40 named formations. Counts + names are the whole model. The 2-3-1 / 3-3-2 presets are just starting numbers the coach can change.

---

## 5. Game workflow

### 5.1 Create game

- Enter **date** and **opponent**.
- **Copy** the team’s default formation and period count onto the new game.
- No attendance rows are written (everyone present by default). No events yet. Draft field assignments start empty.

### 5.2 Game formation and periods (optional edit, before kickoff)

- Same formation editor as §4.3, scoped to this game.
- Period count editable here too.
- Editing here never touches team defaults, and vice versa.
- After the first `period_start`, both are locked for that game.

### 5.3 Set attendance

- Toggle players absent before or during setup.
- Absent players are excluded from the pitch, the bench, and minutes. They are not treated as “sat the whole game.”
- If a player already has a draft assignment and is marked absent, clear that assignment.

### 5.4 Starting field (draft assignments)

- Pitch shows the game’s slots. Bench lists present players not in a slot.
- Assign: tap a bench player then a slot (or tap a slot and pick a player). Replacing a filled slot sends the previous player to the bench.
- Clear a slot: send that player back to the bench.
- This is **draft state on the game**, not yet an event. It can be edited freely until kickoff, and again **between periods** (§5.6).

### 5.5 Live period (primary screen — phone-first)

**Layout:** clock + pitch + bench + **Go** + **Reset pending** + a short **diff list** + quiet minutes list + undo.

There are two pictures of the field:

- **Live** — who is actually on. This is what minutes use. Unchanged until Go.
- **Pending** — starts as an exact **copy** of live. You only edit the slots that are changing. Everyone you do not touch stays where they are; you never re-enter the whole field.

Pending slots that differ from live are marked (e.g. name highlighted, “in” / “off” / “moved”). A line under the pitch lists the diff in plain language, e.g. `D on for A (ST)`, `C off`, `B LM → ST`, `E on (LM)`. **Go** is disabled while pending equals live.

**How to edit pending (order does not matter):**

| Gesture | Effect on pending only |
|---------|------------------------|
| Bench player, then a slot | That player goes in that slot. Whoever was there goes to the pending bench. (Straight 1-for-1.) |
| Field player, then another **empty** slot | That player **moves**. Their old slot becomes empty. |
| Two occupied field players | They **swap** slots. |
| Field player, then bench / “off” | That player goes to the pending bench. Their slot becomes empty. |
| **Reset** | Pending is copied from live again. |

Empty pending slots are allowed (warning if a slot was filled live and is empty pending). Fill them from the bench before Go if that was not intentional.

**Worked slide:** live is A, B, C (plus the rest of the XI, untouched).

1. Pending is already A, B, C, …
2. D (bench) onto A’s slot → D in, A pending-bench.
3. C off → C’s slot empty.
4. B onto C’s empty slot → B has slid; B’s old slot empty.
5. E (bench) onto B’s empty slot.
6. Diff shows the four changes. Wait for the ref. **Go**.

Clock keeps running the whole time you are arranging pending.

1. **Start period** writes `period_start` at 0:00 with the current draft assignments. Clock counts up. Pending is initialized as a copy of that field.
2. Arrange pending as above. **Each gesture saves pending to the server** so a pocket / killed tab does not wipe the staged picture. Live pitch and minutes do not change.
3. **Go** writes one `field_set` with the pending assignments. Default stamp is the current clock; **the coach can type a different time before confirming** (tapped Go late). Live becomes that picture. Pending is re-copied from the new live field.
4. A single 1-for-1 is: put the bench kid on that slot, tap Go.
5. **Pause / resume** does not write a field event. You can still edit pending while paused; Go stamps the frozen time.
6. **Undo** deletes the most recent event. Undoing a `field_set` restores the previous live field (the whole stoppage, not one kid).
7. **End period** writes `period_end` at the current clock time and stops the clock. If pending differs from live, do **not** silently apply it — Reset or Go first, or block End until Reset. The live field at period end becomes draft assignments for the next period.

Empty slots at `period_start` / `field_set` are allowed; nobody is credited minutes for an empty slot.

### 5.6 Between periods

- Clock is stopped. Period N is ended; period N+1 has not started.
- Coach edits **draft assignments** with the same place / move / swap / off gestures as pending (these are not timed events).
- **Start period** writes `period_start` for period N+1 at 0:00 with whatever the draft field is then.
- If the coach starts the next period with no changes, the same seven (or nine) stay on.

### 5.7 After the final period

- Recap view on the same game: per present player, total on-field minutes, minutes by group (GK / DEF / MID / FWD), minutes by slot name. Bench time can be inferred (period lengths minus on-field) but is **not** a featured column in v1 — the point is minutes *played*, by position.
- Event log (time, type, who / which slots) so the coach can see what was recorded and edit a stamped time if they missed it.

### 5.8 Edit after the fact

- Change an event’s `at_ms` (typed game-clock time). Recompute minutes. Reject times that are out of order for that period.
- Cannot change who was in a `field_set` in v1 — undo and re-stage the pending field instead.
- Set-clock (§6.1) is the fix for a clock that does not match the ref; editing an event time is the fix for a Go that was stamped late.

---

## 6. Clock (detail)

Each period has its own 0:00.

| Action | Game-clock | Notes |
|--------|------------|-------|
| Start period | 0:00 | Event + clock running |
| **Go** | stamped `at_ms` | Defaults to current displayed elapsed; coach may type another time before confirm |
| Pause | frozen | `elapsed_ms` stored; `clock_running = false` |
| Resume | continues | `last_resumed_at = now` (UTC wall time) |
| End period | current elapsed | Event; clock not running |
| Refresh / lock screen while running | continues | `displayed = elapsed_ms + (now - last_resumed_at)` |

There is **no** planned duration and **no** auto-end at 25:00. The half is as long as it is.

Display: `M:SS` or `MM:SS` (e.g. `8:15`). Stored as integer milliseconds into the period so we do not accumulate rounding error.

### 6.1 Set / correct clock

Forgot Start, or started two minutes late, or left it running through a water break: the coach can **type the time the clock should show** (e.g. `12:00`).

- If running: set `elapsed_ms` to that value and `last_resumed_at` to now, so it continues from there.
- If paused: set `elapsed_ms` only.
- Reject a time **before** the latest event in this period (cannot rewind past a Go that already happened). To fix that, edit that event’s time or undo it first.
- Set-clock is **not** a field event. It does not change who is on. Minutes already closed on earlier events stay; open stints will end at whatever `period_end` / next `field_set` you stamp later.

### 6.2 Pocket, lock screen, failed saves

- Screen off does **not** pause the match clock. On unlock, recompute from stored `elapsed_ms` + `last_resumed_at`.
- Wake-lock only while the live page is visible, so it does not dim in your hand. It cannot and should not fight a pocketed lock screen.
- No offline queue in v1. No signal → save error, stay on the last successful server state, retry. Reconstruct later by typing times if needed.
- Accidental Go / End: Undo (End undo restores the period in progress). Accidental Pause: Resume.
- Do not use two tabs of the same game; last write wins.

---

## 7. Minutes (derived)

Replay events per period to build **stints**: `(player, slot_key, period, start_ms, end_ms)`.

- `period_start` opens a stint for each filled slot at 0.
- `field_set` at `at_ms` closes every open stint and opens a new stint for each filled slot in that event’s assignments (same instant for everyone who changed **or stayed** — stayers can be implemented as close+reopen on the same slot with no gap, or as “leave stint open if player+slot unchanged”; both yield the same minutes. Prefer **leave unchanged stints open** so a no-op slot does not split).
- `period_end` closes every open stint at `at_ms`.

**Minutes at a slot** = sum of stint lengths for that slot, shown in minutes (one decimal if we want 8.5, or `M:SS` — pick one display in implementation; **`M:SS` matching the clock** is the default).

**Minutes in a group** = sum of stints whose slot’s group is GK / DEF / MID / FWD.

**Total on-field** = sum of all of a player’s stints. A present player with no stints shows 0.

Season totals: same sums across all games on that team. Slot names can differ across games (if the coach renamed slots); group totals always roll up. Per-slot season totals group by **slot name string** (good enough for v1; if you rename LB to “Left Back” mid-season those rows will split — acceptable).

---

## 8. UI / mobile-first

- **All pages** (not only the live game) are laid out for a portrait phone first, then fine on a laptop. Do not design a wide desktop grid and squeeze it.
- Touch targets at least **44px** tall. Pitch slots and bench names are tappable, not tiny labels.
- Hub chrome should not steal the live screen; keep it minimal there.
- Pending vs live must be obvious at a glance (highlight diffs, not a second tiny pitch).
- No hover-only actions, no drag-and-drop as the only way to move a player (tap-tap is the gesture).
- CSS classes use the `scm-` prefix.
- Live actions: vanilla JS, AJAX, no full page reload on Go / pause / pending edits.

---

## 9. Non-goals (v1)

- Auto-rotation / “sub every 8 minutes”
- Fairness engine, targets (40/50/60%), color bars, suggested next sub
- Parent sharing, co-coach, assistant login
- Goals, assists, cards, score, shots
- Late arrival / leave early / injury status as first-class (whole-game absent only)
- Copy starting XI from last game
- Preferred / avoided positions per player
- Multiple formations per team, or changing shape mid-game
- 0 or 2+ GK slots
- Print / PDF / CSV
- Offline PWA / native app
- Haptics, lock-screen live activity, sub notifications
- Cross-season player identity
- Shared tables with Baseball Lineup

---

## 10. Technical notes

- **Stack:** Flask, Postgres, existing hub auth. Vanilla JS on the live screen (no React). AJAX for live actions so the page does not reload on every sub.
- **Tables:** `scm_*` prefix. **CSS:** `scm-` class prefix. **URL:** `/soccer-minutes`.
- **Project id:** `soccer_minutes`.
- **Events are never updated except `at_ms`.** Undo = delete newest event (a `field_set` undoes as one). Field picture and minutes are always recomputed from the log.
- **Pending assignments** live on the game. **Save them on every place / move / swap / off / Reset**, not only on Go. Refresh or a killed tab must restore the staged picture. They are not minutes until **Go** writes a `field_set`.
- **Failed saves** must be visible (toast / banner). Do not update local live/pending as if the server accepted.
- **Wake Lock API** while the live view is visible and `clock_running`. Ignore if the browser refuses (desktop, unsupported).
- **No offline mode in v1.** Needs network for every save.
- **Draft assignments** (`{slot_key: player_id}`) live on the game for pre-kickoff and between-period editing. `period_start` snapshots them into the event payload.
- **Formation JSON** uses stable `slot_key` values (`gk`, `def_0`, `mid_1`, …) so renaming a slot does not break events. See [`DATA_MODEL.md`](DATA_MODEL.md).
- **Migrations:** Coach runs `flask db migrate` / `flask db upgrade` after schema review. Do not hand-write migration files.

---

## 11. Implementation phases

Each phase ends at a manually testable point. **Stop after each phase.**

### Phase 0 — Skeleton + docs ← **done when this file lands**

- Project registered, login-gated placeholder page, this PRD, data model doc.
- No tables yet.

### Phase 1 — Teams, roster, formation

- Migration for the v1 schema.
- Team CRUD, including the formation editor (§4.3) and pitch preview.
- Roster CRUD with jersey numbers, reorder, and delete confirmation.

**Manual test:** On a narrow phone-width viewport (and a laptop is fine too): create “9U United / Fall 2026”, change formation to 3 DEF / 3 MID / 2 FWD, name the slots (LB, CB, RB, LM, CM, RM, ST, ST2 or LW/ST/RW), confirm the pitch shows four bands with those names. Create a second team as 7v7 2-3-1. Add players with and without jersey numbers, reorder two, delete one.

### Phase 2 — Games, attendance, starting field

- Game list, create game (date + opponent) copying team defaults.
- Per-game formation / period editor (locked after kickoff — nothing to lock yet).
- Attendance toggles.
- Draft assignments on the pitch + bench. Persist. No clock.

**Manual test:** Create a game, verify formation matches the team, change the game to a different FWD name and confirm team defaults are untouched, mark two players absent, put seven (or nine) on the pitch, reload, confirm the field and bench persist.

### Phase 3 — Live game

- Count-up clock, pause/resume, **set/correct clock**, start/end period.
- Pending field cloned from live; place / move / swap / off; **save pending each gesture**; diff list; **Go** (optional typed stamp) commits `field_set`; **Reset** recopies live; persist pending across refresh; undo whole `field_set`.
- Wake-lock while visible; failed-save error.

**Manual test:** Start a half. Put one bench kid on one slot, confirm live pitch and minutes unchanged, tap Go and confirm they changed together. Reset after staging two changes and confirm pending matches live again. Do the ABC slide (D for A; C off; B to C; E into B) without retouching other slots; Go once; confirm minutes. Refresh while pending differs from live and confirm pending is still there. Lock the phone for 30+ seconds with the clock running, unlock, confirm the clock jumped forward rather than resetting. Set the clock to `5:00` and confirm it continues from there. Undo the last Go. Type a different time on Go (e.g. `4:30` while the clock shows `5:00`) and confirm minutes use `4:30`.

### Phase 4 — Game recap

- Minutes by player / group / slot from the event log.
- Event list with editable times.

**Manual test:** After a two-period game with a couple of subs and a swap, check that each player’s group minutes add up to their on-field total, and that editing a sub from 8:00 to 10:00 moves the minutes.

### Phase 5 — Season totals

- Team-level rollup of the same minutes across games.

**Manual test:** Two games on the same team; confirm season totals are the sum, and a player who sat out game 2 (absent) is unchanged by that game.

### Backlog (post-v1)

- Copy last starting XI
- Late arrival / leave early
- Fairness view (still quiet, but vs a target %)
- Print-friendly recap
- Preferred positions
- Mid-game formation change
