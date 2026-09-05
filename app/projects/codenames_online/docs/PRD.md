# Codenames Online — Product Requirements (v1)

**Status:** Planning only — no routes or DB yet.  
**Category:** [Live Multiplayer Games](/live-multiplayer-games)  
**Related code:** Same room patterns as `tic_tac_toe_online` and `battleship_online`.

---

## 1. Overview

**Vision:** Play competitive Codenames in person with **two phones** and **four people**. Both spymasters share the **clue-giver phone** (full key). All guessers share the **guesser phone** (words only). Clues and numbers are spoken aloud in v1 — the app is the shared board and referee.

**Why two phones, not four:** In the board game, both spymasters already share one key card. Grouping both spymasters on one device and all guessers on another preserves secrets *between* phones, not within them.

**Engine fit:** Uses the existing **2-seat** room model (seat X = Spy, seat O = Guesser), server-authoritative JSON state, 1s polling, POST `/join`, per-seat serialize (like Battleship fog-of-war).

---

## 2. Players & devices

| | Clue-giver phone (seat X) | Guesser phone (seat O) |
|--|---------------------------|------------------------|
| **Who** | Both spymasters | All guessers (both teams) |
| **Sees (unrevealed)** | Word + team color | Word only |
| **Sees (revealed)** | Word + color | Word + color |
| **Actions (v1)** | View only | Tap guesses, “Done guessing” |

| People | Devices | Works? |
|--------|---------|--------|
| 4 (2 spies + 2 guessers) | 2 | **Target setup** |
| 4+ (extra guessers) | 2 | OK — crowd around guesser phone |
| 2 (1 spy + 1 guesser) | 2 | Awkward — not the intended experience |

---

## 3. Resolved product decisions

| Topic | Decision |
|-------|----------|
| **Clues in v1** | Spoken out loud only — **no clue/number UI** |
| **App responsibilities** | Show boards, handle guesses, enforce reveal rules, end turn |
| **Devices** | Exactly **2 phones** — clue-giver phone + guesser phone |
| **Guess count vs spoken number** | **Honor system** — app does not enforce “bird, 2” |
| **Turn end** | Auto on wrong color / neutral / assassin; manual **“Done guessing”** to pass |
| **Key visibility** | Never sent to guesser client for unrevealed tiles |
| **Architecture** | Postgres room row, poll state, rematch in same room |
| **Join flow** | Creator shares link → second device joins → **both devices in room** → one taps **“Clue-giver phone”** → other is guesser phone automatically |
| **Role assignment** | No roles until both devices joined. **One tap** assigns clue-giver vs guesser. No key/board until setup on clue-giver phone is done. |
| **Spectators** | Low priority — extra visitors get guesser view (no key leak). No special UX. |
| **Word lists** | **Multiple list files** uploaded/bundled, each with a **display name**. Picker in lobby; one list marked **default** for new rooms. |
| **Key layout** | Standard: 9 of one color, 8 of the other, 7 neutral, 1 assassin |
| **Team colors** | Which side is red vs blue is **random** each game. **First turn** = team with **9 cards** (official rule). |
| **Rematch** | New 25-word board from the **same word list** (pre-selected). User **confirms** before deal. |
| **Who can tap** | **Honor system** — guessers share one phone; app cannot know which humans are on which team. All guesser taps accepted during the active **team** turn; no per-player gating. |
| **Turn clarity** | Teams are tied to **spymaster names** on the clue-giver phone. Guesser phone shows whose turn (name + color). Fixed **bottom turn bar** on both phones. |
| **Spymaster names** | Clue-giver phone: enter **Red spymaster** and **Blue spymaster** names. Shown on guesser phone during that team’s turn. |
| **Done guessing** | Guesser phone only; allow pass with 0 guesses |
| **Mis-taps** | No undo v1; ignore taps on already-revealed tiles |
| **Rematch trigger** | Either device can start rematch flow (confirmation step) |
| **Colorblind** | Patterns on revealed tiles (not color alone) |
| **Spy remaining counts** | Show on clue-giver phone only (e.g. “5 red left”) |
| **Language** | English only v1 |
| **Product name** | **Codenames** (homepage + in-app). URL slug: `/codenames-online/`. Personal/family site — see §10. |
| **Start game** | **Clue-giver phone only** — they run setup; guesser phone shows “Waiting to start…” |
| **Creator join** | Creator auto-claims first device seat on room create (same as TTTO/Battleship) |

---

## 4. Setup flow (the whole game start)

