"""Summarize imported camp JSON sessions for admin preview (consensus fields)."""
from __future__ import annotations

import decimal
from typing import Any, List, Optional

from app.projects.camps.models import _format_camp_clock_12h
from app.projects.camps.session_times import parse_time_from_import


def _fmt_grade(g: Optional[int]) -> str:
    if g is None:
        return "—"
    if g == -1:
        return "Pre-K"
    if g == 0:
        return "K"
    return str(g)


def _norm_price(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    try:
        return str(decimal.Decimal(str(raw)))
    except (decimal.InvalidOperation, ValueError, TypeError):
        return None


def _session_row(s: dict) -> dict:
    return {
        "st": parse_time_from_import(s.get("start_time")),
        "et": parse_time_from_import(s.get("end_time")),
        "age_min": s.get("age_min"),
        "age_max": s.get("age_max"),
        "grade_min": s.get("grade_min"),
        "grade_max": s.get("grade_max"),
        "price": _norm_price(s.get("price")),
    }


def consensus_session_summary_lines(session_dicts: List[dict]) -> List[str]:
    """
    Human-readable lines for import preview: consensus time, ages, grades, price.
    Uses "varies" when values disagree across sessions.
    """
    if not session_dicts:
        return []

    rows = []
    for s in session_dicts:
        if isinstance(s, dict):
            rows.append(_session_row(s))
    if not rows:
        return []

    lines: List[str] = []

    def all_same(getter) -> bool:
        vals = [getter(r) for r in rows]
        return len(set(vals)) <= 1

    # Times
    if all_same(lambda r: r["st"]) and all_same(lambda r: r["et"]):
        st, et = rows[0]["st"], rows[0]["et"]
        if st or et:
            fs = _format_camp_clock_12h(st) if st else None
            fe = _format_camp_clock_12h(et) if et else None
            if fs and fe:
                lines.append(f"Daily: {fs} – {fe}")
            elif fs:
                lines.append(f"Daily: starts {fs}")
            elif fe:
                lines.append(f"Daily: ends {fe}")
    else:
        lines.append("Daily times: vary")

    any_age = any(r["age_min"] is not None or r["age_max"] is not None for r in rows)
    if any_age:
        if all_same(lambda r: (r["age_min"], r["age_max"])):
            amin, amax = rows[0]["age_min"], rows[0]["age_max"]
            if amin is not None or amax is not None:
                lines.append(f"Ages: {amin if amin is not None else '?'}–{amax if amax is not None else '?'}")
        else:
            lines.append("Ages: vary")

    any_grade = any(r["grade_min"] is not None or r["grade_max"] is not None for r in rows)
    if any_grade:
        if all_same(lambda r: (r["grade_min"], r["grade_max"])):
            gmin, gmax = rows[0]["grade_min"], rows[0]["grade_max"]
            if gmin is not None or gmax is not None:
                lines.append(
                    f"Grades: {_fmt_grade(gmin)}–{_fmt_grade(gmax)}"
                )
        else:
            lines.append("Grades: vary")

    any_price = any(r["price"] is not None for r in rows)
    if any_price:
        if all_same(lambda r: r["price"]):
            p = rows[0]["price"]
            if p is not None:
                lines.append(f"Price / session: ${decimal.Decimal(p):.2f}")
        else:
            lines.append("Price: vary")

    return lines
