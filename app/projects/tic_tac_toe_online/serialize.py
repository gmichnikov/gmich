def room_to_dict(room, viewer_seat):
    """Serialize room state for a specific viewer (player seat or spectator)."""
    return {
        "code": room["code"],
        "board": room["board"],
        "turn": room["turn"],
        "status": room["status"],
        "winner": room["winner"],
        "winning_line": room["winning_line"],
        "seats": {
            "X": room["seats"]["X"] is not None,
            "O": room["seats"]["O"] is not None,
        },
        "your_seat": viewer_seat,
        "version": room["version"],
    }
