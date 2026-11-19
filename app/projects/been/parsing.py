"""Date and paste-line parsing for Where I've Been."""

import re
from datetime import date

_WHEN = re.compile(r"^(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?$")
_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

DATE_HELP = "Use a date like 2019, 2019-05, or 2019-05-02."


class VisitInputError(ValueError):
    """The user can fix this and try again."""


def parse_when(raw):
    """Return (date or None, precision or None).

    Precision is 'year', 'month', or 'day'. A blank value means the date is unknown.
    """
    text = (raw or "").strip()
    if not text:
        return None, None
    match = _WHEN.match(text)
    if not match:
        raise VisitInputError(DATE_HELP)
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else None
    day = int(match.group(3)) if match.group(3) else None
    if year < 1800 or year > 2100:
        raise VisitInputError(DATE_HELP)
    try:
        if day is not None:
            return date(year, month, day), "day"
        if month is not None:
            return date(year, month, 1), "month"
        return date(year, 1, 1), "year"
    except ValueError as exc:
        raise VisitInputError(DATE_HELP) from exc


def format_when(visited_on, precision):
    if visited_on is None or not precision:
        return ""
    if precision == "year":
        return str(visited_on.year)
    if precision == "month":
        return f"{_MONTHS[visited_on.month - 1]} {visited_on.year}"
    if precision == "day":
        return f"{_MONTHS[visited_on.month - 1]} {visited_on.day}, {visited_on.year}"
    return ""


def when_input_value(visited_on, precision):
    if visited_on is None or not precision:
        return ""
    if precision == "year":
        return f"{visited_on.year:04d}"
    if precision == "month":
        return f"{visited_on.year:04d}-{visited_on.month:02d}"
    return visited_on.isoformat()


def parse_paste_line(line):
    """Return {'query', 'when'} or None for a blank or comment line.

    A trailing comma-separated date is pulled off only when it parses.
    'Washington, DC' stays one query.
    """
    text = (line or "").strip()
    if not text or text.startswith("#"):
        return None
    if "," in text:
        left, right = text.rsplit(",", 1)
        right = right.strip()
        # Split on a date-shaped tail even when the date itself is invalid,
        # so "Lisbon, 2019-13" is a date error and not a search for that whole line.
        if right and _WHEN.match(right):
            query = left.strip().strip(",").strip()
            if not query:
                return None
            return {"query": query, "when": right}
    query = text.strip(",").strip()
    if not query:
        return None
    return {"query": query, "when": ""}
