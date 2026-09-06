"""Serialization for Mancala Online rooms with perspective orientation.

Perspective Rules (Option 1A):
- Player sees their own 6 pits on the bottom row (left-to-right).
- Player sees their opponent's 6 pits on the top row (left-to-right).
- Player sees their own Kalah/store on the right.
- Player sees their opponent's Kalah/store on the left.

Raw Board indexing:
- Player X: pits 0..5, store 6.
- Player O: pits 7..12, store 13.

Counter-clockwise flow on board:
- Bottom row (player's pits) flows Left -> Right towards player's Right Store.
- Top row (opponent's pits) flows Right -> Left towards opponent's Left Store.
For Player X:
- Bottom pits (0..5): left to right is 0, 1, 2, 3, 4, 5.
- Top pits (opponent O: 7..12): moving counter-clockwise around the loop from store 6 goes 7 -> 8 -> 9 -> 10 -> 11 -> 12 -> 13.
  Looking at the board from X's perspective, pit 12 is directly above pit 0, pit 7 is directly above pit 5!
  So from left to right, opponent's pits appear as [12, 11, 10, 9, 8, 7].
- Right store: 6
- Left store: 13

For Player O:
- Bottom pits (7..12): left to right is 7, 8, 9, 10, 11, 12 towards right store 13.
- Top pits (opponent X: 0..5): from left to right appear as [5, 4, 3, 2, 1, 0] towards left store 6.
- Right store: 13
- Left store: 6

For Spectators (neutral perspective, defaults to X's view):
- bottom: X (0..5)
- top: O (12..7)
"""


def room_to_dict(room, viewer_seat):
    your_name = None
    if viewer_seat == "X":
        your_name = room.name_x
    elif viewer_seat == "O":
        your_name = room.name_o

    board = room.board

    # Default / Seat X perspective
    if viewer_seat == "O":
        my_seat = "O"
        opp_seat = "X"
        bottom_pit_indices = [7, 8, 9, 10, 11, 12]
        top_pit_indices = [5, 4, 3, 2, 1, 0]
        right_store_idx = 13
        left_store_idx = 6
    else:
        # "X" or spectator
        my_seat = "X" if viewer_seat == "X" else None
        opp_seat = "O" if viewer_seat == "X" else None
        bottom_pit_indices = [0, 1, 2, 3, 4, 5]
        top_pit_indices = [12, 11, 10, 9, 8, 7]
        right_store_idx = 6
        left_store_idx = 13

    # Format pits with index and seed count
    bottom_pits = [
        {"index": idx, "count": board[idx]} for idx in bottom_pit_indices
    ]
    top_pits = [
        {"index": idx, "count": board[idx]} for idx in top_pit_indices
    ]

    return {
        "code": room.code,
        "board": board,
        "turn": room.turn,
        "status": room.status,
        "winner": room.winner,
        "last_move": room.last_move,
        "seats": {
            "X": bool(room.seat_x),
            "O": bool(room.seat_o),
        },
        "names": {
            "X": room.display_name("X"),
            "O": room.display_name("O"),
        },
        "your_seat": viewer_seat,
        "your_name": your_name,
        # Perspective fields for simple, error-free frontend rendering
        "view": {
            "is_my_turn": (viewer_seat is not None and room.turn == viewer_seat and room.status == "active"),
            "bottom_label": room.display_name(viewer_seat) if viewer_seat else room.display_name("X"),
            "bottom_seat": viewer_seat if viewer_seat else "X",
            "bottom_pits": bottom_pits,
            "right_store": {
                "index": right_store_idx,
                "count": board[right_store_idx],
                "owner": "O" if viewer_seat == "O" else "X",
            },
            "top_label": room.display_name("X" if viewer_seat == "O" else "O"),
            "top_seat": "X" if viewer_seat == "O" else "O",
            "top_pits": top_pits,
            "left_store": {
                "index": left_store_idx,
                "count": board[left_store_idx],
                "owner": "X" if viewer_seat == "O" else "O",
            },
        },
        "version": room.version,
    }
