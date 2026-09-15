"""
Formation helpers for Soccer Minutes.

The slot catalog is data on the team/game (names and counts). Keys and groups
are generated here so they stay stable when a coach only renames a slot.

See docs/DATA_MODEL.md for the stored JSON shape.
"""

GROUPS = ("gk", "def", "mid", "fwd")
PITCH_BANDS = ("fwd", "mid", "def", "gk")  # top of pitch = attack
GROUP_LABELS = {
    "gk": "Goalkeeper",
    "def": "Defense",
    "mid": "Midfield",
    "fwd": "Forwards",
}
PLACEHOLDER_PREFIX = {
    "def": "DEF",
    "mid": "MID",
    "fwd": "FWD",
}

DEFAULT_PERIOD_COUNT = 2
MIN_PERIOD_COUNT = 1
MAX_PERIOD_COUNT = 6
MIN_LINE_COUNT = 0
MAX_LINE_COUNT = 8
MAX_SLOT_NAME_LEN = 20

DEFAULT_SLOT_NAMES = {
    "gk": ["GK"],
    "def": ["LB", "RB"],
    "mid": ["LM", "CM", "RM"],
    "fwd": ["ST"],
}


def default_formation():
    """Shipped 7v7 2-3-1 template."""
    slots = []
    for group in PITCH_BANDS:
        names = DEFAULT_SLOT_NAMES[group]
        if group == "gk":
            slots.append({"key": "gk", "group": "gk", "name": names[0]})
        else:
            for index, name in enumerate(names):
                slots.append(
                    {
                        "key": f"{group}_{index}",
                        "group": group,
                        "name": name,
                    }
                )
    return {"slots": slots}


def normalize_formation(raw):
    """Return a valid formation dict; fall back to the default if unusable."""
    if not isinstance(raw, dict):
        return default_formation()
    slots = raw.get("slots")
    if not isinstance(slots, list) or not slots:
        return default_formation()

    by_group = {group: [] for group in GROUPS}
    seen_keys = set()
    for item in slots:
        if not isinstance(item, dict):
            continue
        group = item.get("group")
        key = item.get("key")
        name = (item.get("name") or "").strip() or None
        if group not in GROUPS or not key or key in seen_keys:
            continue
        if group == "gk" and (key != "gk" or by_group["gk"]):
            continue
        if group != "gk" and not key.startswith(f"{group}_"):
            continue
        seen_keys.add(key)
        by_group[group].append(
            {
                "key": key,
                "group": group,
                "name": (name or _placeholder_name(group, len(by_group[group])))[
                    :MAX_SLOT_NAME_LEN
                ],
            }
        )

    if not by_group["gk"]:
        by_group["gk"] = [{"key": "gk", "group": "gk", "name": "GK"}]

    rebuilt = []
    for group in PITCH_BANDS:
        if group == "gk":
            rebuilt.append(by_group["gk"][0])
        else:
            for index, slot in enumerate(by_group[group][:MAX_LINE_COUNT]):
                rebuilt.append(
                    {
                        "key": f"{group}_{index}",
                        "group": group,
                        "name": slot["name"],
                    }
                )
    return {"slots": rebuilt}


def slots_in_group(formation, group):
    formation = normalize_formation(formation)
    return [slot for slot in formation["slots"] if slot["group"] == group]


def line_counts(formation):
    formation = normalize_formation(formation)
    return {
        "gk": 1,
        "def": len(slots_in_group(formation, "def")),
        "mid": len(slots_in_group(formation, "mid")),
        "fwd": len(slots_in_group(formation, "fwd")),
    }


def field_size(formation):
    return len(normalize_formation(formation)["slots"])


def pitch_bands(formation):
    """Slots grouped for the pitch, attack at the top."""
    formation = normalize_formation(formation)
    return [
        {
            "group": group,
            "label": GROUP_LABELS[group],
            "slots": slots_in_group(formation, group),
        }
        for group in PITCH_BANDS
    ]


def _placeholder_name(group, index):
    if group == "gk":
        return "GK"
    prefix = PLACEHOLDER_PREFIX.get(group, group.upper())
    return f"{prefix} {index + 1}"


def resize_formation(formation, def_count, mid_count, fwd_count):
    """Keep existing names; add placeholders or drop from the end of a line."""
    formation = normalize_formation(formation)
    wanted = {
        "gk": 1,
        "def": _clamp_line_count(def_count),
        "mid": _clamp_line_count(mid_count),
        "fwd": _clamp_line_count(fwd_count),
    }
    by_group = {group: slots_in_group(formation, group) for group in GROUPS}
    slots = []
    for group in PITCH_BANDS:
        current = list(by_group[group])
        target = wanted[group]
        if group == "gk":
            slot = current[0] if current else {"key": "gk", "group": "gk", "name": "GK"}
            slot = {
                "key": "gk",
                "group": "gk",
                "name": slot.get("name") or "GK",
            }
            slots.append(slot)
            continue
        while len(current) < target:
            index = len(current)
            current.append(
                {
                    "key": f"{group}_{index}",
                    "group": group,
                    "name": _placeholder_name(group, index),
                }
            )
        current = current[:target]
        for index, slot in enumerate(current):
            slots.append(
                {
                    "key": f"{group}_{index}",
                    "group": group,
                    "name": slot["name"],
                }
            )
    return {"slots": slots}


def parse_period_count(raw, default=DEFAULT_PERIOD_COUNT):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(MIN_PERIOD_COUNT, min(MAX_PERIOD_COUNT, value))


def parse_line_count(raw, default=0):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return _clamp_line_count(value)


def _clamp_line_count(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0
    return max(MIN_LINE_COUNT, min(MAX_LINE_COUNT, number))


def parse_formation_from_form(form, current_formation):
    """Read period counts from the team settings form and return a new formation."""
    current = normalize_formation(current_formation)
    current_counts = line_counts(current)
    def_count = parse_line_count(form.get("def_count"), current_counts["def"])
    mid_count = parse_line_count(form.get("mid_count"), current_counts["mid"])
    fwd_count = parse_line_count(form.get("fwd_count"), current_counts["fwd"])
    resized = resize_formation(current, def_count, mid_count, fwd_count)
    slots = []
    for slot in resized["slots"]:
        posted = form.get(f"slot_name_{slot['key']}")
        if posted is None:
            name = slot["name"]
        else:
            name = (posted or "").strip() or slot["name"]
        slots.append(
            {
                "key": slot["key"],
                "group": slot["group"],
                "name": name[:MAX_SLOT_NAME_LEN],
            }
        )
    return {"slots": slots}
