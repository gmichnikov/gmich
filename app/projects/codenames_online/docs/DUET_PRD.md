# Codenames Duet (2-Player Co-op Mode) — Product Requirements Document

**Status:** Proposed / Draft  
**Related PRD:** [Codenames Online PRD (Classic v1)](PRD.md)  
**Category:** [Live Multiplayer Games](/live-multiplayer-games)  
**Parent Project:** `codenames_online`

---

## 1. Overview & Vision

**Vision:** Play official **Codenames Duet** in person with **two phones** and **two players** (or two small cooperative teams). 

In Classic Codenames, two teams compete against each other, requiring at least 4 people (or an awkward 3-player variant). **Codenames Duet** turns Codenames into a cooperative, high-tension game for **exactly 2 players**:
- Both players sit across from each other, each holding their own phone.
- The two players work **cooperatively** as a team against a turn counter (Timer Tokens).
- Both players act as **both Spymaster and Guesser** during the game.
- Each phone acts as that player's private Key Card and interactive guessing screen.

**Why the 2-phone architecture is perfect:**  
In the physical board game, a double-sided plastic key card sits in a stand between the two players; Side A is visible only to Player 1, and Side B is visible only to Player 2. Our 2-seat room model (`seat_x` and `seat_o`) maps 1:1 to Side A and Side B with strict server-side fog-of-war secrecy.

---

## 2. Official Codenames Duet Rules Summary

### 2.1 The Board & The 15 Agents
- The board has **25 word cards** in a 5×5 grid (same as Classic).
- Across the whole board, there are **15 total unique Green Agents** that the team must uncover to win.
- Each player's key card shows **9 Green Agents**, **3 Black Assassins**, and **13 Tan Bystanders**.

### 2.2 The Key Card Overlap Matrix
The mathematical distribution between Side A (Player 1) and Side B (Player 2) is fixed and precise:

| Side A (Player 1 sees) | Side B (Player 2 sees) | Count | Gameplay Meaning |
|-------------------------|-------------------------|-------|------------------|
| **Green Agent** | **Green Agent** | **3** | Shared target! Both players want this word guessed. |
| **Green Agent** | Tan Bystander | **5** | Player 1 wants Player 2 to guess this. |
| Tan Bystander | **Green Agent** | **5** | Player 2 wants Player 1 to guess this. |
| **Green Agent** | **Black Assassin** | **1** | Green for P1, but instant death if P1 guesses it! |
| **Black Assassin** | **Green Agent** | **1** | Green for P2, but instant death if P2 guesses it! |
| **Black Assassin** | **Black Assassin** | **1** | Lethal to both players. |
| **Black Assassin** | Tan Bystander | **1** | Assassin for P1; neutral for P2. |
| Tan Bystander | **Black Assassin** | **1** | Assassin for P2; neutral for P1. |
| Tan Bystander | Tan Bystander | **7** | Neutral for both players. |
| **Total Cards** | | **25** | **15 unique Greens, 3 Assassins per player** |

*(Notice: 3 double-greens + 5 P1-only greens + 5 P2-only greens + 1 P1-green/P2-assassin + 1 P2-green/P1-assassin = **15 total green agents**).*

### 2.3 The Turn Loop
The game starts with a fixed number of **Timer Tokens** (standard is **9 turns**; 10 or 11 for beginners/casual play).

1. **Player 1 gives a clue aloud:** e.g. *"RIVER, 2"*.
2. **Player 2 guesses on their phone:**
   - Player 2 selects and confirms a tile.
   - The tile is checked against **Player 1's secret key**:
     - **Green Agent on P1's key:** Success! A Green Agent token covers the card for both players. Player 2 may make another guess or tap **"Done guessing"**.
     - **Tan Bystander on P1's key:** Miss. The card is marked as a bystander called by P1. The turn **ends immediately**.
     - **Black Assassin on P1's key:** Instant loss! The mission fails immediately for both players.
3. **Turn Consumption:**
   - Ending a turn (either via "Done guessing" or by hitting a bystander) consumes **1 Timer Token**.
   - If a bystander was hit, that bystander card permanently consumes that turn token.
4. **Roles Alternate:**
   - Player 2 now gives a clue aloud targeting words on Player 2's key.
   - Player 1 guesses on Player 1's phone.
5. **Win / Loss Conditions:**
   - **Win:** All **15 Green Agents** are uncovered before timer tokens run out.
   - **Loss (Assassin):** Either player touches an Assassin on the other player's key.
   - **Loss (Time Out):** Timer tokens reach 0 and not all 15 agents are uncovered (optional Sudden Death rules allow unprompted final guesses).

---

## 3. User Experience & Device Flows

### 3.1 Lobby & Setup
1. **Game Mode Selection:**
   - In room setup (or on game creation), the clue-giver chooses **Game Mode**:
     - `Classic (4+ players)` — default
     - `Duet (2 players)`
2. **Player Roles:**
   - In Duet mode, there is no "Clue-giver phone vs Guesser phone".
   - Instead, both phones are **Player phones**:
     - Phone 1 claims: **"I am Player 1"** (Seat X)
     - Phone 2 automatically becomes: **"Player 2"** (Seat O)
   - Names: Enter **Player 1 Name** and **Player 2 Name** (replaces Red/Blue spymasters).
   - Options:
     - **Turns / Timer Tokens:** Default `9` (options: `9`, `10`, `11`).
     - **Word List Picker** & **Exclude confusing words** (same as Classic).

### 3.2 In-Game View (Seat X vs. Seat O)
Each phone displays the 5×5 grid with a dual-layer representation:
1. **Their Own Secret Key (Unrevealed tiles):**
   - Soft translucent **Emerald Green** tint on the 9 words they want their partner to guess.
   - Dark **Charcoal / Skull badge** on their 3 Assassins (words their partner must NEVER guess).
   - Neutral soft gray on the other 13 Bystander cards.
2. **Public Revealed Board (Both players see):**
   - **Found Agents:** Bright solid emerald green card with a white checkmark badge (`✓ AGENT`).
   - **Found Bystanders:** Soft tan card marked with an indicator showing who found the bystander (e.g. `Bystander (called by Sarah)`).
   - **Assassin Hit:** Solid black card with skull badge (`💀 ASSASSIN`).
3. **Turn Bar & Interaction Gating:**
   - When it is **Player 1's turn to guess**:
     - **Player 1 phone:** Bottom bar highlights in Emerald Green: *"Your turn to guess! Tap words to select"* + **"Done guessing"** button. Cards are interactive (two-tap confirmation).
     - **Player 2 phone:** Bottom bar shows: *"Sarah is guessing…"* (Tiles are read-only).
   - When Player 1 passes or hits a bystander, turn immediately swaps:
     - **Player 2 phone:** Becomes active for guessing.
     - **Player 1 phone:** Becomes passive / waiting.

### 3.3 Scoreboard HUD
Both phones show a persistent, prominent Duet HUD:
- **Agents Found:** `8 / 15 Agents Found` (with a visual progress bar or badge counter).
- **Turns Left:** `4 Turns Remaining` (or pill icons that deplete from 9 down to 0).

### 3.4 Post-Game Full Debrief
When the game ends (either Victory or Defeat):
- A **"Show Mission Debrief"** toggle reveals the overlap matrix:
  - Highlights which 3 cards were shared Greens for both players.
  - Highlights the 1 assassin that was green for the partner!
  - Displays victory stats: *"Mission Accomplished with 2 turns remaining!"* or *"Mission Failed: Hit Assassin [WORD] on Turn 4"*.

---

## 4. Technical Architecture & Delta from Classic

### 4.1 Database Changes (`CodenamesOnlineRoom`)

Requires adding 4 new columns to `CodenamesOnlineRoom` via a Flask-Migrate script:

```python
# app/projects/codenames_online/models.py

class CodenamesOnlineRoom(db.Model):
    # Existing columns ...
    game_mode = db.Column(db.String(10), nullable=False, default="classic")  # "classic" | "duet"
    key_x = db.Column(db.JSON, nullable=True)          # 25-element list for Seat X in Duet
    key_o = db.Column(db.JSON, nullable=True)          # 25-element list for Seat O in Duet
    turns_remaining = db.Column(db.Integer, nullable=True, default=9)
    turns_total = db.Column(db.Integer, nullable=True, default=9)
```

*(Note: For Classic mode, `key` continues to be used. For Duet mode, `key_x` and `key_o` store the two separate keys).*

### 4.2 Game Logic Additions (`game_logic.py`)

#### A. Key Generation: `generate_duet_keys()`
Generates the exact official 25-card distribution:
```python
def generate_duet_keys():
    """
    Returns (key_x, key_o, first_turn)
    Exact Codenames Duet distribution across 25 tiles:
      3: Green / Green
      5: Green / Neutral
      5: Neutral / Green
      1: Green / Assassin
      1: Assassin / Green
      1: Assassin / Assassin
      1: Assassin / Neutral
      1: Neutral / Assassin
      7: Neutral / Neutral
    """
    pairs = (
        [("green", "green")] * 3 +
        [("green", "neutral")] * 5 +
        [("neutral", "green")] * 5 +
        [("green", "assassin")] * 1 +
        [("assassin", "green")] * 1 +
        [("assassin", "assassin")] * 1 +
        [("assassin", "neutral")] * 1 +
        [("neutral", "assassin")] * 1 +
        [("neutral", "neutral")] * 7
    )
    random.shuffle(pairs)
    key_x = [p[0] for p in pairs]
    key_o = [p[1] for p in pairs]
    first_turn = random.choice(["X", "O"])
    return key_x, key_o, first_turn
```

