import random

from app.projects.codenames_online.confusing_words import get_confusing_set, normalize_word
from app.projects.codenames_online.word_lists import BOARD_SIZE, load_word_list

KEY_COLORS = ("red", "blue", "neutral", "assassin")


def generate_key():
    """Return (key list, first_turn) where first_turn has 9 cards."""
    nine_color = random.choice(["red", "blue"])
    eight_color = "blue" if nine_color == "red" else "red"
    key = [nine_color] * 9 + [eight_color] * 8 + ["neutral"] * 7 + ["assassin"]
    random.shuffle(key)
    return key, nine_color


def _filter_pool(word_list_id, exclude_confusing, exclude_words):
    pool = list(load_word_list(word_list_id))
    if exclude_confusing:
        confusing = get_confusing_set()
        pool = [w for w in pool if w not in confusing]
    if exclude_words:
        blocked = {normalize_word(w) for w in exclude_words}
        pool = [w for w in pool if w not in blocked]
    return pool


def pick_board_words(word_list_id, exclude_confusing, exclude_words=None):
    pool = _filter_pool(word_list_id, exclude_confusing, exclude_words)
    if len(pool) < BOARD_SIZE:
        raise ValueError(
            f"Need at least {BOARD_SIZE} words in pool; got {len(pool)}."
        )
    return random.sample(pool, BOARD_SIZE)


def pick_replacement_word(word_list_id, exclude_confusing, current_words, replacing_index):
    blocked = list(current_words)
    if replacing_index is not None:
        blocked[replacing_index] = None
    blocked = [w for w in blocked if w]
    pool = _filter_pool(word_list_id, exclude_confusing, blocked)
    if not pool:
        raise ValueError("No replacement words available.")
    return random.choice(pool)


def remaining_counts(key, revealed):
    counts = {"red": 0, "blue": 0}
    for idx, color in enumerate(key or []):
        if color in counts and not (revealed or [False] * BOARD_SIZE)[idx]:
            counts[color] += 1
    return counts


def all_team_revealed(key, revealed, team_color):
    for idx, color in enumerate(key or []):
        if color == team_color and not (revealed or [False] * BOARD_SIZE)[idx]:
            return False
    return True


def apply_guess(room, index):
    """Mutate room after revealed[index] was set True."""
    color = room.key[index]
    if color == "assassin":
        room.status = room.STATUS_WON
        room.winner = "blue" if room.turn == "red" else "red"
        return

    if color != room.turn:
        room.turn = "blue" if room.turn == "red" else "red"

    if all_team_revealed(room.key, room.revealed, "red"):
        room.status = room.STATUS_WON
        room.winner = "red"
    elif all_team_revealed(room.key, room.revealed, "blue"):
        room.status = room.STATUS_WON
        room.winner = "blue"
