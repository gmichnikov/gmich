"""Fetch and store NFL game kickoff times from ESPN."""

import logging
from datetime import datetime

import requests

from app import db
from app.projects.nfl_survivor.log import log_nfl_survivor
from app.projects.nfl_survivor.models import NflSurvivorGame
from app.projects.nfl_survivor.utils import UTC, map_team_names_to_ids

logger = logging.getLogger(__name__)


def _parse_espn_kickoff(date_str):
    """Parse ESPN ISO date (UTC) to timezone-aware datetime."""
    if not date_str:
        return None
    if date_str.endswith("Z"):
        date_str = date_str.replace("Z", "+00:00")
    return datetime.fromisoformat(date_str).astimezone(UTC)


def fetch_schedule_for_week(season, week, *, log=True, actor_id=None, source="cron"):
    """
    Load kickoff times for all teams playing in `week` from ESPN.
    Returns number of team rows upserted.
    """
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        f"?dates={season.espn_season_year}&seasontype=2&week={week}"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()

    name_to_id = map_team_names_to_ids()
    upserted = 0
    now = datetime.utcnow()

    for event in data.get("events", []):
        kickoff = _parse_espn_kickoff(event.get("date"))
        if kickoff is None:
            continue
        espn_event_id = str(event.get("id", ""))
        for competition in event.get("competitions", []):
            comp_kickoff = _parse_espn_kickoff(competition.get("date")) or kickoff
            for competitor in competition.get("competitors", []):
                team_name = competitor.get("team", {}).get("displayName")
                team_id = name_to_id.get(team_name)
                if not team_id:
                    logger.warning("ESPN schedule: unknown team %r week %s", team_name, week)
                    continue

                existing = NflSurvivorGame.query.filter_by(
                    season_id=season.id, week=week, team_id=team_id
                ).first()
                kickoff_naive = comp_kickoff.astimezone(UTC).replace(tzinfo=None)
                if existing:
                    existing.kickoff = kickoff_naive
                    existing.espn_event_id = espn_event_id
                    existing.updated_at = now
                else:
                    db.session.add(
                        NflSurvivorGame(
                            season_id=season.id,
                            week=week,
                            team_id=team_id,
                            kickoff=kickoff_naive,
                            espn_event_id=espn_event_id,
                            updated_at=now,
                        )
                    )
                upserted += 1

    if log:
        label = "Manual" if source == "manual" else "Cron"
        log_nfl_survivor(
            "Fetch Schedule",
            f"{label} fetch schedule for week {week} ({season.name}): {upserted} teams",
            actor_id=actor_id,
        )
    db.session.commit()
    return upserted


def fetch_schedule_for_active_weeks(season, *, actor_id=None, source="cron"):
    """Fetch current pick week and the next week (for early future picks)."""
    from app.projects.nfl_survivor.utils import get_current_pick_week

    current_week = get_current_pick_week(season)
    weeks = {current_week}
    if current_week < season.max_weeks:
        weeks.add(current_week + 1)

    total = 0
    for week in sorted(weeks):
        total += fetch_schedule_for_week(
            season, week, log=False, actor_id=actor_id, source=source
        )

    label = "Manual" if source == "manual" else "Cron"
    log_nfl_survivor(
        "Fetch Schedule",
        (
            f"{label} fetch schedule for weeks {sorted(weeks)} "
            f"({season.name}): {total} team rows"
        ),
        actor_id=actor_id,
    )
    db.session.commit()
    return total, sorted(weeks)
