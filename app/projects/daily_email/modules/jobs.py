"""Job listings from public ATS boards (Ashby, Greenhouse) for the daily digest."""

import logging
import re
from typing import NamedTuple
from urllib.parse import urlparse, unquote

import requests

logger = logging.getLogger(__name__)

ATS_ASHBY = "ashby"
ATS_GREENHOUSE = "greenhouse"
ALLOWED_ATS = frozenset({ATS_ASHBY, ATS_GREENHOUSE})

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board"
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards"
_MAX_PER_BOARD = 12


class BoardFetchResult(NamedTuple):
    """Successful HTTP parse. ``unfiltered_count`` = jobs with a title before the filter; ``rows`` = after filter (capped)."""

    rows: list[dict]
    unfiltered_count: int


def parse_ashby_slug_from_input(raw: str) -> str | None:
    """
    Return Ashby company slug, or None if the input is empty or not recognizable.

    Accepts: bare slug, or a URL on *.ashbyhq.com (e.g. jobs.ashbyhq.com/{slug}/...).
    """
    s = (raw or "").strip()
    if not s:
        return None
    s = s.strip()
    if "ashbyhq.com" in s:
        if not s.startswith("http"):
            s = f"https://{s}"
        p = urlparse(s)
        path = (p.path or "").strip("/")
        if path:
            first = unquote(path.split("/")[0])
            if first and re.match(r"^[a-zA-Z0-9][-a-zA-Z0-9_]{0,250}$", first):
                return first
        host = (p.netloc or "").lower()
        if host.endswith("ashbyhq.com"):
            sub = host.rsplit("ashbyhq.com", 1)[0].rstrip(".")
            for part in reversed(sub.split(".")):
                if part and part not in ("www", "jobs", "com") and re.match(
                    r"^[a-zA-Z0-9][-a-zA-Z0-9_]{0,250}$", part
                ):
                    return part
        return None
    if re.match(r"^[a-zA-Z0-9][-a-zA-Z0-9_]{0,250}$", s):
        return s
    return None


def parse_greenhouse_token_from_input(raw: str) -> str | None:
    """
    Return Greenhouse board token, or None if empty or not recognizable.

    Accepts: bare token or a URL on *.greenhouse.io (e.g. boards.greenhouse.io/{token}).
    """
    s = (raw or "").strip()
    if not s:
        return None
    if "greenhouse.io" in s:
        if not s.startswith("http"):
            s = f"https://{s}"
        p = urlparse(s)
        path = (p.path or "").strip("/")
        if path:
            first = unquote(path.split("/")[0])
            if first and re.match(r"^[a-zA-Z0-9][-a-zA-Z0-9_]{0,200}$", first):
                return first
        return None
    if re.match(r"^[a-zA-Z0-9][-a-zA-Z0-9_]{0,200}$", s):
        return s
    return None


def _iter_ashby_postings(data) -> list:
    """Normalize Ashby JSON to a list of job dicts (structure varies by API version)."""
    if not isinstance(data, dict):
        return []
    d = data.get("data", data)
    if isinstance(d, list):
        return d
    if not isinstance(d, dict):
        return []
    for key in ("jobPostings", "postings", "jobs", "openings"):
        v = d.get(key)
        if isinstance(v, list):
            return v
    if "results" in d and isinstance(d["results"], list):
        return d["results"]
    return []


def fetch_ashby_jobs(slug: str, filter_phrase: str | None) -> BoardFetchResult | None:
    """
    Fetch public job board JSON. Returns ``None`` on HTTP/parse failure; otherwise
    ``BoardFetchResult`` (rows may be empty; ``unfiltered_count`` is jobs with a title before filter).
    """
    url = f"{ASHBY_API}/{slug}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.error("daily_email jobs: Ashby fetch failed for slug=%r: %s", slug, exc)
        return None

    raw_list = _iter_ashby_postings(data)
    phrase = (filter_phrase or "").strip().lower()
    out: list[dict] = []
    unfiltered = 0
    for p in raw_list:
        if not isinstance(p, dict):
            continue
        title = (p.get("title") or p.get("name") or "").strip()
        if not title:
            continue
        unfiltered += 1
        if phrase and phrase not in title.lower():
            dep = (p.get("departmentName") or p.get("department") or "") or ""
            if phrase not in str(dep).lower():
                continue
        u = p.get("jobUrl") or p.get("url") or p.get("link") or ""
        if not u and p.get("id") and slug:
            u = f"https://jobs.ashbyhq.com/{slug}/"
        team = p.get("teamName") or p.get("departmentName") or p.get("team") or None
        loc = p.get("locationName") or p.get("location") or None
        if isinstance(loc, dict):
            loc = loc.get("name") or loc.get("label")
        out.append(
            {
                "title": title,
                "url": (u or "").strip(),
                "team": team,
                "location": loc,
            }
        )
        if len(out) >= _MAX_PER_BOARD:
            break

    return BoardFetchResult(rows=out, unfiltered_count=unfiltered)