This is the flow — no hidden steps:

```
1. Person A creates game, shares link
2. Person B opens link on another device → both devices are in the room
3. One device taps “Clue-giver phone” → the other becomes “Guesser phone”
4. On clue-giver phone: pick word list, enter both spymaster names (one per color)
5. Deal board → team with 9 cards goes first → play
```

### Step 1–2: Get both devices in the room

1. **Person A** creates a room (POST `/rooms`) and shares the link or 6-character code.
2. **Person B** opens that link on a **second device** and joins (POST `/join`).
3. Until step 2 completes, the room shows **waiting for second device**. No roles, no board, no key.

Same join mechanics as Tic-Tac-Toe Online / Battleship (POST `/join` only — link alone does not claim a seat).

### Step 3: Pick which phone is which

1. Once **both devices** are in, the lobby shows **“Choose phone roles.”**
2. **Either device** taps **“This is the clue-giver phone.”**
3. That device becomes the **clue-giver phone**; the other device automatically becomes the **guesser phone**.
4. The guesser phone shows a read-only confirmation: **“You are the guesser phone.”**

There is no separate “pick guesser” step — claiming clue-giver assigns both roles.

### Step 4: Clue-giver phone setup (both spymasters at this phone)

On the **clue-giver phone only:**

1. **Word list** — picker with named lists; default pre-selected.
2. **Spymaster names** — two fields, one per color (e.g. Red = “Sarah”, Blue = “Mike”). These are the two people giving clues at this phone.
3. Tap **Start game** when ready (**clue-giver phone only**).

The **guesser phone** shows the two spymaster names once entered, plus **“Waiting for {name} to start…”** until the board deals. It does not show the key.

### Step 5: Deal and first turn

1. Server deals 25 words from the chosen list and a random key (9 / 8 / 7 / 1).
2. Red vs blue placement on the key is **random** each game.
3. **First turn** = whichever color has **9 cards** on the key (official Codenames rule).
4. Clue-giver phone sees the full colored grid. Guesser phone sees words only.
5. Turn bar on both phones: **“{Spymaster name}’s turn ({Color})”** — play begins.

### Edge case: picked the wrong phone before Start

If someone tapped clue-giver on the wrong device **before Start game**, either device can tap **Swap phone roles** in the lobby. After the board is dealt, roles are locked for that game.

---

## 5. Turn flow (every moment)

```
Lobby (2 devices) → Role claim → Word list + names → Deal → [Team turn loop] → Win → Rematch?
```

### 5.1 Lobby (steps 1–4 above)

See §4 — no separate lobby logic beyond that flow.

### 5.2 Deal (step 5)

1. Server picks 25 words from selected list + random key (standard counts).
2. Server randomly assigns which key color is red vs blue; **team with 9 cards goes first**.
3. Clue-giver phone: full 5×5 colored grid + spymaster names.
4. Guesser phone: 5×5 words only + spymaster names in turn bar.

### 5.3 Active team turn (e.g. Red — spymaster “Sarah”)

| Step | Physical world | Clue-giver phone | Guesser phone |
|------|----------------|------------------|---------------|
| 1 | Sarah gives clue + number ** aloud** | Turn bar: “Sarah’s turn (Red)” | Turn bar: “Sarah’s turn (Red) — tap to guess” |
| 2 | Guessers discuss (honor: only Red taps) | Sees reveals sync in | Anyone on phone can tap |
| 3 | Each tap | Tile flips on both when poll syncs | Same |
| 4a | Own color | Turn continues | Can tap again |
| 4b | Opponent / neutral | Turn ends → Blue | Turn ends |
| 4c | Assassin | Game over, Blue wins | Game over |
| 5 | Guessers done early | — | **“Done guessing”** → Blue’s turn |

### 5.4 Win & rematch

- **Win:** All of one team’s words revealed → that team wins.
- **Assassin:** Opposite team wins immediately.
- **Rematch:** Same word list pre-selected; user confirms → new 25 words + new random key/colors.

---

## 6. Rules (server-enforced)

On `POST /guess` with `index` (0–24):

1. Game must be **active**.
2. Must be **active team’s turn** (reject with friendly message if wrong team’s turn — not “who tapped”).
3. Card must not already be **revealed** (ignore silently).
4. Reveal card; append to state.
5. Apply outcome:
   - **Same as `turn`** → stay same team.
   - **Opposite team color** → switch `turn`.
   - **Neutral** → switch `turn`.
   - **Assassin** → `status = won`, `winner = opposite team`.
