"""Sports scores for digest — ESPN scoreboard filtered to watched teams."""

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from app.projects.sports_schedule_admin.core.espn_client import ESPNClient

logger = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
SUPPORTED_LEAGUE_CODES = ("NFL", "NBA", "MLB", "NHL")
_MAX_ROWS = 25


def _scoreboard_url(league_code: str) -> str:
    client = ESPNClient()
    if league_code not in client.LEAGUE_MAP:
        raise ValueError(f"Unsupported league: {league_code}")
    sport, league, _ = client.LEAGUE_MAP[league_code]
    return f"{ESPN_BASE}/{sport}/{league}/scoreboard"


def _dates_param(user_tz: str) -> str:
    """Yesterday through today in the user's IANA zone (inclusive, two calendar days)."""
    z = ZoneInfo(user_tz)
    today = datetime.now(z).date()
    y = today - timedelta(days=1)
    return f"{y.strftime('%Y%m%d')}-{today.strftime('%Y%m%d')}"


def _score_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_utc_start(date_str: str):
    if not date_str:
        return None
    try:
        s = date_str
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _parse_event_for_digest(event) -> dict | None:
    """One row: team ids, names, scores, status, start time (for sorting)."""
    try:
        eid = str(event.get("id", ""))
        comp = event["competitions"][0]
        home_id = away_id = ""
        home_name = away_name = ""
        home_score = away_score = None
        for c in comp.get("competitors", []):
            t = c.get("team", {})
            tid = t.get("id")
            ts = str(tid) if tid is not None else ""
            name = t.get("displayName", "")
            sc = _score_int(c.get("score"))
            if c.get("homeAway") == "home":
                home_id, home_name, home_score = ts, name, sc
            else:
                away_id, away_name, away_score = ts, name, sc

        st = event.get("status", {}).get("type", {})
        state = st.get("state", "pre")
        detail = st.get("shortDetail", "")

        start_utc = _parse_utc_start(event.get("date", ""))
        if start_utc and start_utc.tzinfo is None:
            start_utc = start_utc.replace(tzinfo=timezone.utc)

        return {
            "event_id": eid,
            "away_id": away_id,
            "home_id": home_id,
            "away_team": away_name,
            "home_team": home_name,
            "away_score": away_score,
            "home_score": home_score,
            "state": state,
            "detail": detail,
            "start_utc": start_utc,
        }
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("daily_email sports: skip event parse: %s", exc)
        return None


def _fetch_league_scoreboard(league_code: str, dates_param: str) -> list | None:
    """Return raw `events` list or None on HTTP failure."""
    try:
        url = _scoreboard_url(league_code)
        r = requests.get(url, params={"dates": dates_param}, timeout=20)
        r.raise_for_status()
        return r.json().get("events", [])
    except Exception as exc:
        logger.error("daily_email sports: ESPN %s %s: %s", league_code, dates_param, exc)
        return None


def render_sports_section(watches: list, user_timezone: str) -> str | None:
    """
    Fetch scoreboards per distinct league, keep games involving any watched team.

    watches: list of DailyEmailSportsWatch (league_code, espn_team_id, team_display_name).
    user_timezone: IANA string for the date range (yesterday–today in user's calendar).
    """
    if not watches:
        return (
            '<div class="de-module de-module-sports">'
            '<div class="de-module-header">&#x1F3C0; Scores</div>'
            '<div style="padding:12px 14px;color:#666;font-size:14px;">'
            "Add teams in settings to see scores here."
            "</div></div>"
        )

    dates_param = _dates_param(user_timezone)

    by_league: dict[str, list] = {}
    for w in watches:
        if w.league_code not in SUPPORTED_LEAGUE_CODES:
            continue
        by_league.setdefault(w.league_code, []).append(w)

    if not by_league:
        return None

    # Per-league: which team ids are we watching?
    watched_by_league: dict[str, set[str]] = {
        league: {str(x.espn_team_id) for x in rows}
        for league, rows in by_league.items()
    }

    all_games: list[dict] = []
    ok_leagues = 0
    failed_leagues = 0
    for league_code in by_league:
        evs = _fetch_league_scoreboard(league_code, dates_param)
        if evs is None:
            failed_leagues += 1
            continue
        ok_leagues += 1
        wset = watched_by_league[league_code]
        for ev in evs:
            row = _parse_event_for_digest(ev)
            if not row:
                continue
            if (
                row["home_id"] in wset
                or row["away_id"] in wset
            ):
                row["league_code"] = league_code
                all_games.append(row)

    if not all_games and failed_leagues > 0 and ok_leagues == 0:
        return None

    # Sort: most recent first (by start time desc); missing time last
    all_games.sort(
        key=lambda g: (g["start_utc"] or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )

    total = len(all_games)
    if total == 0:
        inner = (
            '<div style="padding:12px 14px;color:#666;font-size:14px;">'
            "No games for your teams in the last two days (yesterday and today in your timezone)."
            "</div>"
        )
    else:
        shown = all_games[:_MAX_ROWS]
        more = total - len(shown)
        body_rows = ""
        for g in shown:
            away = g["away_team"][:20]
            home = g["home_team"][:20]
            st = g["state"]
            if st == "post" and g["home_score"] is not None and g["away_score"] is not None:
                score = f"{g['away_score']} - {g['home_score']}"
                badge = f'<span style="font-weight:700;">{score}</span> <span style="color:#888;">Final</span>'
            elif st == "in":
                hs = g["home_score"] if g["home_score"] is not None else "\u2014"
                ahs = g["away_score"] if g["away_score"] is not None else "\u2014"
                badge = f"{ahs} - {hs} <span style=\'color:#c60;\'>LIVE</span>"
            else:
                badge = f'<span style="color:#666;">{g.get("detail") or "Scheduled"}</span>'

            lg = g["league_code"]
            body_rows += (
                f'<tr><td style="padding:6px 10px;border-bottom:1px solid #eee;'
                f'font-size:12px;color:#999;">{lg}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;'
                f'font-size:14px;">{away} <span style="color:#aaa;">@</span> {home}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #eee;'
                f'text-align:right;white-space:nowrap;">{badge}</td></tr>'
            )
        more_html = (
            f'<p style="margin:8px 0 0;font-size:12px;color:#999;">+{more} more (see ESPN)</p>'
            if more > 0
            else ""
        )
        inner = (
            f'<table style="width:100%;border-collapse:collapse;">{body_rows}</table>{more_html}'
        )

    return (
        '<div class="de-module de-module-sports">'
        '<div class="de-module-header">&#x1F3C0; Scores (yesterday &amp; today)</div>'
        f'<div style="padding:0 4px 10px;">{inner}'
        f'<p style="margin:8px 0 0;font-size:10px;color:#aaa;">Data from ESPN (unofficial API).</p>'
        "</div></div>"
    )
