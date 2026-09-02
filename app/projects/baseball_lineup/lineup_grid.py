"""
Lineup grid load/save and inning-level validation.

See docs/PRD.md §5.4 and §6.
"""

from app import db
from app.projects.baseball_lineup.lineup_config import (
    ALL_CODES,
    BENCH_CODE,
    EDITOR_FIELD_CODES,
    LABEL_BY_CODE,
    expected_count,
    field_spots_for_inning,
    normalize_expected_counts,
    repeated_positions,
    summarize_row,
)
from app.projects.baseball_lineup.models import BluLineupCell, BluPlayer


def present_players_for_game(game, team):
    """Roster players marked present for this game, in roster order."""
    absent_ids = {
        entry.player_id
        for entry in game.roster_entries.filter_by(is_present=False).all()
    }
    return [
        player
        for player in team.players.order_by(BluPlayer.sort_order, BluPlayer.id).all()
        if player.id not in absent_ids
    ]


def load_cells_by_player(game, player_ids):
    """Return ``{player_id: {inning: position_code}}`` for the given players."""
    if not player_ids:
        return {}
    cells = (
        BluLineupCell.query.filter(
            BluLineupCell.game_id == game.id,
            BluLineupCell.player_id.in_(player_ids),
        ).all()
    )
    grid = {player_id: {} for player_id in player_ids}
    for cell in cells:
        if 1 <= cell.inning <= game.inning_count:
            grid.setdefault(cell.player_id, {})[cell.inning] = cell.position_code
    return grid


def build_lineup_rows(game, present_players, cells_by_player):
    """Rows for template/JSON: cells list, summary, repeat map per player."""
    rows = []
    for player in present_players:
        codes_by_inning = cells_by_player.get(player.id, {})
        cells = [
            codes_by_inning.get(inning, "")
            for inning in range(1, game.inning_count + 1)
        ]
        repeats = repeated_positions(codes_by_inning)
        rows.append(
            {
                "player": player,
                "player_id": player.id,
                "player_name": player.full_name,
                "cells": cells,
                "codes_by_inning": codes_by_inning,
                "summary": summarize_row(codes_by_inning, game.inning_count),
                "repeats": repeats,
            }
        )
    return rows


def compute_inning_warnings(game, present_players, cells_by_player):
    """Inning-level warning strings (warnings only, never blocking)."""
    warnings = []
    expected = normalize_expected_counts(game.expected_counts, game.inning_count)
    present_count = len(present_players)

    for inning in range(1, game.inning_count + 1):
        actual_by_code = {}
        unassigned = 0

        for player in present_players:
            code = cells_by_player.get(player.id, {}).get(inning)
            if not code:
                unassigned += 1
            else:
                actual_by_code[code] = actual_by_code.get(code, 0) + 1

        for code in EDITOR_FIELD_CODES:
            expected_n = expected_count(expected, code, inning)
            actual_n = actual_by_code.get(code, 0)
            if actual_n != expected_n:
                label = LABEL_BY_CODE.get(code, code)
                if actual_n == 0:
                    warnings.append(
                        f"Inning {inning}: expected {expected_n} {label}, found none"
                    )
                else:
                    warnings.append(
                        f"Inning {inning}: expected {expected_n} {label}, found {actual_n}"
                    )

        if unassigned:
            noun = "player" if unassigned == 1 else "players"
            warnings.append(f"Inning {inning}: {unassigned} {noun} unassigned")

        field_spots = field_spots_for_inning(expected, inning)
        if field_spots > present_count:
            warnings.append(
                f"Inning {inning}: {field_spots} field spots but only "
                f"{present_count} players present"
            )

    return warnings


def lineup_editor_payload(game, team):
    """Initial JSON for the client-side lineup editor."""
    present_players = present_players_for_game(game, team)
    player_ids = [player.id for player in present_players]
    cells_by_player = load_cells_by_player(game, player_ids)
    rows = build_lineup_rows(game, present_players, cells_by_player)

    return {
        "inning_count": game.inning_count,
        "expected_counts": normalize_expected_counts(
            game.expected_counts, game.inning_count
        ),
        "editor_field_codes": [
            {"code": code, "label": LABEL_BY_CODE[code]} for code in EDITOR_FIELD_CODES
        ],
        "position_codes": [
            {"code": code, "label": LABEL_BY_CODE[code]} for code in ALL_CODES
        ],
        "rows": [
            {
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "cells": {
                    str(inning): row["cells"][inning - 1]
                    for inning in range(1, game.inning_count + 1)
                },
            }
            for row in rows
        ],
        "warnings": compute_inning_warnings(game, present_players, cells_by_player),
    }


def save_lineup_cells(game, present_player_ids, cells_payload):
    """
    Replace lineup cells for present players only.

    ``cells_payload`` is a list of dicts with ``player_id``, ``inning``,
    ``position_code``. Empty position codes are stored as no row (Blank).
    Absent players' existing cells are left untouched.
    """
    present_ids = set(present_player_ids)
    if not present_ids:
        BluLineupCell.query.filter_by(game_id=game.id).delete(
            synchronize_session=False
        )
        return

    BluLineupCell.query.filter(
        BluLineupCell.game_id == game.id,
        BluLineupCell.player_id.in_(present_ids),
    ).delete(synchronize_session=False)

    for item in cells_payload:
        try:
            player_id = int(item["player_id"])
            inning = int(item["inning"])
        except (KeyError, TypeError, ValueError):
            continue
        if player_id not in present_ids:
            continue
        if not (1 <= inning <= game.inning_count):
            continue

        code = (item.get("position_code") or "").strip()
        if not code or code not in ALL_CODES:
            continue

        db.session.add(
            BluLineupCell(
                game_id=game.id,
                player_id=player_id,
                inning=inning,
                position_code=code,
            )
        )
