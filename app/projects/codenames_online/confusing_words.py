"""Global registry of words too confusing for kids."""

from sqlalchemy.exc import ProgrammingError, OperationalError

from app import db
from app.projects.codenames_online.models import CodenamesConfusingWord
from app.projects.codenames_online.word_lists import list_word_lists, load_word_list


def normalize_word(word):
    return (word or "").strip().upper()


def get_confusing_set():
    try:
        return {row.word for row in CodenamesConfusingWord.query.all()}
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return set()


def is_confusing(word):
    return normalize_word(word) in get_confusing_set()


def tag_confusing(word, user_id=None):
    normalized = normalize_word(word)
    if not normalized:
        raise ValueError("Word is required.")
    existing = CodenamesConfusingWord.query.get(normalized)
    if existing:
        return existing
    row = CodenamesConfusingWord(
        word=normalized,
        created_by_user_id=user_id,
    )
    db.session.add(row)
    db.session.commit()
    return row


def untag_confusing(word):
    normalized = normalize_word(word)
    row = CodenamesConfusingWord.query.get(normalized)
    if row:
        db.session.delete(row)
        db.session.commit()
    return normalized


def all_words_catalog():
    """Unique words across all lists with list membership and confusing flag."""
    confusing = get_confusing_set()
    word_lists = {}
    for entry in list_word_lists():
        for word in load_word_list(entry["id"]):
            normalized = normalize_word(word)
            if normalized not in word_lists:
                word_lists[normalized] = []
            if entry["id"] not in word_lists[normalized]:
                word_lists[normalized].append(entry["id"])
    catalog = []
    for word in sorted(word_lists):
        catalog.append(
            {
                "word": word,
                "lists": word_lists[word],
                "confusing": word in confusing,
            }
        )
    return catalog
