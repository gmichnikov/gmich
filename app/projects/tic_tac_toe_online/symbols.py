"""Shared emoji pool for per-player symbol selection."""

ALLOWED_SYMBOLS = (
    "❌",
    "⭕",
    "🐱",
    "🐶",
    "🍕",
    "🍔",
    "⚽",
    "🏀",
    "😊",
    "😎",
    "⭐",
    "💜",
    "🦊",
    "🐼",
    "🍩",
    "🚀",
)

DEFAULT_SYMBOL_X = "❌"
DEFAULT_SYMBOL_O = "⭕"


def opponent_symbol(room, seat):
    if seat == "X":
        return room.symbol_o
    if seat == "O":
        return room.symbol_x
    return None


def default_symbol_for_seat(room, seat):
    other = opponent_symbol(room, seat)
    preferred = DEFAULT_SYMBOL_X if seat == "X" else DEFAULT_SYMBOL_O
    if preferred != other:
        return preferred
    for symbol in ALLOWED_SYMBOLS:
        if symbol != other:
            return symbol
    return ALLOWED_SYMBOLS[0]


def display_symbol(room, seat):
    raw = room.symbol_x if seat == "X" else room.symbol_o
    if raw:
        return raw
    return default_symbol_for_seat(room, seat)
