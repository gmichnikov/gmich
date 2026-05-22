"""Serialize bowling game state for API responses."""

from __future__ import annotations

from flask import url_for

from app.projects.bowling.game_state import (
    can_add_player,
    get_actionable_frame,
    get_clearable_frame,
    get_current_turn_player_id,
    is_mark_complete_eligible,
    is_player_add_locked,
)
from app.projects.bowling.models import BowlingGame, BowlingPlayer
from app.projects.bowling.scoring import PlayerScorecard, compute_player_scorecard


def _roll_dicts(player: BowlingPlayer) -> list[dict]:
    return [
        {"frame": roll.frame, "roll": roll.roll, "pins": roll.pins}
        for roll in player.rolls
    ]


def _frame_to_dict(frame) -> dict:
    return {
        "frame": frame.frame,
        "rolls": [
            {
                "roll": roll.roll,
                "pins": roll.pins,
                "display": roll.display,
            }
            for roll in frame.rolls
        ],
        "roll_slots": frame.roll_slots,
        "third_roll_locked": frame.third_roll_locked,
        "frame_score": frame.frame_score,
        "cumulative": frame.cumulative,
        "pending": frame.pending,
        "complete": frame.complete,
    }


def _scorecard_to_dict(card: PlayerScorecard) -> dict:
    return {
        "frames": [_frame_to_dict(frame) for frame in card.frames],
        "total": card.total,
    }


def _player_to_dict(player: BowlingPlayer, roll_dicts: list[dict], card: PlayerScorecard) -> dict:
    return {
        "id": player.id,
        "name": player.name,
        "order_index": player.order_index,
        "actionable_frame": get_actionable_frame(roll_dicts),
        "clearable_frame": get_clearable_frame(roll_dicts),
        "scorecard": _scorecard_to_dict(card),
    }


def game_to_dict(game: BowlingGame) -> dict:
    players = list(game.players)
    roll_dicts_by_id = {player.id: _roll_dicts(player) for player in players}
    all_roll_lists = list(roll_dicts_by_id.values())

    return {
        "code": game.code,
        "status": game.status,
        "url": url_for("bowling.game_page", code=game.code, _external=False),
        "created_at": game.created_at.isoformat() + "Z" if game.created_at else None,
        "completed_at": game.completed_at.isoformat() + "Z" if game.completed_at else None,
        "current_turn_player_id": get_current_turn_player_id(players, roll_dicts_by_id),
        "player_add_locked": is_player_add_locked(all_roll_lists),
        "can_add_player": can_add_player(game.status, all_roll_lists),
        "mark_complete_eligible": is_mark_complete_eligible(players, roll_dicts_by_id),
        "players": [
            _player_to_dict(
                player,
                roll_dicts_by_id[player.id],
                compute_player_scorecard(roll_dicts_by_id[player.id]),
            )
            for player in players
        ],
    }
