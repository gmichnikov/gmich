#!/usr/bin/env python3
"""Check that all words in Speaker phrases exist in core words or common.txt."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
APP_JS = REPO_ROOT / "app/projects/speaker/static/speaker/app.js"
COMMON_TXT = REPO_ROOT / "app/projects/speaker/common.txt"


def strip_apostrophes(text: str) -> str:
    return re.sub(r"[''`´]", "", text)


def match_key(text: str) -> str:
    return strip_apostrophes(text.lower()).replace(".", "")


def strip_trailing_punct(word: str) -> str:
    return re.sub(r"[?,.!]+$", "", word)


def load_core_words() -> set[str]:
    text = APP_JS.read_text(encoding="utf-8")
    block = text.split("var CORE_WORDS = [", 1)[1].split("];", 1)[0]
    words = re.findall(r'"([^"]+)"', block)
    return {match_key(w) for w in words}


def load_common_words() -> set[str]:
    keys: set[str] = set()
    if not COMMON_TXT.exists():
        return keys
    for line in COMMON_TXT.read_text(encoding="utf-8").splitlines():
        word = line.strip()
        if word:
            keys.add(match_key(word))
    return keys


def words_in_phrase(phrase: str) -> list[str]:
    return [strip_trailing_punct(w) for w in phrase.split() if strip_trailing_punct(w)]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: check_words.py \"Phrase one\" \"Phrase two\" ...", file=sys.stderr)
        return 1

    core = load_core_words()
    common = load_common_words()
    known = core | common

    missing_by_phrase: dict[str, list[str]] = {}
    all_missing: list[str] = []

    for phrase in sys.argv[1:]:
        missing = []
        for word in words_in_phrase(phrase):
            if match_key(word) not in known:
                missing.append(word)
                if word not in all_missing:
                    all_missing.append(word)
        if missing:
            missing_by_phrase[phrase] = missing

    if not missing_by_phrase:
        print("OK — all words covered by core words or common.txt")
        return 0

    print("Missing words (append to end of common.txt):\n")
    for phrase, words in missing_by_phrase.items():
        print(f"  {phrase!r}")
        print(f"    → {', '.join(words)}")
    print(f"\nUnique to append: {', '.join(all_missing)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
