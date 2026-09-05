"""Disc color options for per-player selection."""

ALLOWED_COLORS = (
    "red",
    "yellow",
    "orange",
    "green",
    "blue",
    "purple",
)

DEFAULT_COLOR_X = "red"
DEFAULT_COLOR_O = "yellow"

COLOR_LABELS = {
    "red": "Red",
    "yellow": "Yellow",
    "orange": "Orange",
    "green": "Green",
    "blue": "Blue",
    "purple": "Purple",
}


def opponent_color(room, seat):
    if seat == "X":
        return room.color_o
    if seat == "O":
        return room.color_x
    return None


def default_color_for_seat(room, seat):
    other = opponent_color(room, seat)
    preferred = DEFAULT_COLOR_X if seat == "X" else DEFAULT_COLOR_O
    if preferred != other:
        return preferred
    for color in ALLOWED_COLORS:
        if color != other:
            return color
    return ALLOWED_COLORS[0]


def display_color(room, seat):
    raw = room.color_x if seat == "X" else room.color_o
    if raw:
        return raw
    return default_color_for_seat(room, seat)