6. If all team tiles for either side revealed → `status = won`, appropriate `winner`.

On `POST /end_turn`:

1. Game active, active team’s turn.
2. **Guesser phone only.**
3. Switch `turn`.

**Honor system (not enforced):** Which humans tap on the guesser phone; clue number vs guess count.

---

## 7. Per-seat UI (v1)

### Clue-giver phone

- 5×5 grid: unrevealed show **word + background color**; revealed show flipped styling + patterns.
- **Spymaster name fields** (Red / Blue) in lobby; editable until game starts.
- Turn bar: **“{Name}’s turn ({Color})”** + remaining counts per team.
- Read-only for guesses (no tile taps that affect game).
- Word list picker + **Start game** (clue-giver phone only) before first deal; **Rematch** with confirm after win.

### Guesser phone

- 5×5 grid: unrevealed **word only**; revealed show **color/pattern**.
- All unrevealed tiles tappable; revealed tiles visually **dead** (dimmed, no tap).
- **Done guessing** only in bottom bar **during active turn** — hidden otherwise.
- Turn bar: **“{Name}’s turn ({Color})”** — prominent; both spymaster names in lobby.
- Pre-start: **“Waiting to start…”** while clue-giver finishes setup.

### Both

- Room code, link to home.
- Lobby: **Swap phone roles** before Start (edge case only).
- Setup hint (first visit, dismissible): “Clue givers: this phone. Guessers: other phone.”

---

## 8. UX — smooth, simple, fun

Design goal: **get four people playing in under a minute** with almost no explanation. The app stays out of the way; the table talk is the game.

### 8.1 One job per screen

Each lobby phase gets **one primary action** — no forms and choices competing for attention.

| Phase | What you see | Primary action |
|-------|----------------|----------------|
| Waiting for 2nd device | Room code + share hint | **Share link** (copy or native share) |
| Both devices in | “Who’s which phone?” | **Clue-giver phone** (single button) |
| Setup (clue phone) | List picker + two name fields | **Start game** |
| Setup (guesser phone) | Names + waiting message | — (read-only) |
| Playing | Grid + turn bar | Tap words / **Done guessing** |
| Won | Winner + rematch | **Play again** |

### 8.2 Turn bar is the hero

Both phones share a **fixed bottom bar** (Battleship pattern):

- **Active team color** as background stripe (red / blue).
- Large text: **“Sarah’s turn”** with small **“(Red)”** — spymaster name is what humans say aloud.
- Clue-giver phone adds compact **“5 Red · 4 Blue left”** counts.
- On turn change: brief highlight pulse so everyone at the table notices without staring at the phone.

### 8.3 Grid feel

- Words in **ALL CAPS** (matches the board game, easier to read across a table).
- **Quick flip** on reveal (~200ms) — satisfying, not slow.
- Revealed tiles: color + pattern, slightly dimmed, clearly not tappable.
- Unrevealed guesser tiles: high contrast, finger-sized tap targets on mobile.
- Clue-giver grid: soft team tint on unrevealed tiles; assassin never labeled (just looks like a team color until revealed — same as physical key).

### 8.4 Gentle feedback, no nagging

- Wrong team’s turn + tap on guesser phone → **small toast**: “Mike’s turn (Blue)” — not a modal.
- Assassin hit → turn bar turns dramatic for 2s, then win screen.
- All team words found → simple win moment; no confetti overload.
- Already-revealed tap → ignore silently.

### 8.5 Share & rejoin

- **Copy link** + **Share** (mobile `navigator.share` when available) on the waiting screen.
- Room code shown large; link in clipboard is the happy path.
- `localStorage` player id → refresh or brief disconnect **rejoins same seat** automatically.

### 8.6 Keep v1 minimal

- No accounts, no chat, no clue typing, no settings page.
- No tutorial carousel — one dismissible line per phone role is enough.
- Compact header during play (code small, like Battleship battle mode).
- Word list picker is a simple `<select>` or button list — not a catalog UI.

### 8.7 Rematch flow

1. Either phone taps **Play again** after win.
2. Clue-giver phone sees confirm: same word list pre-selected, can change list.
3. Names carry over; editable before deal.
4. **Start game** → new 25 words + new key.

---

## 9. Technical sketch

