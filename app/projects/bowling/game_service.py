"""Bowling game write operations and validation."""

from __future__ import annotations

from datetime import datetime

from app import db
from app.projects.bowling.code import generate_unique_game_code
from app.projects.bowling.game_state import (
    can_add_player,
    can_remove_or_reorder_players,
    can_rename_player,
    get_actionable_frame,
    get_clearable_frame,
    get_next_roll_number,
    is_mark_complete_eligible,
    max_valid_pins,
)
from app.projects.bowling.models import BowlingGame, BowlingPlayer, BowlingRoll


class BowlingApiError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_game_by_code(code: str) -> BowlingGame:
    game = BowlingGame.query.filter_by(code=code).first()
    if not game:
        raise BowlingApiError("No game found with that code.", 404)
    return game


def _ensure_writable(game: BowlingGame) -> None:
    if game.status == BowlingGame.STATUS_COMPLETE:
        raise BowlingApiError("Game is complete and cannot be edited.")


def _player_roll_dicts(player: BowlingPlayer) -> list[dict]:
    return [
        {"frame": roll.frame, "roll": roll.roll, "pins": roll.pins}
        for roll in player.rolls
    ]


def _all_player_roll_lists(game: BowlingGame) -> list[list[dict]]:
    return [_player_roll_dicts(player) for player in game.players]


def _get_player(game: BowlingGame, player_id: int) -> BowlingPlayer:
    player = db.session.get(BowlingPlayer, player_id)
    if not player or player.game_id != game.id:
        raise BowlingApiError("Player not found.", 404)
    return player


def create_game() -> BowlingGame:
    game = BowlingGame(code=generate_unique_game_code())
    db.session.add(game)
    db.session.commit()
    return game


def add_player(game: BowlingGame, name: str) -> BowlingPlayer:
    _ensure_writable(game)
    if not can_add_player(game.status, _all_player_roll_lists(game)):
        raise BowlingApiError("Players cannot be added at this point in the game.")

    cleaned = (name or "").strip()
    if not cleaned:
        raise BowlingApiError("Player name is required.")

    next_order = max((player.order_index for player in game.players), default=-1) + 1
    player = BowlingPlayer(game_id=game.id, name=cleaned, order_index=next_order)
    db.session.add(player)
    db.session.commit()
    return player


def update_player_name(game: BowlingGame, player_id: int, name: str) -> BowlingPlayer:
    _ensure_writable(game)
    if not can_rename_player(game.status):
        raise BowlingApiError("Player names cannot be changed after the game has started.")

    player = _get_player(game, player_id)
    cleaned = (name or "").strip()
    if not cleaned:
        raise BowlingApiError("Player name is required.")

    player.name = cleaned
    db.session.commit()
    return player


def remove_player(game: BowlingGame, player_id: int) -> None:
    _ensure_writable(game)
    if not can_remove_or_reorder_players(game.status):
        raise BowlingApiError("Players cannot be removed after the game has started.")

    if len(game.players) <= 1:
        raise BowlingApiError("At least one player must remain.")

    player = _get_player(game, player_id)
    db.session.delete(player)
    db.session.commit()


def reorder_players(game: BowlingGame, player_ids: list[int]) -> None:
    _ensure_writable(game)
    if not can_remove_or_reorder_players(game.status):
        raise BowlingApiError("Players cannot be reordered after the game has started.")

    if not isinstance(player_ids, list) or not player_ids:
        raise BowlingApiError("player_ids must be a non-empty list.")

    existing_ids = {player.id for player in game.players}
    if set(player_ids) != existing_ids or len(player_ids) != len(existing_ids):
        raise BowlingApiError("player_ids must include each player exactly once.")

    players_by_id = {player.id: player for player in game.players}
    for order_index, player_id in enumerate(player_ids):
        players_by_id[player_id].order_index = order_index

    db.session.commit()


def start_game(game: BowlingGame) -> BowlingGame:
    _ensure_writable(game)
    if game.status != BowlingGame.STATUS_SETUP:
        raise BowlingApiError("Game has already started.")

    named_players = [player for player in game.players if player.name.strip()]
    if not named_players:
        raise BowlingApiError("At least one named player is required to start.")

    game.status = BowlingGame.STATUS_ACTIVE
    db.session.commit()
    return game


def submit_roll(
    game: BowlingGame,
    player_id: int,
    frame: int,
    roll: int,
    pins: int,
) -> BowlingRoll:
    _ensure_writable(game)
    if game.status != BowlingGame.STATUS_ACTIVE:
        raise BowlingApiError("Rolls can only be entered during an active game.")

    player = _get_player(game, player_id)
    roll_dicts = _player_roll_dicts(player)

    actionable = get_actionable_frame(roll_dicts)
    if actionable is None:
        raise BowlingApiError("This player has finished all frames.")
    if frame != actionable:
        raise BowlingApiError("Rolls can only be entered on the actionable frame.")

    expected_roll = get_next_roll_number(roll_dicts, frame)
    if expected_roll is None:
        raise BowlingApiError("This frame does not accept more rolls.")
    if roll != expected_roll:
        raise BowlingApiError("Invalid roll number for this frame.")

    if not isinstance(pins, int) or pins < 0:
        raise BowlingApiError("Invalid pin count.")

    max_pins = max_valid_pins(frame, roll, roll_dicts)
    if pins > max_pins:
        raise BowlingApiError(f"Invalid pin count. Maximum for this roll is {max_pins}.")

    existing = BowlingRoll.query.filter_by(
        player_id=player.id,
        frame=frame,
        roll=roll,
    ).first()
    if existing:
        existing.pins = pins
        db.session.commit()
        return existing

    bowling_roll = BowlingRoll(
        player_id=player.id,
        frame=frame,
        roll=roll,
        pins=pins,
    )
    db.session.add(bowling_roll)
    db.session.commit()
    return bowling_roll


def clear_frame(game: BowlingGame, player_id: int, frame: int) -> None:
    _ensure_writable(game)
    if game.status != BowlingGame.STATUS_ACTIVE:
        raise BowlingApiError("Frames can only be cleared during an active game.")

    player = _get_player(game, player_id)
    roll_dicts = _player_roll_dicts(player)
    clearable = get_clearable_frame(roll_dicts)
    if clearable is None:
        raise BowlingApiError("No frame is clearable for this player.")
    if frame != clearable:
        raise BowlingApiError("Only the clearable frame can be cleared.")

    BowlingRoll.query.filter_by(player_id=player.id, frame=frame).delete()
    db.session.commit()


def mark_complete(game: BowlingGame) -> BowlingGame:
    _ensure_writable(game)
    if game.status != BowlingGame.STATUS_ACTIVE:
        raise BowlingApiError("Only active games can be marked complete.")

    roll_dicts_by_id = {player.id: _player_roll_dicts(player) for player in game.players}
    if not is_mark_complete_eligible(game.players, roll_dicts_by_id):
        raise BowlingApiError("All players must finish all frames before marking complete.")

    game.status = BowlingGame.STATUS_COMPLETE
    game.completed_at = datetime.utcnow()
    db.session.commit()
    return game
