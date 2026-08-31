"""CPU opponent for Battleship Online solo games."""

import random

CPU_PLAYER_ID = "__cpu__"
CPU_DISPLAY_NAME = "Computer"


def choose_random_shot(shots):
    """Pick a random un-fired cell from a shots grid."""
    candidates = []
    for row in range(len(shots)):
        for col in range(len(shots[row])):
            if shots[row][col] == 0:
                candidates.append((row, col))
    if not candidates:
        return None
    return random.choice(candidates)