### 9.1 Routes (follow TTTO/Battleship)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/codenames-online/` | Landing |
| POST | `/codenames-online/rooms` | Create room |
| GET | `/codenames-online/room/<code>` | Page shell |
| POST | `/codenames-online/room/<code>/join` | Claim device seat (no role yet) |
| POST | `/codenames-online/room/<code>/claim_role` | `{ role: "clue_giver" }` or `{ swap: true }` |
| POST | `/codenames-online/room/<code>/setup` | `{ word_list_id, name_red, name_blue }` — clue-giver only |
| POST | `/codenames-online/room/<code>/start` | Deal board — **clue-giver phone only** |
| GET | `/codenames-online/room/<code>/state` | Poll |
| POST | `/codenames-online/room/<code>/guess` | `{ index: 0–24 }` |
| POST | `/codenames-online/room/<code>/end_turn` | Pass |
| POST | `/codenames-online/room/<code>/rematch` | Confirm rematch → new board, same list |

Player identity: `localStorage` + `X-CNO-Player-Id` header (same pattern as TTTO/BSO).

CSS prefix: **`cno-`**.

### 9.2 Room state (JSON columns)

```json
{
  "words": ["Apple", "…25"],
  "key": ["red", "blue", "neutral", "…25"],
  "revealed": [false, "…25"],
  "turn": "red",
  "status": "waiting_devices | waiting_roles | waiting_start | active | won",
  "winner": "red | blue | null",
  "word_list_id": "default",
  "name_red": "Sarah",
  "name_blue": "Mike",
  "phone_role_x": "clue_giver | guesser | null",
  "phone_role_o": "clue_giver | guesser | null",
  "seat_x": "player_id | null",
  "seat_o": "player_id | null"
}
```

Word list assets live in `word_lists/`:

| File | Purpose |
|------|---------|
| `manifest.json` | Catalog: `{ "lists": [{ "id", "name", "word_count", "default?" }] }` |
| `<id>.json` | `{ "words": ["APPLE", …] }` — min **25** unique words; **400** typical |

**Shipped lists:**

| id | name | words | default |
|----|------|-------|---------|
| `base400` | Base400 | 400 | yes |
| `base800` | Base800 | 800 | no (superset of Base400 — adds 400 words) |
| `darktwinge832` | DarkTwinge832 | 832 | no |

Loader: `app/projects/codenames_online/word_lists.py` (`list_word_lists`, `load_word_list`, `default_word_list_id`).

To add a list: drop `<id>.json`, add an entry to `manifest.json`. Multi-word entries are one string (e.g. `"ICE CREAM"`).

### 9.3 Serialize (`room_to_dict`)

| Viewer | Payload |
|--------|---------|
| **Clue-giver phone** | Full `words`, `key`, `revealed`, `turn`, `status`, `winner`, names, remaining counts |
| **Guesser phone** | `words`, `revealed` (+ colors only for revealed indices), `turn`, names — no unrevealed `key` |
| **Spectator / unseated** | Same as guesser |

### 9.4 DB

Table `codenames_online_room` — same lifecycle fields as other online games (`code`, seats, `version`, `updated_at`, 14-day idle cleanup).

**Migration:** User runs `flask db migrate` / `upgrade` — do not hand-create migration files in agent sessions.

---

## 10. Naming & trademark

**Decision:** Display name **Codenames** on the homepage and in-app. Acceptable for personal/family use on gregmichnikov.com.

“Codenames” is a registered board game (Czech Games Edition). If the site ever goes broader than friends/family, revisit with a generic public name.

---

## 11. v1 out of scope

- Typed clues + number entry and validation
- Enforcing guess count from spoken clue
- Timer per turn
- Per-guesser player accounts on the guesser phone
- In-app chat
- Codenames Duet (2-player co-op)
- WebSockets (polling only)

---

## 12. v2+ backlog

- Clue log on clue-giver phone (type clue + number)
- Optional timer
- Word list admin UI (upload new packs without deploy)
- Duet mode
- Shared engine extraction under `live_multiplayer/`

---

## 13. Implementation checklist (when starting build)

- [ ] `app/projects/codenames_online/` — models, room_service, serialize, routes, templates, static
- [ ] Register blueprint + model import in `app/__init__.py`
- [ ] Registry entry under `live_multiplayer_games`
- [x] Word list manifest + Base400 default pack
- [ ] Manual test: 2 browsers as spy/guesser; 4 humans optional

---

## 14. References

- Backlog context: [`../live_multiplayer/docs/GAME_IDEAS.md`](../live_multiplayer/docs/GAME_IDEAS.md)
- Room patterns: `app/projects/tic_tac_toe_online/`, `app/projects/battleship_online/`
