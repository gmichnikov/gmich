"""Mancala (Kalah) core game rules and logic.

Board layout (14 slots):
- 0..5: Player X pits (indices 0, 1, 2, 3, 4, 5)
- 6: Player X Kalah / Store
- 7..12: Player O pits (indices 7, 8, 9, 10, 11, 12)
- 13: Player O Kalah / Store

Rules configured:
- Initial seeds: 4 per pit (48 total seeds).
- Direction: Counter-clockwise (0 -> 1 -> ... -> 6 -> 7 -> ... -> 13 -> 0).
- Stores: Player drops seeds into their own store, skips opponent's store.
- Extra Turn: If the last seed drops into the current player's store, they get an extra turn.
- Empty-pit capture: Disabled per rules selection.
- End Game & Sweep: When either player has 0 seeds in all 6 of their pits, the game ends.
  The player who still has seeds sweeps all remaining seeds from their pits into their own store.
  Highest store count wins (or draw if equal).
"""

INITIAL_SEEDS_PER_PIT = 4
TOTAL_PITS = 14

P1_PITS = list(range(0, 6))      # [0, 1, 2, 3, 4, 5]
P1_STORE = 6
P2_PITS = list(range(7, 13))     # [7, 8, 9, 10, 11, 12]
P2_STORE = 13


def initial_board():
    """Return initial 14-element board array with 4 stones per pit and 0 in stores."""
    board = [INITIAL_SEEDS_PER_PIT] * TOTAL_PITS
    board[P1_STORE] = 0
    board[P2_STORE] = 0
    return board


def player_pits(seat):
    return P1_PITS if seat == "X" else P2_PITS


def player_store(seat):
    return P1_STORE if seat == "X" else P2_STORE


def opponent_store(seat):
    return P2_STORE if seat == "X" else P1_STORE


def is_side_empty(board, seat):
    """Check if all 6 pits for the given seat are empty."""
    pits = player_pits(seat)
    return all(board[p] == 0 for p in pits)


def check_game_over(board):
    """Return True if either side has no seeds left in their pits."""
    return is_side_empty(board, "X") or is_side_empty(board, "O")


def sweep_remaining(board):
    """
    Sweep any remaining stones in pits to their respective player's store.
    Modifies board in-place and returns swept counts dict: {"X": int, "O": int}.
    """
    swept_x = sum(board[p] for p in P1_PITS)
    swept_o = sum(board[p] for p in P2_PITS)

    for p in P1_PITS:
        board[p] = 0
    board[P1_STORE] += swept_x

    for p in P2_PITS:
        board[p] = 0
    board[P2_STORE] += swept_o

    return {"X": swept_x, "O": swept_o}


def determine_winner(board):
    """Return 'X', 'O', or 'draw' based on final store counts."""
    score_x = board[P1_STORE]
    score_o = board[P2_STORE]
    if score_x > score_o:
        return "X"
    elif score_o > score_x:
        return "O"
    return "draw"


def apply_move(board, pit_index, seat):
    """
    Execute a move for seat ('X' or 'O') starting from pit_index.

    Returns dict with:
      - board: new board list
      - extra_turn: bool
      - sown_steps: list of indices where stones were dropped (in order)
      - game_over: bool
      - winner: 'X', 'O', 'draw', or None
      - swept: {"X": int, "O": int} or None
      - last_pit: index where last stone landed
    """
    if seat not in ("X", "O"):
        raise ValueError(f"Invalid seat: {seat}")

    pits = player_pits(seat)
    if pit_index not in pits:
        raise ValueError(f"Pit index {pit_index} does not belong to seat {seat}")

    if board[pit_index] <= 0:
        raise ValueError(f"Pit {pit_index} has no stones to move")

    new_board = list(board)
    stones = new_board[pit_index]
    new_board[pit_index] = 0

    curr_idx = pit_index
    own_store = player_store(seat)
    opp_store = opponent_store(seat)
    sown_steps = []

    while stones > 0:
        curr_idx = (curr_idx + 1) % TOTAL_PITS
        # Skip opponent's store
        if curr_idx == opp_store:
            continue
        new_board[curr_idx] += 1
        sown_steps.append(curr_idx)
        stones -= 1

    last_pit = curr_idx
    extra_turn = (last_pit == own_store)

    # Check game over condition
    game_over = check_game_over(new_board)
    winner = None
    swept = None

    if game_over:
        swept = sweep_remaining(new_board)
        winner = determine_winner(new_board)
        extra_turn = False

    return {
        "board": new_board,
        "extra_turn": extra_turn,
        "sown_steps": sown_steps,
        "game_over": game_over,
        "winner": winner,
        "swept": swept,
        "last_pit": last_pit,
    }
