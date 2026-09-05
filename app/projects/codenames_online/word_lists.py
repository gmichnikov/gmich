"""Load bundled Codenames word lists from JSON assets."""

import json
from functools import lru_cache
from pathlib import Path

WORD_LISTS_DIR = Path(__file__).resolve().parent / "word_lists"
MANIFEST_PATH = WORD_LISTS_DIR / "manifest.json"
BOARD_SIZE = 25


@lru_cache(maxsize=1)
def get_manifest():
    with MANIFEST_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def list_word_lists():
    """Return manifest entries: [{ id, name, word_count, default? }, ...]."""
    return get_manifest()["lists"]


def default_word_list_id():
    for entry in list_word_lists():
        if entry.get("default"):
            return entry["id"]
    lists = list_word_lists()
    if not lists:
        raise RuntimeError("No word lists configured.")
    return lists[0]["id"]


@lru_cache(maxsize=None)
def load_word_list(word_list_id):
    path = WORD_LISTS_DIR / f"{word_list_id}.json"
    if not path.is_file():
        raise KeyError(f"Unknown word list: {word_list_id}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    words = data.get("words") or []
    if len(words) < BOARD_SIZE:
        raise ValueError(
            f"Word list {word_list_id!r} needs at least {BOARD_SIZE} words; got {len(words)}."
        )
    return words
