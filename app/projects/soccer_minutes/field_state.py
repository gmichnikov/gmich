"""Present players, draft assignments, and pitch/bench view for a game."""

from app import db
from app.projects.soccer_minutes.formation_config import (
    normalize_formation,
    pitch_bands,
)
from app.projects.soccer_minutes.models import ScmEvent, ScmGameRosterEntry, ScmPlayer


def player_chip_label(player):
    if player is None:
        return ""
    if player.jersey_number:
        return f"{player.first_name} #{player.jersey_number}"
    return player.first_name


def roster_entries_by_player(game):
    return {entry.player_id: entry for entry in game.roster_entries.all()}


def player_is_present(player_id, entries_by_player):
    entry = entries_by_player.get(player_id)
    if entry is None:
        return True
    return bool(entry.is_present)


def present_player_ids(players, entries_by_player):
    return {
        player.id
        for player in players
        if player_is_present(player.id, entries_by_player)
    }


def coerce_assignment_map(formation, assignments):
    """Keep one player per valid slot. Does not filter by attendance."""
    valid_keys = {slot["key"] for slot in normalize_formation(formation)["slots"]}
    clean = {}
    used = set()
    if not isinstance(assignments, dict):
        return clean
    for raw_key, raw_id in assignments.items():
        key = str(raw_key)
        if key not in valid_keys:
            continue
        try:
            player_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if player_id in used:
            continue
        clean[key] = player_id
        used.add(player_id)
    return clean


def sanitize_assignments(formation, assignments, present_ids):
    """Keep one present player per valid slot; drop the rest."""
    clean = {}
    for key, player_id in coerce_assignment_map(formation, assignments).items():
        if player_id in present_ids:
            clean[key] = player_id
    return clean


def assignment_view(formation, assignments, players, present_ids, live_assignments=None):
    """Pitch bands + bench for a field map. Marks slots that differ from live."""
    formation = normalize_formation(formation)
    assignments = sanitize_assignments(formation, assignments, present_ids)
    compare = live_assignments is not None
    live_map = coerce_assignment_map(formation, live_assignments or {})
    players_by_id = {player.id: player for player in players}
    assigned_ids = set(assignments.values())
    bands = []
    for band in pitch_bands(formation):
        slots = []
        for slot in band["slots"]:
            player_id = assignments.get(slot["key"])
            player = players_by_id.get(player_id)
            live_id = live_map.get(slot["key"])
            changed = compare and player_id != live_id
            emptied = compare and bool(live_id) and not player_id
            slots.append(
                {
                    "key": slot["key"],
                    "name": slot["name"],
                    "player_id": player_id,
                    "player_label": player_chip_label(player),
                    "changed": changed,
                    "emptied": emptied,
                }
            )
        bands.append(
            {
                "group": band["group"],
                "label": band["label"],
                "slots": slots,
            }
        )
    bench = sorted(
        [
            {
                "id": player.id,
                "label": player_chip_label(player),
                "first_name": player.first_name,
                "full_name": player.full_name,
            }
            for player in players
            if player.id in present_ids and player.id not in assigned_ids
        ],
        key=lambda item: (
            item["first_name"].lower(),
            item["full_name"].lower(),
            item["id"],
        ),
    )
    return {
        "assignments": assignments,
        "bands": bands,
        "bench": bench,
        "field_size": len(formation["slots"]),
        "filled": len(assignments),
    }


def set_player_present(game, player, present):
    entry = ScmGameRosterEntry.query.filter_by(
        game_id=game.id, player_id=player.id
    ).first()
    if present:
        if entry is not None:
            db.session.delete(entry)
    elif entry is None:
        db.session.add(
            ScmGameRosterEntry(
                game_id=game.id,
                player_id=player.id,
                is_present=False,
            )
        )
    else:
        entry.is_present = False


def drop_player_from_assignments(assignments, player_id):
    if not isinstance(assignments, dict):
        return {}
    try:
        target = int(player_id)
    except (TypeError, ValueError):
        return dict(assignments)
    clean = {}
    for key, value in assignments.items():
        try:
            if int(value) == target:
                continue
        except (TypeError, ValueError):
            pass
        clean[key] = value
    return clean


def event_mentions_player(event, player_id):
    payload = event.payload if isinstance(event.payload, dict) else {}
    assignments = payload.get("assignments")
    if not isinstance(assignments, dict):
        return False
    try:
        target = int(player_id)
    except (TypeError, ValueError):
        return False
    for value in assignments.values():
        try:
            if int(value) == target:
                return True
        except (TypeError, ValueError):
            continue
    return False


def strip_player_from_team_games(team, player_id):
    """Remove a player from draft/pending maps and events. Returns affected game count."""
    affected = 0
    for game in team.games.all():
        changed = False
        draft = drop_player_from_assignments(game.draft_assignments, player_id)
        if draft != (game.draft_assignments or {}):
            game.draft_assignments = draft
            changed = True
        if game.pending_assignments is not None:
            pending = drop_player_from_assignments(
                game.pending_assignments, player_id
            )
            if pending != game.pending_assignments:
                game.pending_assignments = pending
                changed = True
        for event in list(game.events.all()):
            if event_mentions_player(event, player_id):
                db.session.delete(event)
                changed = True
        if changed:
            affected += 1
    return affected


def game_has_kickoff(game):
    return (
        ScmEvent.query.filter_by(game_id=game.id, type="period_start").first()
        is not None
    )


def setup_state(team, game):
    """JSON-serializable setup for the game page (attendance + draft field)."""
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    entries = roster_entries_by_player(game)
    present_ids = present_player_ids(players, entries)
    formation = normalize_formation(game.formation)
    view = assignment_view(formation, game.draft_assignments, players, present_ids)
    attendance = [
        {
            "id": player.id,
            "full_name": player.full_name,
            "jersey_number": player.jersey_number,
            "is_present": player.id in present_ids,
        }
        for player in players
    ]
    return {
        "assignments": view["assignments"],
        "bands": view["bands"],
        "bench": view["bench"],
        "attendance": attendance,
        "field_size": view["field_size"],
        "filled": view["filled"],
        "locked": game_has_kickoff(game),
    }
