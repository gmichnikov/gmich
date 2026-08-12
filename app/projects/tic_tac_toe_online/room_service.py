"""
In-memory room/game engine for Tic-Tac-Toe Online.

Rooms live in a single process-wide dict, guarded by a lock. This is
intentional: the app runs as a single gunicorn worker, so there's no
cross-process split-brain risk, but it does mean every deploy/restart
wipes all active games.
"""

import random
import threading
import time

ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L (easy to misread)
ROOM_CODE_LENGTH = 6

WIN_PATTERNS = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columns
    (0, 4, 8), (2, 4, 6),             # diagonals
)

_lock = threading.Lock()
_rooms = {}


class RoomError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _generate_code():
    return "".join(random.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def _check_winner(board):
    for pattern in WIN_PATTERNS:
        a, b, c = pattern
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a], list(pattern)
    return None, None


def seat_for_player(room, player_id):
    for seat, occupant_id in room["seats"].items():
        if occupant_id is not None and occupant_id == player_id:
            return seat
    return None


def create_room():
    """Create an empty room. Seats are claimed later via join_room."""
    with _lock:
        for _ in range(20):
            code = _generate_code()
            if code not in _rooms:
                now = time.time()
                room = {
                    "code": code,
                    "board": [None] * 9,
                    "turn": "X",
                    "last_starter": "X",
                    "seats": {"X": None, "O": None},
                    "status": "waiting",  # waiting | active | won | draw
                    "winner": None,
                    "winning_line": None,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                }
                _rooms[code] = room
                return room
        raise RoomError("Could not create a room right now. Please try again.", 500)


def get_room(code):
    room = _rooms.get((code or "").upper())
    if room is None:
        raise RoomError(
            "That game room doesn't exist. It may have expired after a server restart.",
            404,
        )
    return room


def join_room(code, player_id):
    """
    Ensure player_id has a seat if one is open, or is recognized as an
    existing occupant. Returns (room, seat) where seat is None for
    spectators.

    Intentionally only called from an explicit POST (not page GET), so
    link prefetchers / chat unfurl bots can't steal a seat.
    """
    with _lock:
        room = get_room(code)
        seat = seat_for_player(room, player_id)
        if seat is not None:
            return room, seat

        # Prefer an empty seat; X then O (covers odd recovery cases too).
        for open_seat in ("X", "O"):
            if room["seats"][open_seat] is None:
                room["seats"][open_seat] = player_id
                if room["seats"]["X"] is not None and room["seats"]["O"] is not None:
                    room["status"] = "active"
                room["updated_at"] = time.time()
                room["version"] += 1
                return room, open_seat

        return room, None  # both seats taken by others: spectator


def get_state(code, player_id):
    with _lock:
        room = get_room(code)
        seat = seat_for_player(room, player_id)
        return room, seat


def make_move(code, player_id, cell_index):
    with _lock:
        room = get_room(code)
        seat = seat_for_player(room, player_id)

        if seat is None:
            raise RoomError("You're spectating this room and can't make moves.", 403)
        if room["status"] != "active":
            raise RoomError("This game isn't active right now.", 400)
        if room["turn"] != seat:
            raise RoomError("It's not your turn.", 400)
        if not isinstance(cell_index, int) or not (0 <= cell_index <= 8):
            raise RoomError("Invalid cell.", 400)
        if room["board"][cell_index] is not None:
            raise RoomError("That cell is already taken.", 400)

        room["board"][cell_index] = seat
        winner, line = _check_winner(room["board"])
        if winner is not None:
            room["status"] = "won"
            room["winner"] = winner
            room["winning_line"] = line
        elif all(value is not None for value in room["board"]):
            room["status"] = "draw"
        else:
            room["turn"] = "O" if seat == "X" else "X"

        room["updated_at"] = time.time()
        room["version"] += 1
        return room, seat


def rematch(code, player_id):
    """Reset the board in-place, alternating who starts for fairness. Players only."""
    with _lock:
        room = get_room(code)
        seat = seat_for_player(room, player_id)

        if seat is None:
            raise RoomError("Only players in this room can start a rematch.", 403)
        if room["status"] not in ("won", "draw"):
            raise RoomError("The current game isn't finished yet.", 400)

        new_starter = "O" if room["last_starter"] == "X" else "X"
        room["board"] = [None] * 9
        room["winner"] = None
        room["winning_line"] = None
        room["status"] = "active"
        room["turn"] = new_starter
        room["last_starter"] = new_starter
        room["updated_at"] = time.time()
        room["version"] += 1
        return room, seat
