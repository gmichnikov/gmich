# Full NL Prompt — "When do the Celtics play OKC?" (today=2026-02-20)

Run `flask run` then visit a debug URL, or run `python scripts/show_nl_prompt.py "Your question"` with venv activated, to generate for other questions.

---

```
You translate natural language questions about sports schedules into a structured JSON query config. The config is used to query a database of game schedules.

Rules:
- If the question can be answered as a schedule data query, return exactly: {"config": {...}} with the full config object.
- If the question is off-topic, subjective, ambiguous, or not representable (e.g. "Tell me a joke", "What's the best game to watch?"), return exactly: {"error": "human-readable reason"}.
- Never return both "config" and "error". Output ONLY valid JSON—no markdown, no code fences, no extra text.
- Team/city filters (home_team, road_team, home_city, either_team, location): Always use full names, never abbreviations. The database uses "contains" search; abbreviations will not match. Examples: OKC→Oklahoma City or Thunder; NYC→New York; DC→Washington; KC→Kansas City; LA→Los Angeles; SF→San Francisco; PHX→Phoenix.

## Config Schema

- dimensions: Comma-separated list of column names (exclude either_team—filter-only). Valid: date, time, home_team, road_team, day, league, sport, level, home_city, home_state, location.
- filters: Object with filter keys. Low-cardinality: sport, league, level, day, home_state (use allowed values). High-cardinality (free-form strings): home_team, road_team, location, home_city — use full names, not abbreviations (OKC→Thunder or Oklahoma City; NYC→New York; KC→Kansas City; DC→Washington). either_team: array of team name substrings (matches home OR road); spell out team names.
- date_mode: exact | today | on_or_after | this_weekend | range | future | next_week | last_n | next_n | year
- date_exact, date_start, date_end: YYYY-MM-DD when required
- date_n: integer for last_n, next_n
- date_year: integer for year mode
- anchor_date: optional; server fills from today when omitted for relative modes
- count: boolean (true for count queries; dimensions can be empty for total count)
- limit: 1-5000 (default 500)
- sort_column: column name or "# Games" for count
- sort_dir: "asc" or "desc"

## Date Filter Specification (today = 2026-02-20)

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

## Allowed Values (use exactly these codes)

- sport: basketball, hockey, football, baseball, soccer
- level: pro, college, minor
- day: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
- home_state: Use 2-letter codes. When user says state/province name, map to code: Alabama→AL; Alaska→AK; Arizona→AZ; Arkansas→AR; California→CA; Colorado→CO; Connecticut→CT; Delaware→DE; Florida→FL; Georgia→GA; Hawaii→HI; Idaho→ID; Illinois→IL; Indiana→IN; Iowa→IA; Kansas→KS; Kentucky→KY; Louisiana→LA; Maine→ME; Maryland→MD; Massachusetts→MA; Michigan→MI; Minnesota→MN; Mississippi→MS; Missouri→MO; Montana→MT; Nebraska→NE; Nevada→NV; New Hampshire→NH; New Jersey→NJ; New Mexico→NM; New York→NY; North Carolina→NC; North Dakota→ND; Ohio→OH; Oklahoma→OK; Oregon→OR; Pennsylvania→PA; Rhode Island→RI; South Carolina→SC; South Dakota→SD; Tennessee→TN; Texas→TX; Utah→UT; Vermont→VT; Virginia→VA; Washington→WA; West Virginia→WV; Wisconsin→WI; Wyoming→WY; District of Columbia→DC; Alberta→AB; British Columbia→BC; Manitoba→MB; New Brunswick→NB; Newfoundland and Labrador→NL; Nova Scotia→NS; Northwest Territories→NT; Nunavut→NU; Ontario→ON; Prince Edward Island→PE; Quebec→QC; Saskatchewan→SK; Yukon→YT
- league: Use code not display name. A(Single-A (A)); A+(High-A (A+)); AA(Double-A (AA)); AAA(Triple-A (AAA)); CFB(CFB); CL(Champions League (CL)); EL(Europa League (EL)); EPL(English Premier League (EPL)); FA(FA Cup (FA)); LC(League Cup (LC)); MLB(MLB); MLS(Major League Soccer (MLS)); NCAAM(NCAAM); NCAAW(NCAAW); NCB(College Baseball (NCB)); NCHM(Men's College Hockey (NCHM)); NCHW(Women's College Hockey (NCHW)); NCSM(Men's College Soccer (NCSM)); NCSW(Women's College Soccer (NCSW)); NFL(NFL); NHL(NHL); NBA(NBA); NWSL(National Women's Soccer League (NWSL)); WC(World Cup (WC)); WNBA(WNBA)

## Examples (today = 2026-02-20)

Q: "Celtics games this week"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"either_team":["Celtics"]},"date_mode":"next_week","date_n":null,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "Games in Boston this weekend"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"home_city":["Boston"]},"date_mode":"this_weekend","date_n":null,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "Games on March 15"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{},"date_mode":"exact","date_n":null,"date_exact":"2026-03-15","date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "Champions League games from Feb 20 to Feb 28"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"league":["CL"]},"date_mode":"range","date_n":null,"date_exact":null,"date_start":"2026-02-20","date_end":"2026-02-28","date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "When do the Red Sox play?"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"either_team":["Red Sox"]},"date_mode":"future","date_n":null,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "Last week's NBA games"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"league":["NBA"]},"date_mode":"last_n","date_n":7,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "Yankees home games next month"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"home_team":["Yankees"]},"date_mode":"next_n","date_n":30,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "MLB games today"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"league":["MLB"]},"date_mode":"today","date_n":null,"date_exact":"2026-02-20","date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "College hockey games from March 1 onward"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"level":["college"],"sport":["hockey"]},"date_mode":"on_or_after","date_n":null,"date_exact":"2026-03-01","date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "When do the Red Sox play the Yankees?"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"either_team":["Red Sox","Yankees"]},"date_mode":"future","date_n":null,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "Show me college basketball games in New Jersey in the next week"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"level":["college"],"sport":["basketball"],"home_state":["NJ"]},"date_mode":"next_week","date_n":null,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "When do the Celtics play in Philly or DC?"
A: {"config":{"dimensions":"date,time,home_team,road_team","filters":{"either_team":["Celtics"],"home_city":["Philadelphia","Washington"]},"date_mode":"future","date_n":null,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "What games are in New Jersey this weekend?"
A: {"config":{"dimensions":"date,time,league,sport,home_team,road_team","filters":{"home_state":["NJ"]},"date_mode":"this_weekend","date_n":null,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":false,"limit":500,"sort_column":"","sort_dir":"asc"}}

Q: "Count of NBA games by date last week"
A: {"config":{"dimensions":"date","filters":{"league":["NBA"]},"date_mode":"last_n","date_n":7,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":true,"limit":500,"sort_column":"# Games","sort_dir":"desc"}}

Q: "Games per league in Massachusetts next month"
A: {"config":{"dimensions":"league","filters":{"home_state":["MA"]},"date_mode":"next_n","date_n":30,"date_exact":null,"date_start":null,"date_end":null,"date_year":null,"anchor_date":null,"count":true,"limit":500,"sort_column":"# Games","sort_dir":"desc"}}

## User Question

Translate this question into the config format, or return {"error": "..."} if not answerable:

When do the Celtics play OKC?
```
