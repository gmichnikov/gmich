"""
Natural language to query config prompt builder for Sports Schedules.
Builds a single prompt string with instructions, schema, allowed values, and few-shot examples.
"""

from app.projects.sports_schedules.core.constants import (
    DAYS,
    LEAGUE_CODES,
    LEAGUE_DISPLAY_NAMES,
    LEVELS,
    SPORTS,
)

# State/province name -> 2-letter code for LLM mapping
STATE_NAME_TO_CODE = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
    "Alberta": "AB",
    "British Columbia": "BC",
    "Manitoba": "MB",
    "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL",
    "Nova Scotia": "NS",
    "Northwest Territories": "NT",
    "Nunavut": "NU",
    "Ontario": "ON",
    "Prince Edward Island": "PE",
    "Quebec": "QC",
    "Saskatchewan": "SK",
    "Yukon": "YT",
}

FEW_SHOT_EXAMPLES = [
    (
        "Celtics games this week",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"either_team": ["Celtics"]},
            "date_mode": "next_week",
            "date_n": None,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "Games in Boston this weekend",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"home_city": ["Boston"]},
            "date_mode": "this_weekend",
            "date_n": None,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "Games on March 15",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {},
            "date_mode": "exact",
            "date_n": None,
            "date_exact": "2026-03-15",
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "Champions League games from Feb 20 to Feb 28",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"league": ["CL"]},
            "date_mode": "range",
            "date_n": None,
            "date_exact": None,
            "date_start": "2026-02-20",
            "date_end": "2026-02-28",
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "When do the Red Sox play?",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"either_team": ["Red Sox"]},
            "date_mode": "future",
            "date_n": None,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "Last week's NBA games",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"league": ["NBA"]},
            "date_mode": "last_n",
            "date_n": 7,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "Yankees home games next month",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"home_team": ["Yankees"]},
            "date_mode": "next_n",
            "date_n": 30,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "MLB games today",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"league": ["MLB"]},
            "date_mode": "today",
            "date_n": None,
            "date_exact": "2026-02-20",
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "College hockey games from March 1 onward",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"level": ["college"], "sport": ["hockey"]},
            "date_mode": "on_or_after",
            "date_n": None,
            "date_exact": "2026-03-01",
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "When do the Red Sox play the Yankees?",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"either_team": ["Red Sox", "Yankees"]},
            "date_mode": "future",
            "date_n": None,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "Show me college basketball games in New Jersey in the next week",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"level": ["college"], "sport": ["basketball"], "home_state": ["NJ"]},
            "date_mode": "next_week",
            "date_n": None,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "When do the Celtics play in Philly or DC?",
        {
            "dimensions": "date,time,home_team,road_team",
            "filters": {"either_team": ["Celtics"], "home_city": ["Philadelphia", "Washington"]},
            "date_mode": "future",
            "date_n": None,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "What games are in New Jersey this weekend?",
        {
            "dimensions": "date,time,league,sport,home_team,road_team",
            "filters": {"home_state": ["NJ"]},
            "date_mode": "this_weekend",
            "date_n": None,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": False,
            "limit": 500,
            "sort_column": "",
            "sort_dir": "asc",
        },
    ),
    (
        "Count of NBA games by date last week",
        {
            "dimensions": "date",
            "filters": {"league": ["NBA"]},
            "date_mode": "last_n",
            "date_n": 7,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": True,
            "limit": 500,
            "sort_column": "# Games",
            "sort_dir": "desc",
        },
    ),
    (
        "Games per league in Massachusetts next month",
        {
            "dimensions": "league",
            "filters": {"home_state": ["MA"]},
            "date_mode": "next_n",
            "date_n": 30,
            "date_exact": None,
            "date_start": None,
            "date_end": None,
            "date_year": None,
            "anchor_date": None,
            "count": True,
            "limit": 500,
            "sort_column": "# Games",
            "sort_dir": "desc",
        },
    ),
]


