GRID_SIZE = 10


def _cell_ship_id(fleet, row, col):
    if not fleet:
        return None
    for ship in fleet.get("ships", []):
        for ship_row, ship_col in ship["cells"]:
            if ship_row == row and ship_col == col:
                return ship["id"]
    return None


def build_own_board(fleet, incoming_shots):
    board = []
    for row in range(GRID_SIZE):
        board_row = []
        for col in range(GRID_SIZE):
            shot = incoming_shots[row][col] if incoming_shots else 0
            if shot == 0:
                ship_id = _cell_ship_id(fleet, row, col)
                if ship_id is not None:
                    board_row.append("ship-" + str(ship_id))
                else:
                    board_row.append("water")
            elif shot == 1:
                board_row.append("miss")
            else:
                board_row.append("hit")
        board.append(board_row)
    return board


def _sunk_cells(fleet):
    cells = set()
    if not fleet:
        return cells
    for ship in fleet.get("ships", []):
        if ship.get("sunk"):
            for row, col in ship["cells"]:
                cells.add((row, col))
    return cells


def _sunk_ship_ids(fleet):
    if not fleet:
        return []
    return [ship["id"] for ship in fleet.get("ships", []) if ship.get("sunk")]


def build_placement_board(fleet, selected_ship_id=None):
    board = [["water" for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    if not fleet:
        return board
    for ship in fleet.get("ships", []):
        label = "ship-" + str(ship["id"])
        if selected_ship_id is not None and ship["id"] == selected_ship_id:
            label = "ship-selected"
        for row, col in ship["cells"]:
            board[row][col] = label
    return board


def build_targeting(shots, opponent_fleet=None, reveal_unhit_ships=False):
    sunk = _sunk_cells(opponent_fleet)
    board = []
    for row in range(GRID_SIZE):
        board_row = []
        for col in range(GRID_SIZE):
            shot = shots[row][col] if shots else 0
            if shot == 0:
                if reveal_unhit_ships and _cell_ship_id(opponent_fleet, row, col) is not None:
                    board_row.append("revealed-ship")
                else:
                    board_row.append("unknown")
            elif shot == 1:
                board_row.append("miss")
            elif (row, col) in sunk:
                board_row.append("sunk")
            else:
                board_row.append("hit")
        board.append(board_row)
    return board


def _empty_board(fill="water"):
    return [[fill for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def _fleet_for_viewer(room, viewer_seat):
    if viewer_seat == "X":
        return room.fleet_x
    if viewer_seat == "O":
        return room.fleet_o
    return None


def _opponent_fleet_for_viewer(room, viewer_seat):
    if viewer_seat == "X":
        return room.fleet_o
    if viewer_seat == "O":
        return room.fleet_x
    return None


def _reveal_unhit_ships_for_viewer(room, viewer_seat):
    return room.status == "won" and viewer_seat is not None and viewer_seat != room.winner


def room_to_dict(room, viewer_seat):
    your_name = None
    if viewer_seat == "X":
        your_name = room.name_x
    elif viewer_seat == "O":
        your_name = room.name_o

    payload = {
        "code": room.code,
        "status": room.status,
        "turn": room.turn,
        "winner": room.winner,
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
        "grid_size": GRID_SIZE,
        "vs_cpu": room.vs_cpu,
    }

    if viewer_seat == "X":
        payload["your_ready"] = room.ready_x
        payload["opponent_ready"] = room.ready_o
        if room.status == "placement":
            payload["your_ships"] = room.fleet_x["ships"] if room.fleet_x else []
            payload["your_board"] = build_placement_board(room.fleet_x)
        else:
            payload["your_board"] = build_own_board(
                room.fleet_x, room.shots_o or _empty_board(0)
            )
            payload["targeting"] = build_targeting(
                room.shots_x or _empty_board(0),
                room.fleet_o,
                reveal_unhit_ships=_reveal_unhit_ships_for_viewer(room, "X"),
            )
            payload["your_sunk_ship_ids"] = _sunk_ship_ids(room.fleet_x)
    elif viewer_seat == "O":
        payload["your_ready"] = room.ready_o
        payload["opponent_ready"] = room.ready_x
        if room.status == "placement":
            payload["your_ships"] = room.fleet_o["ships"] if room.fleet_o else []
            payload["your_board"] = build_placement_board(room.fleet_o)
        else:
            payload["your_board"] = build_own_board(
                room.fleet_o, room.shots_x or _empty_board(0)
            )
            payload["targeting"] = build_targeting(
                room.shots_o or _empty_board(0),
                room.fleet_x,
                reveal_unhit_ships=_reveal_unhit_ships_for_viewer(room, "O"),
            )
            payload["your_sunk_ship_ids"] = _sunk_ship_ids(room.fleet_o)
    elif viewer_seat is None:
        payload["spectator"] = True
        payload["board_x"] = build_own_board(room.fleet_x, room.shots_o or _empty_board(0))
        payload["board_o"] = build_own_board(room.fleet_o, room.shots_x or _empty_board(0))
        payload["targeting_x"] = build_targeting(
            room.shots_x or _empty_board(0), room.fleet_o
        )
        payload["targeting_o"] = build_targeting(
            room.shots_o or _empty_board(0), room.fleet_x
        )
        payload["ready_x"] = room.ready_x
        payload["ready_o"] = room.ready_o

    return payload
