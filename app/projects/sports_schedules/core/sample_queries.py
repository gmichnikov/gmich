"""
Sample queries for Sports Schedules. Everyone sees these regardless of login state.
"""
from datetime import datetime, timedelta

SAMPLE_QUERIES = [
    {
        "id": "sample-nj-weekend",
        "name": "Games in New Jersey this weekend",
        "config": {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"home_state": ["NJ"]},
            "date_mode": "this_weekend",
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    },
    {
        "id": "sample-celtics-month",
        "name": "Celtics games in the next month",
        "config": {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"either_team": ["Celtics"]},
            "date_mode": "next_n",
            "date_n": 30,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    },
]


def _compute_this_weekend(anchor_ymd: str) -> tuple[str, str]:
    """Compute Friday–Sunday date range for 'this weekend' from anchor date."""
    d = datetime.strptime(anchor_ymd, "%Y-%m-%d").date()
    day = d.weekday()  # Mon=0, Fri=4, Sat=5, Sun=6
    if day >= 4:  # Fri, Sat, or Sun — we're in or past the weekend
        days_back = 2 if day == 6 else (day - 4)  # Sun: 2, Sat: 1, Fri: 0
        friday = d - timedelta(days=days_back)
    else:
        days_forward = 4 - day
        friday = d + timedelta(days=days_forward)
    sunday = friday + timedelta(days=2)
    return friday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def config_to_params(config: dict, anchor_date: str | None = None) -> dict:
    """
    Convert stored config to the params dict that build_sql() expects.
    Used for validating sample configs. Frontend has equivalent logic for loading.
    """
    anchor = anchor_date or datetime.utcnow().strftime("%Y-%m-%d")
    params = {
        "dimensions": config.get("dimensions") or "",
        "filters": config.get("filters") or {},
        "date_mode": config.get("date_mode") or "",
        "date_exact": config.get("date_exact") or "",
        "date_start": config.get("date_start") or "",
        "date_end": config.get("date_end") or "",
        "date_year": config.get("date_year") or "",
        "date_n": config.get("date_n"),
        "anchor_date": config.get("anchor_date") or anchor,
        "count": config.get("count", False),
        "limit": config.get("limit", 500),
        "sort_column": config.get("sort_column") or "",
        "sort_dir": config.get("sort_dir") or "asc",
    }
    # For relative date modes, fill date_start/date_end or anchor
    mode = params["date_mode"]
    if mode == "this_weekend" and not params["date_start"]:
        params["date_start"], params["date_end"] = _compute_this_weekend(anchor)
    elif mode in ("next_week", "last_n", "next_n") and not params["anchor_date"]:
        params["anchor_date"] = anchor
    return params