def build_nl_prompt(question: str, today_ymd: str) -> str:
    """
    Build a single prompt string for NL-to-query translation.
    Order: Instructions → schema → date spec → allowed values → few-shot examples → user question.
    Returns the full prompt. Output format: exactly { "config": {...} } or { "error": "..." }; no markdown.
    """
    import json

    # --- Instructions ---
    instructions = """You translate natural language questions about sports schedules into a structured JSON query config. The config is used to query a database of game schedules.

Rules:
- If the question can be answered as a schedule data query, return exactly: {"config": {...}} with the full config object.
- If the question is off-topic, subjective, ambiguous, or not representable (e.g. "Tell me a joke", "What's the best game to watch?"), return exactly: {"error": "human-readable reason"}.
- Never return both "config" and "error". Output ONLY valid JSON—no markdown, no code fences, no extra text.
"""

    # --- Schema ---
    schema = """
## Config Schema

- dimensions: Comma-separated list of column names (exclude either_team—filter-only). Valid: date, time, home_team, road_team, day, league, sport, level, home_city, home_state, location.
- filters: Object with filter keys. Low-cardinality: sport, league, level, day, home_state (use allowed values). High-cardinality (free-form strings): home_team, road_team, location, home_city. either_team: array of team name substrings (matches home OR road).
- date_mode: exact | today | on_or_after | this_weekend | range | future | next_week | last_n | next_n | year
- date_exact, date_start, date_end: YYYY-MM-DD when required
- date_n: integer for last_n, next_n
- date_year: integer for year mode
- anchor_date: optional; server fills from today when omitted for relative modes
- count: boolean (true for count queries; dimensions can be empty for total count)
- limit: 1-5000 (default 500)
- sort_column: column name or "# Games" for count
- sort_dir: "asc" or "desc"
"""

    # --- Date filter spec table ---
    date_spec = """
## Date Filter Specification (today = """ + today_ymd + """)

| date_mode | LLM must provide | LLM may omit |
|-----------|------------------|--------------|
| exact     | date_exact (YYYY-MM-DD) | — |
| today     | — | date_exact (server uses today) |
| on_or_after | date_exact (YYYY-MM-DD) | — |
| this_weekend | — | date_start, date_end (server computes) |
| range     | date_start, date_end (YYYY-MM-DD) | — |
| future    | — | anchor_date |
| next_week | — | anchor_date |
| last_n    | date_n (int > 0) | anchor_date |
| next_n    | date_n (int > 0) | anchor_date |
| year      | date_year (int) | — |

For exact/on_or_after/range: output concrete YYYY-MM-DD. Use today's date to resolve "tomorrow", "March 15" (current year if not stated), etc.
"""

    # --- Allowed values ---
    sport_vals = ", ".join(SPORTS)
    level_vals = ", ".join(LEVELS)
    day_vals = ", ".join(DAYS)
    state_mapping = "; ".join(f"{k}→{v}" for k, v in STATE_NAME_TO_CODE.items())
    league_mapping = ", ".join(
        f"{code}({LEAGUE_DISPLAY_NAMES.get(code, code)})" for code in LEAGUE_CODES
    )

    allowed_values = f"""
## Allowed Values (use exactly these codes)

- sport: {sport_vals}
- level: {level_vals}
- day: {day_vals}
- home_state: Use 2-letter codes. When user says state/province name, map to code: {state_mapping}
- league: Use code not display name. {league_mapping}
"""

    # --- Few-shot examples ---
    examples_text = "\n## Examples (today = 2026-02-20)\n\n"
    for nl, config in FEW_SHOT_EXAMPLES:
        output = {"config": config}
        output_str = json.dumps(output, separators=(",", ":"))
        examples_text += f'Q: "{nl}"\nA: {output_str}\n\n'

    # --- User question ---
    user_block = f"""
## User Question

Translate this question into the config format, or return {{"error": "..."}} if not answerable:

{question}
"""

    return (
        instructions
        + schema
        + date_spec
        + allowed_values
        + examples_text
        + user_block
    )
