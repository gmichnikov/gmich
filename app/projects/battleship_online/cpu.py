"""CPU opponent for Battleship Online solo games."""

import random

CPU_PLAYER_ID = "__cpu__"
CPU_DISPLAY_NAME = "Computer"


def _sunk_cells_from_fleet(fleet):
    cells = set()
    if not fleet:
        return cells
    for ship in fleet.get("ships", []):
        if ship.get("sunk"):
            for row, col in ship["cells"]:
                cells.add((row, col))
    return cells


def _active_hits(shots, sunk_cells):
    hits = []
    for row in range(len(shots)):
        for col in range(len(shots[row])):
            if shots[row][col] == 2 and (row, col) not in sunk_cells:
                hits.append((row, col))
    return hits


def _group_hits(hits):
    hit_set = set(hits)
    groups = []
    visited = set()
    for start in hits:
        if start in visited:
            continue
        group = []
        stack = [start]
        while stack:
            cell = stack.pop()
            if cell in visited:
                continue
            visited.add(cell)
            group.append(cell)
            row, col = cell
            for drow, dcol in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbor = (row + drow, col + dcol)
                if neighbor in hit_set and neighbor not in visited:
                    stack.append(neighbor)
        groups.append(group)
    return groups


def _is_valid_target(shots, row, col):
    return 0 <= row < len(shots) and 0 <= col < len(shots[row]) and shots[row][col] == 0


def _hunt_targets(group, shots):
    if len(group) == 1:
        row, col = group[0]
        directions = [(row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)]
        random.shuffle(directions)
        return [cell for cell in directions if _is_valid_target(shots, *cell)]

    rows = {row for row, _col in group}
    cols = {_col for _row, _col in group}
    if len(rows) == 1:
        row = next(iter(rows))
        min_col = min(cols)
        max_col = max(cols)
        directions = [(row, min_col - 1), (row, max_col + 1)]
        random.shuffle(directions)
        return [cell for cell in directions if _is_valid_target(shots, *cell)]

    if len(cols) == 1:
        col = next(iter(cols))
        min_row = min(rows)
        max_row = max(rows)
        directions = [(min_row - 1, col), (max_row + 1, col)]
        random.shuffle(directions)
        return [cell for cell in directions if _is_valid_target(shots, *cell)]

    candidates = []
    seen = set()
    for row, col in group:
        for cell in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            if cell not in seen and _is_valid_target(shots, *cell):
                seen.add(cell)
                candidates.append(cell)
    random.shuffle(candidates)
    return candidates


def _search_targets(shots):
    fired = set()
    unknown = []
    for row in range(len(shots)):
        for col in range(len(shots[row])):
            if shots[row][col] == 0:
                unknown.append((row, col))
            else:
                fired.add((row, col))

    if not unknown:
        return []

    def ortho_adjacent_to_fired(row, col):
        for drow, dcol in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if (row + drow, col + dcol) in fired:
                return True
        return False

    def is_checkerboard(row, col):
        return (row + col) % 2 == 0

    spread = [cell for cell in unknown if not ortho_adjacent_to_fired(*cell)]
    checkerboard = [cell for cell in unknown if is_checkerboard(*cell)]
    checkerboard_spread = [cell for cell in spread if is_checkerboard(*cell)]

    if checkerboard_spread:
        return checkerboard_spread
    if checkerboard:
        return checkerboard
    if spread:
        return spread
    return unknown


def choose_shot(shots, opponent_fleet=None):
    """Pick the next shot using hunt/search targeting."""
    sunk_cells = _sunk_cells_from_fleet(opponent_fleet)
    groups = _group_hits(_active_hits(shots, sunk_cells))
    if groups:
        random.shuffle(groups)
        for group in groups:
            targets = _hunt_targets(group, shots)
            if targets:
                return targets[0]

    candidates = _search_targets(shots)
    if not candidates:
        return None
    return random.choice(candidates)