#### B. Guess Resolution: `apply_duet_guess(room, index, guessing_seat)`
```python
def apply_duet_guess(room, index, guessing_seat):
    # If seat X is guessing, evaluate against partner's key (key_o)
    partner_key = room.key_o if guessing_seat == "X" else room.key_x
    target_type = partner_key[index]

    if target_type == "assassin":
        room.status = room.STATUS_WON  # or STATUS_LOST
        room.winner = "defeat_assassin"
        return

    if target_type == "green":
        # Card becomes revealed as an Agent
        room.revealed[index] = "green"
        # Check if all 15 greens are found
        # (A card is one of the 15 greens if it is green on either key_x or key_o)
        greens_found = sum(1 for i, r in enumerate(room.revealed) if r == "green")
        if greens_found >= 15:
            room.status = room.STATUS_WON
            room.winner = "victory"
        # Turn stays with current guessing_seat (may guess again or pass)
        return

    if target_type == "neutral":
        # Card is revealed as a bystander
        room.revealed[index] = f"neutral_{guessing_seat.lower()}"
        # Consumes turn token and swaps turn
        room.turns_remaining -= 1
        if room.turns_remaining <= 0 and room.winner != "victory":
            room.status = room.STATUS_WON
            room.winner = "defeat_timeout"
            return
        # Switch turn to the other player
        room.turn = "O" if guessing_seat == "X" else "X"
```

#### C. End Turn: `end_duet_turn(room, player_id)`
When a player taps **"Done guessing"**:
- Decrements `room.turns_remaining -= 1`.
- If `room.turns_remaining <= 0`: trigger `defeat_timeout` (or Sudden Death).
- Switches active guessing seat (`X` $\leftrightarrow$ `O`).

### 4.3 Serialization & Fog-of-War (`serialize.py`)

Strict fog-of-war is maintained during gameplay:
- **Active Game:**
  - Player X receives `my_key: key_x` (never receives `key_o`).
  - Player O receives `my_key: key_o` (never receives `key_x`).
  - Both players receive `revealed` array, `turns_remaining`, `agents_found` count, and `turn`.
- **Game Over (Won / Lost):**
  - Both players receive both `key_x` and `key_o` to render the mission debrief.

```python
# serialize.py snippet for Duet
if room.game_mode == "duet":
    payload["game_mode"] = "duet"
    payload["turns_remaining"] = room.turns_remaining
    payload["turns_total"] = room.turns_total
    payload["agents_found"] = sum(1 for r in room.revealed if r == "green")
    
    if room.status in (CodenamesOnlineRoom.STATUS_WON, CodenamesOnlineRoom.STATUS_LOST):
        payload["key_x"] = room.key_x
        payload["key_o"] = room.key_o
    else:
        payload["my_key"] = room.key_x if viewer_seat == "X" else room.key_o
```

### 4.4 Frontend Components (`room.js`, `style.css`, `room.html`)

1. **Setup Mode Switcher:**
   - Clean radio/segmented button in `cnoSetupPanel`: `Classic` vs `Duet`.
   - In Duet mode, labels change to "Player 1 (This phone)" and "Player 2 (Other phone)".
2. **Duet Visual Theme:**
   - Uses emerald green accents (`#27ae60` / `#2ecc71`) and midnight charcoal.
   - Distinct badges for player's secret keys:
     - Player's unrevealed target words: dotted green border + subtle green background.
     - Player's unrevealed assassin words: subtle skull icon in corner.
3. **Two-Tap Guessing:**
   - Reuses the existing robust two-tap confirmation UX already built for Classic mode.
4. **Turn Banner & HUD:**
   - Displays live agent counter: `🌿 10/15 Agents Found`
   - Displays live timer tokens: `⏳ 3 Turns Left`
   - Shows active instruction: `"Sarah's turn to guess"` or `"Waiting for Mike's clue..."`.

---

## 5. Implementation Phasing Plan

When ready to implement, this feature can be deployed in 4 sequential phases:

### Phase 1: Database & Migration
- Add `game_mode`, `key_x`, `key_o`, `turns_remaining`, `turns_total` to `CodenamesOnlineRoom`.
- Generate migration script via `flask db migrate` and apply with `flask db upgrade`.
- *Manual test:* Verify database columns exist and existing Classic rooms are unaffected.

### Phase 2: Core Duet Game Logic & Engine
- Implement `generate_duet_keys()` with unit test assertions confirming the 15-green and 3-assassin overlap distribution.
- Implement `apply_duet_guess()` and `end_duet_turn()` in `room_service.py`.
- Update `serialize.py` to enforce asymmetric key fog-of-war.
- *Manual test:* Run backend tests simulating a full Duet game sequence via Python shell.

### Phase 3: Setup UI & Lobby Mode Selection
- Add mode selection toggle to room setup on clue-giver phone.
- Adapt name fields and role assignment for Duet (Player 1 / Player 2).
- *Manual test:* Create a Duet room with 2 devices; verify each device receives its own distinct secret key.

### Phase 4: Duet Board UI, HUD, & Post-Game Debrief
- Add the Duet HUD (Agents Found progress counter + Turns Remaining counter).
- Render private key tints on unrevealed cards (greens and assassins).
- Style revealed agents and bystander tokens.
- Add post-game victory/defeat debrief showing the full overlap matrix.
- *Manual test:* Play a complete 2-player Duet game end-to-end on two phones.
