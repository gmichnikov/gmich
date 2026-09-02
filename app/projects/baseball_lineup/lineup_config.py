"""
Position catalog and lineup structure helpers.

The catalog is code, not data, so adding a position code later applies to every
existing team at once. The per-inning expected counts *are* data: they live on
each game (copied from team defaults at creation) and every number is editable.

See docs/DATA_MODEL.md for the stored JSON shape.
"""

INFIELD = "infield"
OUTFIELD = "outfield"
BENCH = "bench"

# The three categories partition every code, so a player's outfield + infield +
# bench + blank innings always sum to the game's inning count. P and PH are
# infield because that is how the coach adds them up by hand.
SUMMARY_CATEGORIES = (OUTFIELD, INFIELD, BENCH)

BENCH_CODE = "Bench"

POSITION_CATALOG = [
    {"code": "C", "label": "Catcher", "category": INFIELD},
    {"code": "1B", "label": "First Base", "category": INFIELD},
    {"code": "2B", "label": "Second Base", "category": INFIELD},
    {"code": "3B", "label": "Third Base", "category": INFIELD},
    {"code": "SS", "label": "Shortstop", "category": INFIELD},
    {"code": "LF", "label": "Left Field", "category": OUTFIELD},
    {"code": "CF", "label": "Center Field", "category": OUTFIELD},
    {"code": "RF", "label": "Right Field", "category": OUTFIELD},
    {"code": "P", "label": "Pitcher", "category": INFIELD},
    {"code": "PH", "label": "Pitcher Helper", "category": INFIELD},
    {"code": BENCH_CODE, "label": "Bench", "category": BENCH},
]

ALL_CODES = [p["code"] for p in POSITION_CATALOG]
FIELD_CODES = [c for c in ALL_CODES if c != BENCH_CODE]
LABEL_BY_CODE = {p["code"]: p["label"] for p in POSITION_CATALOG}
CATEGORY_BY_CODE = {p["code"]: p["category"] for p in POSITION_CATALOG}
CODES_BY_CATEGORY = {
    category: [c for c in ALL_CODES if CATEGORY_BY_CODE[c] == category]
    for category in SUMMARY_CATEGORIES
}

# Grouping for the structure editor only; these codes count as infield above.
BATTERY_CODES = ("P", "PH")

DEFAULT_INNING_COUNT = 6

# Shipped default template: 5 infield + 4 outfield (2 CF) + 1 battery = 10 spots.
DEFAULT_STANDING_COUNTS = {
    "C": 1,
    "1B": 1,
    "2B": 1,
    "3B": 1,
    "SS": 1,
    "LF": 1,
    "CF": 2,
    "RF": 1,
}
DEFAULT_PITCHER_INNINGS = (3, 4)


def default_expected_counts(inning_count=DEFAULT_INNING_COUNT):
    """Build the shipped default template: a count per position per inning."""
    counts = {
        code: [n] * inning_count for code, n in DEFAULT_STANDING_COUNTS.items()
    }
    counts["P"] = [
        1 if inning in DEFAULT_PITCHER_INNINGS else 0
        for inning in range(1, inning_count + 1)
    ]
    counts["PH"] = [1 - n for n in counts["P"]]
    return counts


def resize_expected_counts(expected_counts, inning_count):
    """
    Fit every row to ``inning_count``: grow by repeating the last inning's value,
    shrink by dropping from the end. Returns a new dict.
    """
    resized = {}
    for code, row in (expected_counts or {}).items():
        row = list(row or [])
        if not row:
            row = [0]
        if len(row) < inning_count:
            row = row + [row[-1]] * (inning_count - len(row))
        resized[code] = row[:inning_count]
    return resized


def expected_count(expected_counts, code, inning):
    """Expected number of players at ``code`` in 1-based ``inning``. 0 if unset."""
    row = (expected_counts or {}).get(code) or []
    if 1 <= inning <= len(row):
        return row[inning - 1] or 0
    return 0


def field_spots_for_inning(expected_counts, inning):
    """Derived total on-field spots for an inning: the sum of that inning's column."""
    return sum(expected_count(expected_counts, code, inning) for code in FIELD_CODES)


def summarize_row(codes_by_inning, inning_count):
    """
    Trailing summary columns for one player's row.

    ``codes_by_inning`` maps 1-based inning -> position code; a missing inning is
    a blank. Returns counts keyed ``outfield``, ``infield``, ``bench``, ``blank``,
    which always sum to ``inning_count``.
    """
    summary = {category: 0 for category in SUMMARY_CATEGORIES}
    summary["blank"] = 0
    for inning in range(1, inning_count + 1):
        category = CATEGORY_BY_CODE.get(codes_by_inning.get(inning))
        if category is None:
            summary["blank"] += 1
        else:
            summary[category] += 1
    return summary


def repeated_positions(codes_by_inning):
    """
    Positions this player fills more than once in the game, as {code: count}.

    Bench is excluded: repeat bench innings are expected and already visible in
    the Bench summary column.
    """
    counts = {}
    for code in codes_by_inning.values():
        if not code or code == BENCH_CODE:
            continue
        counts[code] = counts.get(code, 0) + 1
    return {code: n for code, n in counts.items() if n > 1}