def ashby_board_url(slug: str) -> str:
    return f"https://jobs.ashbyhq.com/{slug}"


def _greenhouse_departments_text(job: dict) -> str:
    parts = []
    for d in job.get("departments") or []:
        if isinstance(d, dict) and d.get("name"):
            parts.append(str(d["name"]))
    return " ".join(parts)


def _greenhouse_office_location(job: dict) -> str | None:
    for o in job.get("offices") or []:
        if isinstance(o, dict) and o.get("name"):
            return o["name"]
    loc = job.get("location")
    if isinstance(loc, dict):
        return loc.get("name") or loc.get("name_with_office")
    if isinstance(loc, str):
        return loc
    return None


def fetch_greenhouse_jobs(token: str, filter_phrase: str | None) -> BoardFetchResult | None:
    """Public Greenhouse Job Board API. ``None`` on failure; else ``BoardFetchResult``."""
    url = f"{GREENHOUSE_API}/{token}/jobs"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        logger.error("daily_email jobs: Greenhouse fetch failed for token=%r: %s", token, exc)
        return None

    if not isinstance(data, dict):
        return None
    raw_jobs = data.get("jobs")
    if not isinstance(raw_jobs, list):
        raw_jobs = []

    phrase = (filter_phrase or "").strip().lower()
    out: list[dict] = []
    unfiltered = 0
    for j in raw_jobs:
        if not isinstance(j, dict):
            continue
        title = (j.get("title") or "").strip()
        if not title:
            continue
        unfiltered += 1
        dep_txt = _greenhouse_departments_text(j)
        if phrase and phrase not in title.lower() and phrase not in dep_txt.lower():
            continue
        u = (j.get("absolute_url") or j.get("url") or "").strip()
        team = dep_txt or None
        loc = _greenhouse_office_location(j)
        out.append(
            {
                "title": title,
                "url": u,
                "team": team,
                "location": loc,
            }
        )
        if len(out) >= _MAX_PER_BOARD:
            break

    return BoardFetchResult(rows=out, unfiltered_count=unfiltered)


def greenhouse_board_url(token: str) -> str:
    return f"https://boards.greenhouse.io/{token}"


def parse_board_token_for_ats(ats: str, raw: str) -> str | None:
    """Parse user input for the given ATS; return normalized token or None."""
    if ats == ATS_ASHBY:
        return parse_ashby_slug_from_input(raw)
    if ats == ATS_GREENHOUSE:
        return parse_greenhouse_token_from_input(raw)
    return None


def ats_label(ats: str) -> str:
    if ats == ATS_ASHBY:
        return "Ashby"
    if ats == ATS_GREENHOUSE:
        return "Greenhouse"
    return ats


def validate_and_fetch(ats: str, board_token: str, filter_phrase: str | None) -> list[dict] | None:
    """Live fetch for validation on save. None means HTTP/parse failure; empty list is valid."""
    if ats == ATS_ASHBY:
        res = fetch_ashby_jobs(board_token, filter_phrase)
    elif ats == ATS_GREENHOUSE:
        res = fetch_greenhouse_jobs(board_token, filter_phrase)
    else:
        return None
    if res is None:
        return None
    return res.rows


def _error_line(ats: str, board_token: str) -> str:
    return (
        f'<p style="margin:6px 0 10px;font-size:13px;color:#a94442;">'
        f"Couldn\u2019t load {ats_label(ats)} board \u2014 {board_token}."
        f"</p>"
    )


