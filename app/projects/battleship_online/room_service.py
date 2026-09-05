"""Database-backed room/game engine for Battleship Online."""

import copy
import random
from datetime import datetime, timedelta

from app import db
from app.projects.battleship_online.cpu import (
    CPU_DISPLAY_NAME,
    CPU_PLAYER_ID,
    choose_shot,
)
from app.projects.battleship_online.models import BattleshipOnlineRoom

ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 6
CLEANUP_DAYS = 14
MAX_NAME_LENGTH = 30
GRID_SIZE = 10
SHIP_SIZES = (5, 4, 3, 3, 2)
SHIP_NAMES = ("Carrier", "Battleship", "Cruiser", "Submarine", "Destroyer")


class RoomError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _generate_code():
    return "".join(random.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def _normalize_name(name):
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    return cleaned[:MAX_NAME_LENGTH]


def _touch(room):
    room.updated_at = datetime.utcnow()


def _empty_shots():
    return [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def _neighbor_cells(row, col):
    for drow in (-1, 0, 1):
        for dcol in (-1, 0, 1):
            if drow == 0 and dcol == 0:
                continue
            neighbor_row = row + drow
            neighbor_col = col + dcol
            if 0 <= neighbor_row < GRID_SIZE and 0 <= neighbor_col < GRID_SIZE:
                yield neighbor_row, neighbor_col


def _forbidden_cells_for_fleet(fleet, ship_index=None):
    forbidden = set()
    for index, ship in enumerate(fleet["ships"]):
        if index == ship_index:
            continue
        for row, col in ship["cells"]:
            forbidden.add((row, col))
            forbidden.update(_neighbor_cells(row, col))
    return forbidden


def _generate_random_fleet():
    ships = []
    forbidden = set()
    for size in SHIP_SIZES:
        placed = False
        for _ in range(1000):
            horizontal = random.choice((True, False))
            if horizontal:
                row = random.randint(0, GRID_SIZE - 1)
                col = random.randint(0, GRID_SIZE - size)
                cells = [[row, col + offset] for offset in range(size)]
            else:
                row = random.randint(0, GRID_SIZE - size)
                col = random.randint(0, GRID_SIZE - 1)
                cells = [[row + offset, col] for offset in range(size)]
            cell_set = {tuple(cell) for cell in cells}
            if cell_set.isdisjoint(forbidden):
                for row, col in cell_set:
                    forbidden.add((row, col))
                    forbidden.update(_neighbor_cells(row, col))
                ships.append(
                    {
                        "id": len(ships),
                        "size": size,
                        "horizontal": horizontal,
                        "cells": cells,
                        "hits": [False] * size,
                        "sunk": False,
                    }
                )
                placed = True
                break
        if not placed:
            raise RoomError("Could not place ships right now. Please try again.", 500)
    return {"ships": ships}


def _default_placement_fleet():
    ships = []
    for ship_id, size in enumerate(SHIP_SIZES):
        ships.append(
            {
                "id": ship_id,
                "size": size,
                "horizontal": True,
                "cells": [[ship_id, col] for col in range(size)],
                "hits": [False] * size,
                "sunk": False,
            }
        )
    return {"ships": ships}


def _cells_are_valid(cells, size, fleet, ship_index):
    if len(cells) != size:
        return False

    rows = [cell[0] for cell in cells]
    cols = [cell[1] for cell in cells]
    horizontal = len(set(rows)) == 1 and cols == list(range(min(cols), min(cols) + size))
    vertical = len(set(cols)) == 1 and rows == list(range(min(rows), min(rows) + size))
    if not (horizontal or vertical):
        return False

    for row, col in cells:
        if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
            return False

    occupied = set()
    for index, ship in enumerate(fleet["ships"]):
        if index == ship_index:
            continue
        for row, col in ship["cells"]:
            occupied.add((row, col))

    forbidden = _forbidden_cells_for_fleet(fleet, ship_index)
    for row, col in cells:
        if (row, col) in occupied:
            return False
        if (row, col) in forbidden:
            return False
    return True


def _apply_ship_update(fleet, ship_index, cells, horizontal):
    if not _cells_are_valid(cells, fleet["ships"][ship_index]["size"], fleet, ship_index):
        raise RoomError("Ships can't overlap, touch, or leave the grid.", 400)
    fleet = copy.deepcopy(fleet)
    fleet["ships"][ship_index]["cells"] = cells
    fleet["ships"][ship_index]["horizontal"] = horizontal
    return fleet


def _move_ship(fleet, ship_index, drow, dcol):
    ship = fleet["ships"][ship_index]
    cells = [[row + drow, col + dcol] for row, col in ship["cells"]]
    return _apply_ship_update(fleet, ship_index, cells, ship["horizontal"])


def _rotate_ship(fleet, ship_index):
    ship = fleet["ships"][ship_index]
    anchor_row, anchor_col = ship["cells"][0]
    size = ship["size"]
    if ship.get("horizontal", True):
        cells = [[anchor_row + offset, anchor_col] for offset in range(size)]
        horizontal = False
    else:
        cells = [[anchor_row, anchor_col + offset] for offset in range(size)]
        horizontal = True
    return _apply_ship_update(fleet, ship_index, cells, horizontal)


def _all_sunk(fleet):
    return all(ship["sunk"] for ship in fleet["ships"])


def _find_ship_hit(fleet, row, col):
    for ship_index, ship in enumerate(fleet["ships"]):
        for hit_index, (ship_row, ship_col) in enumerate(ship["cells"]):
            if ship_row == row and ship_col == col:
                return ship_index, hit_index
    return None, None


def _start_placement(room):
    room.status = BattleshipOnlineRoom.STATUS_PLACEMENT
    room.fleet_x = _default_placement_fleet()
    room.fleet_o = _default_placement_fleet()
    room.ready_x = False
    room.ready_o = False
    room.shots_x = _empty_shots()
    room.shots_o = _empty_shots()
    room.winner = None
    room.turn = "X"


def _cpu_seat():
    return "O"


def _is_cpu_turn(room):
    return room.vs_cpu and room.turn == _cpu_seat()


def _auto_ready_cpu(room):
    cpu_seat = _cpu_seat()
    if cpu_seat == "O":
        room.fleet_o = _generate_random_fleet()
        room.ready_o = True
        room.name_o = CPU_DISPLAY_NAME
    else:
        room.fleet_x = _generate_random_fleet()
        room.ready_x = True
        room.name_x = CPU_DISPLAY_NAME


def _fire_for_seat(room, seat, row, col):
    if not isinstance(row, int) or not isinstance(col, int):
        raise RoomError("Invalid coordinates.", 400)
    if not (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE):
        raise RoomError("Invalid coordinates.", 400)

    if seat == "X":
        shots = [shot_row[:] for shot_row in room.shots_x]
        opponent_fleet = room.fleet_o
    else:
        shots = [shot_row[:] for shot_row in room.shots_o]
        opponent_fleet = room.fleet_x

    if shots[row][col] != 0:
        raise RoomError("You already fired there.", 400)

    opponent_fleet = copy.deepcopy(opponent_fleet)
    event = None

    ship_index, hit_index = _find_ship_hit(opponent_fleet, row, col)
    if ship_index is not None:
        shots[row][col] = 2
        ship = opponent_fleet["ships"][ship_index]
        ship["hits"][hit_index] = True
        if all(ship["hits"]) and not ship["sunk"]:
            ship["sunk"] = True
            event = {
                "type": "sink",
                "ship_name": SHIP_NAMES[ship_index],
                "ship_size": ship["size"],
            }
        if _all_sunk(opponent_fleet):
            room.status = BattleshipOnlineRoom.STATUS_WON
            room.winner = seat
    else:
        shots[row][col] = 1

    if room.status != BattleshipOnlineRoom.STATUS_WON:
        room.turn = "O" if seat == "X" else "X"

    if seat == "X":
        room.shots_x = shots
        room.fleet_o = opponent_fleet
    else:
        room.shots_o = shots
        room.fleet_x = opponent_fleet

    return event


def _cpu_take_turn(room):
    cpu_seat = _cpu_seat()
    shots = room.shots_o if cpu_seat == "O" else room.shots_x
    opponent_fleet = room.fleet_x if cpu_seat == "O" else room.fleet_o
    target = choose_shot(shots, opponent_fleet)
    if target is None:
        return room
    row, col = target
    _fire_for_seat(room, cpu_seat, row, col)
    room.version += 1
    _touch(room)
    db.session.commit()
    return room


def cleanup_stale_rooms():
    cutoff = datetime.utcnow() - timedelta(days=CLEANUP_DAYS)
    BattleshipOnlineRoom.query.filter(BattleshipOnlineRoom.updated_at < cutoff).delete()
    db.session.commit()


def _get_room_row(code):
    room = BattleshipOnlineRoom.query.filter_by(code=(code or "").upper()).first()
    if room is None:
        raise RoomError("That game room doesn't exist.", 404)
    return room


def create_room(creator_player_id=None):
    cleanup_stale_rooms()
    for _ in range(20):
        code = _generate_code()
        if BattleshipOnlineRoom.query.filter_by(code=code).first():
            continue
        now = datetime.utcnow()
        room = BattleshipOnlineRoom(
            code=code,
            status=BattleshipOnlineRoom.STATUS_WAITING,
            seat_x=creator_player_id,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.session.add(room)
        db.session.commit()
        return room
    raise RoomError("Could not create a room right now. Please try again.", 500)


def create_cpu_room(creator_player_id=None):
    cleanup_stale_rooms()
    for _ in range(20):
        code = _generate_code()
        if BattleshipOnlineRoom.query.filter_by(code=code).first():
            continue
        now = datetime.utcnow()
        room = BattleshipOnlineRoom(
            code=code,
            status=BattleshipOnlineRoom.STATUS_WAITING,
            seat_x=creator_player_id,
            seat_o=CPU_PLAYER_ID,
            name_o=CPU_DISPLAY_NAME,
            vs_cpu=True,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.session.add(room)
        db.session.commit()
        return room
    raise RoomError("Could not create a room right now. Please try again.", 500)


def get_room(code):
    return _get_room_row(code)


def join_room(code, player_id, name=None):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    normalized_name = _normalize_name(name)

    if seat is not None:
        if normalized_name is not None:
            if seat == "X":
                room.name_x = normalized_name
            else:
                room.name_o = normalized_name
            _touch(room)
            db.session.commit()
        return room, seat

    for open_seat in ("X", "O"):
        seat_value = room.seat_x if open_seat == "X" else room.seat_o
        if seat_value is None:
            if open_seat == "X":
                room.seat_x = player_id
                if normalized_name is not None:
                    room.name_x = normalized_name
            else:
                room.seat_o = player_id
                if normalized_name is not None:
                    room.name_o = normalized_name
            if room.seat_x and room.seat_o:
                _start_placement(room)
            room.version += 1
            _touch(room)
            db.session.commit()
            return room, open_seat

    return room, None


def get_state(code, player_id):
    room = _get_room_row(code)
    return room, room.seat_for_player(player_id)


def set_name(code, player_id, name):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can change their name.", 403)

    normalized_name = _normalize_name(name)
    if seat == "X":
        room.name_x = normalized_name
    else:
        room.name_o = normalized_name
    _touch(room)
    db.session.commit()
    return room, seat


def shuffle_fleet(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can randomize ships.", 403)
    if room.status != BattleshipOnlineRoom.STATUS_PLACEMENT:
        raise RoomError("Ship placement is already finished.", 400)
    if (seat == "X" and room.ready_x) or (seat == "O" and room.ready_o):
        raise RoomError("You're already ready and can't move ships.", 400)

    if seat == "X":
        room.fleet_x = _generate_random_fleet()
    else:
        room.fleet_o = _generate_random_fleet()
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def adjust_ship(code, player_id, ship_index, action):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can move ships.", 403)
    if room.status != BattleshipOnlineRoom.STATUS_PLACEMENT:
        raise RoomError("Ship placement is already finished.", 400)
    if (seat == "X" and room.ready_x) or (seat == "O" and room.ready_o):
        raise RoomError("You're already ready and can't move ships.", 400)
    if not isinstance(ship_index, int) or not (0 <= ship_index < len(SHIP_SIZES)):
        raise RoomError("Invalid ship.", 400)

    fleet = room.fleet_x if seat == "X" else room.fleet_o
    moves = {
        "up": (0, -1, False),
        "down": (0, 1, False),
        "left": (-1, 0, False),
        "right": (1, 0, False),
        "rotate": (0, 0, True),
    }
    if action not in moves:
        raise RoomError("Invalid move.", 400)

    dcol, drow, is_rotate = moves[action]
    try:
        if is_rotate:
            updated = _rotate_ship(fleet, ship_index)
        else:
            updated = _move_ship(fleet, ship_index, drow, dcol)
    except RoomError:
        raise
    except (IndexError, KeyError, TypeError):
        raise RoomError("Invalid ship.", 400)

    if seat == "X":
        room.fleet_x = updated
    else:
        room.fleet_o = updated
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def set_ready(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can ready up.", 403)
    if room.status != BattleshipOnlineRoom.STATUS_PLACEMENT:
        raise RoomError("Ship placement is already finished.", 400)

    if seat == "X":
        room.ready_x = True
    else:
        room.ready_o = True

    if room.vs_cpu and seat == "X":
        _auto_ready_cpu(room)

    if room.ready_x and room.ready_o:
        room.status = BattleshipOnlineRoom.STATUS_BATTLE
        room.turn = random.choice(("X", "O"))
        room.shots_x = _empty_shots()
        room.shots_o = _empty_shots()

    room.version += 1
    _touch(room)
    db.session.commit()

    if _is_cpu_turn(room):
        room = _cpu_take_turn(room)

    return room, seat


def set_unready(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can unready.", 403)
    if room.status != BattleshipOnlineRoom.STATUS_PLACEMENT:
        raise RoomError("Ship placement is already finished.", 400)
    if seat == "X":
        if not room.ready_x:
            raise RoomError("You're not ready yet.", 400)
        room.ready_x = False
        if room.vs_cpu:
            room.ready_o = False
    else:
        if not room.ready_o:
            raise RoomError("You're not ready yet.", 400)
        room.ready_o = False

    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def fire(code, player_id, row, col):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("You're spectating this room and can't fire.", 403)
    if room.status != BattleshipOnlineRoom.STATUS_BATTLE:
        raise RoomError("The battle hasn't started yet.", 400)
    if room.turn != seat:
        raise RoomError("It's not your turn.", 400)

    event = _fire_for_seat(room, seat, row, col)
    room.version += 1
    _touch(room)
    db.session.commit()

    if room.status == BattleshipOnlineRoom.STATUS_BATTLE and _is_cpu_turn(room):
        room = _cpu_take_turn(room)

    return room, seat, event


def rematch(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only players in this room can start a rematch.", 403)
    if room.status != BattleshipOnlineRoom.STATUS_WON:
        raise RoomError("The current game isn't finished yet.", 400)
    if not room.seat_x:
        raise RoomError("Both players are needed for a rematch.", 400)
    if not room.vs_cpu and not room.seat_o:
        raise RoomError("Both players are needed for a rematch.", 400)

    _start_placement(room)
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat
