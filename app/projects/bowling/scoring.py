"""
Bowling score computation from per-frame rolls.

Rolls are dicts or objects with frame (1-10), roll (1-3), and pins (0-10).
Scores are never stored — always derived on read.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RollDisplay:
    frame: int
    roll: int
    pins: int
    display: str


@dataclass(frozen=True)
class FrameResult:
    frame: int
    rolls: tuple[RollDisplay, ...]
    roll_slots: int
    third_roll_locked: bool
    frame_score: int | None
    cumulative: int | None
    pending: bool
    complete: bool


@dataclass(frozen=True)
class PlayerScorecard:
    frames: tuple[FrameResult, ...]
    total: int | None


def _roll_get(roll: Any, key: str) -> Any:
    if isinstance(roll, Mapping):
        return roll[key]
    return getattr(roll, key)


def rolls_by_frame(rolls: Sequence[Any]) -> dict[int, dict[int, int]]:
    grouped: dict[int, dict[int, int]] = {}
    for roll in rolls:
        frame = int(_roll_get(roll, "frame"))
        roll_num = int(_roll_get(roll, "roll"))
        pins = int(_roll_get(roll, "pins"))
        grouped.setdefault(frame, {})[roll_num] = pins
    return grouped


def format_roll_display(frame: int, roll: int, pins: int, roll1_pins: int | None) -> str:
    if pins == 0:
        return "–"
    if frame <= 9 and roll == 1 and pins == 10:
        return "X"
    if roll == 2 and roll1_pins is not None and roll1_pins < 10 and roll1_pins + pins == 10:
        return "/"
    return str(pins)


def frame_is_complete(frame: int, frame_rolls: Mapping[int, int]) -> bool:
    if not frame_rolls:
        return False
    if frame <= 9:
        r1 = frame_rolls.get(1)
        if r1 is None:
            return False
        if r1 == 10:
            return True
        return 2 in frame_rolls
    r1 = frame_rolls.get(1)
    if r1 is None:
        return False
    r2 = frame_rolls.get(2)
    if r1 == 10:
        return r2 is not None and 3 in frame_rolls
    if r2 is None:
        return False
    if r1 + r2 == 10:
        return 3 in frame_rolls
    return True


def build_flat_pin_sequence(by_frame: Mapping[int, Mapping[int, int]]) -> list[int]:
    """Pin counts in bowling order for bonus lookahead."""
    sequence: list[int] = []
    for frame in range(1, 11):
        frame_rolls = by_frame.get(frame)
        if not frame_rolls:
            break
        if frame <= 9:
            r1 = frame_rolls.get(1)
            if r1 is None:
                break
            if r1 == 10:
                sequence.append(10)
                continue
            r2 = frame_rolls.get(2)
            if r2 is None:
                break
            sequence.append(r1)
            sequence.append(r2)
            continue
        if not frame_is_complete(10, frame_rolls):
            for roll_num in (1, 2, 3):
                if roll_num in frame_rolls:
                    sequence.append(frame_rolls[roll_num])
                else:
                    break
            break
        for roll_num in (1, 2, 3):
            if roll_num in frame_rolls:
                sequence.append(frame_rolls[roll_num])
    return sequence


def _frame_roll_displays(frame: int, frame_rolls: Mapping[int, int]) -> tuple[RollDisplay, ...]:
    displays: list[RollDisplay] = []
    r1 = frame_rolls.get(1)
    if r1 is not None:
        displays.append(
            RollDisplay(frame, 1, r1, format_roll_display(frame, 1, r1, None))
        )
    if frame <= 9:
        if r1 is not None and r1 == 10:
            return tuple(displays)
        r2 = frame_rolls.get(2)
        if r2 is not None:
            displays.append(
                RollDisplay(frame, 2, r2, format_roll_display(frame, 2, r2, r1))
            )
        return tuple(displays)

    r2 = frame_rolls.get(2)
    if r2 is not None:
        displays.append(
            RollDisplay(frame, 2, r2, format_roll_display(frame, 2, r2, r1))
        )
    r3 = frame_rolls.get(3)
    if r3 is not None:
        displays.append(
            RollDisplay(frame, 3, r3, format_roll_display(frame, 3, r3, r2))
        )
    return tuple(displays)


def frame_10_third_roll_locked(frame_rolls: Mapping[int, int]) -> bool:
    """True when frame 10 is complete as an open frame (2 rolls only)."""
    if not frame_is_complete(10, frame_rolls):
        return False
    r1 = frame_rolls.get(1)
    r2 = frame_rolls.get(2)
    if r1 is None or r2 is None:
        return False
    if r1 == 10:
        return False
    return r1 + r2 < 10


def _score_frames_one_to_nine(
    by_frame: Mapping[int, Mapping[int, int]], flat: list[int]
) -> list[FrameResult]:
    roll_idx = 0
    total = 0
    results: list[FrameResult] = []

    for frame in range(1, 10):
        frame_rolls = by_frame.get(frame, {})
        complete = frame_is_complete(frame, frame_rolls)
        displays = _frame_roll_displays(frame, frame_rolls)
        frame_score: int | None = None
        pending = False

        if not complete:
            results.append(
                FrameResult(
                    frame=frame,
                    rolls=displays,
                    roll_slots=2,
                    third_roll_locked=False,
                    frame_score=None,
                    cumulative=total if total > 0 else None,
                    pending=False,
                    complete=False,
                )
            )
            for remaining in range(frame + 1, 10):
                rem_rolls = by_frame.get(remaining, {})
                results.append(
                    FrameResult(
                        frame=remaining,
                        rolls=_frame_roll_displays(remaining, rem_rolls),
                        roll_slots=2,
                        third_roll_locked=False,
                        frame_score=None,
                        cumulative=None,
                        pending=False,
                        complete=frame_is_complete(remaining, rem_rolls),
                    )
                )
            return results

        if flat[roll_idx] == 10:
            if roll_idx + 2 >= len(flat):
                pending = True
            else:
                frame_score = 10 + flat[roll_idx + 1] + flat[roll_idx + 2]
                roll_idx += 1
        elif roll_idx + 1 >= len(flat):
            pending = True
        elif flat[roll_idx] + flat[roll_idx + 1] == 10:
            if roll_idx + 2 >= len(flat):
                pending = True
            else:
                frame_score = 10 + flat[roll_idx + 2]
                roll_idx += 2
        else:
            frame_score = flat[roll_idx] + flat[roll_idx + 1]
            roll_idx += 2

        if pending:
            results.append(
                FrameResult(
                    frame=frame,
                    rolls=displays,
                    roll_slots=2,
                    third_roll_locked=False,
                    frame_score=None,
                    cumulative=total if total > 0 else None,
                    pending=True,
                    complete=True,
                )
            )
            for remaining in range(frame + 1, 10):
                rem_rolls = by_frame.get(remaining, {})
                results.append(
                    FrameResult(
                        frame=remaining,
                        rolls=_frame_roll_displays(remaining, rem_rolls),
                        roll_slots=2,
                        third_roll_locked=False,
                        frame_score=None,
                        cumulative=None,
                        pending=True,
                        complete=frame_is_complete(remaining, rem_rolls),
                    )
                )
            return results

        total += frame_score or 0
        results.append(
            FrameResult(
                frame=frame,
                rolls=displays,
                roll_slots=2,
                third_roll_locked=False,
                frame_score=frame_score,
                cumulative=total,
                pending=False,
                complete=True,
            )
        )

    return results


def compute_player_scorecard(rolls: Sequence[Any]) -> PlayerScorecard:
    by_frame = rolls_by_frame(rolls)
    flat = build_flat_pin_sequence(by_frame)
    frames_1_9 = _score_frames_one_to_nine(by_frame, flat)
    any_pending = any(f.pending for f in frames_1_9)

    frame_10_rolls = by_frame.get(10, {})
    f10_complete = frame_is_complete(10, frame_10_rolls)
    f10_displays = _frame_roll_displays(10, frame_10_rolls)
    f10_locked = frame_10_third_roll_locked(frame_10_rolls)
    f10_score: int | None = None
    f10_pending = bool(frame_10_rolls) and not f10_complete
    f10_cumulative: int | None = None

    base_total = frames_1_9[-1].cumulative if frames_1_9 else 0
    if base_total is None:
        base_total = 0

    if f10_complete and not any_pending:
        f10_score = sum(frame_10_rolls[r] for r in sorted(frame_10_rolls))
        f10_cumulative = base_total + f10_score
    elif f10_pending or any_pending:
        f10_pending = f10_pending or any_pending

    frame_10 = FrameResult(
        frame=10,
        rolls=f10_displays,
        roll_slots=3,
        third_roll_locked=f10_locked,
        frame_score=f10_score,
        cumulative=f10_cumulative,
        pending=f10_pending,
        complete=f10_complete,
    )

    all_frames = tuple(list(frames_1_9) + [frame_10])
    final_total: int | None = None
    if f10_complete and not any_pending:
        final_total = f10_cumulative
    else:
        final_total = next(
            (
                f.cumulative
                for f in reversed(all_frames)
                if f.cumulative is not None and not f.pending
            ),
            None,
        )

    return PlayerScorecard(frames=all_frames, total=final_total)


def count_completed_frames(rolls: Sequence[Any]) -> int:
    by_frame = rolls_by_frame(rolls)
    return sum(
        1
        for frame in range(1, 11)
        if frame_is_complete(frame, by_frame.get(frame, {}))
    )


def all_frames_complete_no_pending(rolls: Sequence[Any]) -> bool:
    card = compute_player_scorecard(rolls)
    if len(card.frames) != 10:
        return False
    return all(f.complete for f in card.frames) and not any(f.pending for f in card.frames)
