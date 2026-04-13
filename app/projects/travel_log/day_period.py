"""Optional time-of-day labels for travel log entries (list + calendar ordering)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import case

# Display order within a day (evening before dinner). Unknown/unlabeled last.
DAY_PERIOD_KEYS: tuple[str, ...] = (
    "early_morning",
    "breakfast",
    "morning",
    "lunch",
    "afternoon",
    "evening",
    "dinner",
    "night",
)

DAY_PERIOD_LABELS: dict[str, str] = {
    "early_morning": "Early morning",
    "breakfast": "Breakfast",
    "morning": "Morning",
    "lunch": "Lunch",
    "afternoon": "Afternoon",
    "evening": "Evening",
    "dinner": "Dinner",
    "night": "Night",
}

# Calendar filter: "meals" = these period keys only
MEAL_PERIOD_KEYS: frozenset[str] = frozenset({"breakfast", "lunch", "dinner"})

UNKNOWN_LABEL = "Unknown"

TLOG_PERIOD_SORT_ORDER: dict[str | None, int] = {k: i for i, k in enumerate(DAY_PERIOD_KEYS)}
TLOG_PERIOD_SORT_ORDER[None] = len(DAY_PERIOD_KEYS)


def normalize_day_period(raw: str | None) -> str | None:
    """Return a valid period key or None (unknown)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if s in DAY_PERIOD_LABELS:
        return s
    return None


def day_period_options_for_template() -> list[tuple[str, str]]:
    """(value, label) for HTML selects."""
    return [(k, DAY_PERIOD_LABELS[k]) for k in DAY_PERIOD_KEYS]


def period_order_case(entry_model: Any):
    """SQLAlchemy expression: sort unknown (null) last, then fixed order."""
    whens = [(entry_model.day_period == k, TLOG_PERIOD_SORT_ORDER[k]) for k in DAY_PERIOD_KEYS]
    return case(*whens, else_=TLOG_PERIOD_SORT_ORDER[None])


def is_meal_period(period: str | None) -> bool:
    return period is not None and period in MEAL_PERIOD_KEYS


def period_label(period: str | None) -> str:
    if period is None:
        return UNKNOWN_LABEL
    return DAY_PERIOD_LABELS.get(period, UNKNOWN_LABEL)


def build_calendar_days(entries: list[Any]) -> list[dict[str, Any]]:
    """
    Group sorted entries by visited_date, then by period.
    Skips days with no entries. Skips period buckets with no entries.
    Each day: { 'date', 'date_iso', 'date_label', 'periods': [ { 'key', 'label', 'entries' } ] }
    """
    by_date: dict[date, list[Any]] = defaultdict(list)
    for e in entries:
        by_date[e.visited_date].append(e)

    out: list[dict[str, Any]] = []
    for d in sorted(by_date.keys()):
        day_list = by_date[d]
        periods_out: list[dict[str, Any]] = []
        for pk in DAY_PERIOD_KEYS:
            bucket = [x for x in day_list if x.day_period == pk]
            if bucket:
                periods_out.append(
                    {
                        "key": pk,
                        "label": DAY_PERIOD_LABELS[pk],
                        "entries": bucket,
                    }
                )
        known_keys = set(DAY_PERIOD_KEYS)
        unknown = [x for x in day_list if x.day_period is None or x.day_period not in known_keys]
        if unknown:
            periods_out.append(
                {
                    "key": None,
                    "label": UNKNOWN_LABEL,
                    "entries": unknown,
                }
            )
        out.append(
            {
                "date": d,
                "date_iso": d.isoformat(),
                "date_label": d.strftime("%a, %b %d, %Y"),
                "periods": periods_out,
            }
        )
    return out
