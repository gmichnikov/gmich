"""
Game-state helpers: actionable/clearable frames, turn order, locks.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from app.projects.bowling.models import BowlingGame
from app.projects.bowling.scoring import (
    all_frames_complete_no_pending,
    compute_player_scorecard,
    frame_is_complete,
    rolls_by_frame,
)


def _roll_get(roll: Any, key: str) -> Any:
    if isinstance(roll, Mapping):
        return roll[key]
    return getattr(roll, key)


def get_actionable_frame(rolls: Sequence[Any]) -> int | None:
    """
    Leading-edge frame where the next roll can be entered, or None if done.
    """
    by_frame = rolls_by_frame(rolls)
    highest_with_rolls = 0
    for frame in range(1, 11):
        if by_frame.get(frame):
            highest_with_rolls = frame

    if highest_with_rolls == 0:
        return 1

    frame_rolls = by_frame.get(highest_with_rolls, {})
    if not frame_is_complete(highest_with_rolls, frame_rolls):
        return highest_with_rolls

    if highest_with_rolls < 10:
        return highest_with_rolls + 1

    return None


def get_next_roll_number(rolls: Sequence[Any], frame: int) -> int | None:
    """Which roll slot (1–3) is next for the given frame."""
    by_frame = rolls_by_frame(rolls)
    frame_rolls = by_frame.get(frame, {})

    if frame <= 9:
        if 1 not in frame_rolls:
            return 1
        if frame_rolls.get(1) == 10:
            return None
        if 2 not in frame_rolls:
            return 2
        return None

    r1 = frame_rolls.get(1)
    if r1 is None:
        return 1
    r2 = frame_rolls.get(2)
    if r1 == 10:
        if r2 is None:
            return 2
        if 3 not in frame_rolls:
            return 3
        return None
    if r2 is None:
        return 2
    if r1 + r2 == 10:
        if 3 not in frame_rolls:
            return 3
        return None
    return None


def get_clearable_frame(rolls: Sequence[Any]) -> int | None:
    """
    Frame that can be cleared: in-progress frame, or most recently completed
    if nothing is in progress.
    """
    by_frame = rolls_by_frame(rolls)
    if not by_frame:
        return None

    actionable = get_actionable_frame(rolls)
    if actionable is None:
        for frame in range(10, 0, -1):
            if by_frame.get(frame):
                return frame
        return None

    frame_rolls = by_frame.get(actionable, {})
    if frame_rolls and not frame_is_complete(actionable, frame_rolls):
        return actionable

    if actionable > 1 and by_frame.get(actionable - 1):
        return actionable - 1

    return None


def get_current_turn_player_id(
    players: Sequence[Any],
    rolls_by_player_id: Mapping[int, Sequence[Any]],
) -> int | None:
    """
    Player with fewest completed frames; tiebreak lowest order_index.
    """
    if not players:
        return None
    if len(players) == 1:
        return int(_roll_get(players[0], "id"))

    best_id: int | None = None
    best_completed: int | None = None
    best_order: int | None = None

    for player in players:
        player_id = int(_roll_get(player, "id"))
        order_index = int(_roll_get(player, "order_index"))
        rolls = rolls_by_player_id.get(player_id, ())
        by_frame = rolls_by_frame(rolls)
        completed = sum(
            1
            for frame in range(1, 11)
            if frame_is_complete(frame, by_frame.get(frame, {}))
        )
        if (
            best_completed is None
            or completed < best_completed
            or (completed == best_completed and order_index < (best_order or 0))
        ):
            best_completed = completed
            best_order = order_index
            best_id = player_id

    return best_id


def is_player_add_locked(all_player_rolls: Sequence[Sequence[Any]]) -> bool:
    """True once any player has recorded roll 1 of frame 2."""
    for rolls in all_player_rolls:
        for roll in rolls:
            if int(_roll_get(roll, "frame")) == 2 and int(_roll_get(roll, "roll")) == 1:
                return True
    return False


def can_remove_or_reorder_players(status: str) -> bool:
    return status == BowlingGame.STATUS_SETUP


def can_rename_player(status: str) -> bool:
    return status == BowlingGame.STATUS_SETUP


def can_add_player(status: str, all_player_rolls: Sequence[Sequence[Any]]) -> bool:
    if status == BowlingGame.STATUS_SETUP:
        return True
    if status != BowlingGame.STATUS_ACTIVE:
        return False
    return not is_player_add_locked(all_player_rolls)


def is_mark_complete_eligible(
    players: Sequence[Any],
    rolls_by_player_id: Mapping[int, Sequence[Any]],
) -> bool:
    if not players:
        return False
    for player in players:
        player_id = int(_roll_get(player, "id"))
        rolls = rolls_by_player_id.get(player_id, ())
        if not all_frames_complete_no_pending(rolls):
            return False
        card = compute_player_scorecard(rolls)
        if card.total is None:
            return False
    return True


def max_valid_pins(frame: int, roll: int, rolls: Sequence[Any]) -> int:
    """Highest pin count allowed for this roll (PRD §05 validation table)."""
    by_frame = rolls_by_frame(rolls)
    frame_rolls = by_frame.get(frame, {})

    if frame <= 9:
        if roll == 1:
            return 10
        r1 = frame_rolls.get(1, 0)
        return 10 - r1

    r1 = frame_rolls.get(1)
    if roll == 1:
        return 10
    r2 = frame_rolls.get(2)
    if r1 == 10:
        if roll == 2:
            return 10
        if roll == 3 and r2 is not None and r2 < 10:
            return 10 - r2
        return 10
    if roll == 2:
        return 10 - (r1 or 0)
    if r1 is not None and r1 < 10 and r2 is not None and r1 + r2 == 10:
        return 10
    return 10
