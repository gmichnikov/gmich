# Live multiplayer game ideas

Backlog for games that fit the **room engine** used by Tic-Tac-Toe Online and Battleship Online:

- Shareable link + 6-char room code
- POST `/join` (no auto-join on page load)
- `localStorage` player id + header
- Server-authoritative state in Postgres
- 1s polling (pause when tab hidden)
- 2 seats + read-only spectators
- Rematch in same room

## Fit criteria

**Good fit:** turn-based, one discrete action per turn, state fits in JSON, 2 players (or 2 + spectators).

**Poor fit without WebSockets:** real-time reflexes (Pong, typing races, rhythm games).

**Harder:** 4+ required players, long sessions needing mid-game save.

---

## Tier S — build next (high fun / low pain)

| Game | Notes |
|------|--------|
| **Connect 4 Online** | Local Connect 4 exists; drop-in-column, win detection |
| **Gomoku** | 5-in-a-row; TTTO but bigger board |
| **Ultimate tic-tac-toe** | 9 sub-boards; viral, same stack |
| **Mancala / Kalah** | Pit counts in one array |
| **Mastermind duel** | Codemaker vs guesser; solo Mastermind exists |
| **Yahtzee duel** | Category race; Yahtzee scorer exists |
| **Dots and Boxes** | Line drawing, close boxes |
| **Checkers** | 8×8, simpler than chess |
| **Wordle race** | Same word, fewest guesses |
| **20 Questions** | Yes/no; chat-like UI |
| **Hangman duel** | One word, alternating rounds |

---

## Tier A — great but more design

| Game | Notes |
|------|--------|
| **Reversi / Othello** | 8×8 flip logic |
| **Quoridor** | Move pawn or place wall |
| **Onitama** | 5×5 + move cards |
| **Coup / Love Letter (2p)** | Small deck, bluff |
| **Liar's Dice (2p)** | Hidden dice, bids |
| **Codenames Online** | 2-device spy/guesser — [PRD](../codenames_online/docs/PRD.md) (planning) |
| **Carcassonne lite** | Tile placement |
| **Stratego lite** | Hidden ranks, 8×8 |
| **Bulls and Cows** | Number Mastermind |
| **Notakto** | Misère tic-tac-toe |

---

## Tier B — possible, chunky

| Game | Notes |
|------|--------|
| **Go (9×9)** | Simple rules, big state |
| **Shogi / Xiangqi** | Chess-family |
| **Blokus (2p)** | Polyomino placement |
| **Santorini** | Move + build |
| **UNO / Crazy Eights lite** | Hands server-side |
| **Ticket to Ride lite** | Route claiming |
| **Risk micro** | Few territories only |

---

## Word & party

| Game | Notes |
|------|--------|
| **Word chain** | Last letter → next word |
| **Categories / Scattergories** | Same letter, compare lists |
| **Balderdash** | Fake definitions |
| **Trivia / Jeopardy duel** | Pick category, take turns |
| **Geography higher-or-lower** | Async turns OK |

---

## Dice & luck

| Game | Notes |
|------|--------|
| **Farkle / Pig** | Push-your-luck |
| **Ship, Captain, Crew** | Quick 2p dice |
| **War (cards)** | Flip and compare |

---

## Game-night utilities (not clones)

Leverage existing hub projects; same room pattern:

| Idea | Existing project |
|------|------------------|
| **Shared scoreboard room** | Generic +1 tracker |
| **Dice roller room** | `dice_roll` |
| **Synced timer room** | `hourglass_timer` |
| **Randomizer room** | `randomizer` |
| **Bowling head-to-head** | `bowling` tracker |
| **Whiteboard room** | Strokes in JSON |

---

## Already shipped

- [x] **Tic-Tac-Toe Online** — `/tic-tac-toe-online`
- [x] **Battleship Online** — `/battleship-online`

---

## Suggested build order (original short list)

1. Connect 4 Online
2. ~~Battleship~~ ✓
3. Gomoku
4. Mastermind duel

---

## Codenames Online

**Full spec:** [`../codenames_online/docs/PRD.md`](../codenames_online/docs/PRD.md)  
Planning-only project folder: `app/projects/codenames_online/`.

Summary: 4 people, 2 phones (Spy + Guesser seats), verbal clues in v1, app handles board + guesses + done.

---

## Notes
- Shared engine extraction (optional someday): `room_service` patterns, player id, serialize per-viewer, cleanup
- Mobile: one board at a time + bottom turn bar (Battleship)
