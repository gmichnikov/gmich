def room_to_dict(room, viewer_seat):
    """Serialize room state for a specific viewer (player seat or spectator)."""
    your_name = None
    if viewer_seat == "X":
        your_name = room.name_x
    elif viewer_seat == "O":
        your_name = room.name_o

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
        "version": room.version,
    }
