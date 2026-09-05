"""Load valid Wordle guess words from Kids Words data files."""

import json
import os

_KIDS_WORDS_DATA = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "projects", "kids_words", "data")
)

_guess_cache = None


def load_valid_guesses():
    """Union of grade2 keys, grade4 keys, and wordle_guesses.txt."""
    global _guess_cache
    if _guess_cache is not None:
        return _guess_cache

    words = set()
    for filename in ("grade2_words.json", "grade4_words.json"):
        path = os.path.join(_KIDS_WORDS_DATA, filename)
        try:
            with open(path, encoding="utf-8") as handle:
                words.update(json.load(handle).keys())
        except FileNotFoundError:
            continue

    guesses_path = os.path.join(_KIDS_WORDS_DATA, "wordle_guesses.txt")
    try:
        with open(guesses_path, encoding="utf-8") as handle:
            for line in handle:
                word = line.strip().lower()
                if word:
                    words.add(word)
    except FileNotFoundError:
        pass

    _guess_cache = frozenset(words)
    return _guess_cache


def is_valid_guess(word):
    cleaned = (word or "").strip().lower()
    if len(cleaned) != 5:
        return False
    return cleaned in load_valid_guesses()
