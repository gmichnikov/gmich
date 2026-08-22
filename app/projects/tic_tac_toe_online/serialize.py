from app.projects.tic_tac_toe_online.symbols import ALLOWED_SYMBOLS, display_symbol


def room_to_dict(room, viewer_seat):
    """Serialize room state for a specific viewer (player seat or spectator)."""
    your_name = None
    if viewer_seat == "X":
        your_name = room.name_x
    elif viewer_seat == "O":
        your_name = room.name_o

    symbols = {
        "X": display_symbol(room, "X"),
        "O": display_symbol(room, "O"),
    }
    opponent_seat = None
    if viewer_seat == "X":
        opponent_seat = "O"
    elif viewer_seat == "O":
        opponent_seat = "X"
    opponent_symbol = symbols[opponent_seat] if opponent_seat else None

    return {
        "code": room.code,
        "board": room.board,
        "turn": room.turn,
        "status": room.status,
        "winner": room.winner,
        "winning_line": room.winning_line,
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
        "symbols": symbols,
        "your_symbol": symbols.get(viewer_seat) if viewer_seat else None,
        "opponent_symbol": opponent_symbol,
        "allowed_symbols": list(ALLOWED_SYMBOLS),
        "version": room.version,
    }