def _empty_board_block(
    ats: str,
    board_token: str,
    board_url: str,
    unfiltered_count: int,
    filter_phrase: str | None,
    is_first: bool,
) -> str:
    if unfiltered_count == 0:
        msg = "No open jobs on this board right now."
    else:
        msg = "No jobs match your filter. Try a different keyword or see the full board for all openings."
    ats_l = ats_label(ats)
    sub_style = (
        "padding:0;"
        if is_first
        else "margin:14px 0 0;padding:10px 0 0;border-top:1px solid #eee;"
    )
    return (
        f'<div style="{sub_style}">'
        f'<div style="font-size:12px;font-weight:600;color:#555;margin-bottom:6px;">{ats_l} &mdash; {board_token}</div>'
        f'<p style="margin:0 0 8px;font-size:13px;color:#666;">{msg}</p>'
        f'<p style="margin:0;">'
        f'<a href="{board_url}" style="color:#3a7dc9;font-size:12px;">See full board on {ats_l}</a>'
        f"</p></div>"
    )


def _rows_html(
    rows: list[dict], board_url: str, ats: str, board_token: str, is_first: bool
) -> str:
    body = ""
    for r in rows:
        title = r.get("title", "")
        u = (r.get("url") or "").strip() or board_url
        sub = " — ".join(
            x for x in (r.get("team"), r.get("location")) if x
        )
        line = '<div style="margin:6px 0 10px;">'
        line += f'<a href="{u}" style="color:#1a1a2e;font-weight:600;">{title}</a>'
        if sub:
            line += f'<div style="font-size:12px;color:#888;">{sub}</div>'
        line += "</div>"
        body += line
    b = board_url
    ats_l = ats_label(ats)
    sub_style = (
        "padding:0;"
        if is_first
        else "margin:14px 0 0;padding:10px 0 0;border-top:1px solid #eee;"
    )
    return (
        f'<div style="{sub_style}">'
        f'<div style="font-size:12px;font-weight:600;color:#555;margin-bottom:6px;">{ats_l} &mdash; {board_token}</div>'
        f"{body}"
        f'<p style="margin:6px 0 0;">'
        f'<a href="{b}" style="color:#3a7dc9;font-size:12px;">See full board on {ats_l}</a>'
        f"</p></div>"
    )


def render_jobs_section(watches) -> str | None:
    """
    Build HTML for the jobs module.

    ``watches``: list of `DailyEmailJobWatch` (ordered), or None / empty.
    Returns ``None`` (every board failed to load) or HTML (including per-board
    "no jobs" / "no filter matches" messages). Empty string is only used when
    the module should omit the section (rare; no applicable watches).
    """
    wlist = list(watches or [])
    if not wlist:
        return (
            '<div class="de-module de-module-jobs">'
            '<div class="de-module-header">&#x1F4BC; Job Listings</div>'
            '<div style="padding:12px 14px;color:#666;font-size:14px;">'
            "Add one or more job boards (Ashby and Greenhouse) in settings."
            "</div></div>"
        )

    parts: list[str] = []
    any_fetch_ok = False
    block_idx = 0

    for w in wlist:
        if w.ats not in ALLOWED_ATS:
            continue
        token = (w.board_token or "").strip()
        if not token:
            continue
        fp = (w.filter_phrase or "").strip() or None
        res: BoardFetchResult | None
        if w.ats == ATS_ASHBY:
            res = fetch_ashby_jobs(token, fp)
        elif w.ats == ATS_GREENHOUSE:
            res = fetch_greenhouse_jobs(token, fp)
        else:
            res = None
        if res is None:
            parts.append(_error_line(w.ats, token))
            continue
        any_fetch_ok = True
        burl = (
            ashby_board_url(token) if w.ats == ATS_ASHBY else greenhouse_board_url(token)
        )
        is_first = block_idx == 0
        if res.rows:
            parts.append(_rows_html(res.rows, burl, w.ats, token, is_first=is_first))
        else:
            parts.append(
                _empty_board_block(
                    w.ats, token, burl, res.unfiltered_count, fp, is_first=is_first
                )
            )
        block_idx += 1

    if not any_fetch_ok:
        if parts:
            return (
                '<div class="de-module de-module-jobs">'
                '<div class="de-module-header">&#x1F4BC; Job Listings</div>'
                '<div style="padding:4px 14px 12px;">' + "".join(parts) + "</div></div>"
            )
        return None
    return (
        '<div class="de-module de-module-jobs">'
        '<div class="de-module-header">&#x1F4BC; Job Listings</div>'
        '<div style="padding:4px 14px 12px;">' + "".join(parts) + "</div></div>"
    )
