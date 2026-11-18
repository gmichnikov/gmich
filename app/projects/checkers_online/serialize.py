from app.projects.checkers_online.models import CheckersOnlineRoom
from app.projects.checkers_online.room_service import _colors_locked
from app.projects.checkers_online.rules import board_from_key, describe_last_move, legal_moves

_DRAW_TEXT = {
    "quiet": "Draw — 40 moves with no capture or king.",
    "repeat": "Draw — the same position happened three times.",
}


def _last_move(room):
    history = room.position_history or []
    if len(history) < 2:
        return None
    try:
        previous = board_from_key(history[-2])
    except (ValueError, IndexError):
        return None
    return describe_last_move(previous, room.board)


def room_to_dict(room, viewer_seat):
    your_color = room.color_for_seat(viewer_seat) if viewer_seat else None
    show_moves = (
        room.status == CheckersOnlineRoom.STATUS_ACTIVE
        and your_color is not None
        and room.turn == your_color
    )
    moves = legal_moves(room.board, room.turn) if show_moves else []

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
        "result_text": _DRAW_TEXT.get(room.result_reason),
        "seats": {
            "X": room.seat_x is not None,
            "O": room.seat_o is not None,
        },
        "names": {
            "X": room.display_name("X"),
            "O": room.display_name("O"),
        },
        "colors": {
            "X": room.color_x,
            "O": room.color_o,
        },
        "your_seat": viewer_seat,
        "your_name": your_name,
        "your_color": your_color,
        "can_pick_color": bool(viewer_seat) and not _colors_locked(room),
        "legal_moves": moves,
        "last_move": _last_move(room),
        "version": room.version,
        "vs_cpu": bool(room.vs_cpu),
        "difficulty": room.difficulty or "medium",
        "cpu_first": bool(room.cpu_first),
    }
