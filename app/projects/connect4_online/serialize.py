from app.projects.connect4_online.colors import ALLOWED_COLORS, COLOR_LABELS, display_color
from app.projects.connect4_online.room_service import COLS, ROWS


def room_to_dict(room, viewer_seat):
    your_name = None
    if viewer_seat == "X":
        your_name = room.name_x
    elif viewer_seat == "O":
        your_name = room.name_o

    colors = {
        "X": display_color(room, "X"),
        "O": display_color(room, "O"),
    }
    opponent_seat = None
    if viewer_seat == "X":
        opponent_seat = "O"
    elif viewer_seat == "O":
        opponent_seat = "X"
    opponent_color = colors[opponent_seat] if opponent_seat else None

    return {
        "code": room.code,
        "board": room.board,
        "turn": room.turn,
        "status": room.status,
        "winner": room.winner,
        "winning_cells": room.winning_cells,
        "seats": {
            "X": room.seat_x is not None,
            "O": room.seat_o is not None,
        },
        "names": {
            "X": room.display_name("X"),
            "O": room.display_name("O"),
        },
        "your_seat": viewer_seat,
        "your_name": your_name,
        "colors": colors,
        "your_color": colors.get(viewer_seat) if viewer_seat else None,
        "opponent_color": opponent_color,
        "allowed_colors": list(ALLOWED_COLORS),
        "color_labels": COLOR_LABELS,
        "rows": ROWS,
        "cols": COLS,
        "version": room.version,
    }
