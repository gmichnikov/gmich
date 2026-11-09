# Sports Schedules — MCP Query Plan

Let a person ask "What games are in NJ this weekend?" or "MLB games within 50 miles of 07928 in the next 30 days" from Claude, ChatGPT, Cursor, or Claude Code, and get rows from the same schedule data and the same query logic the web UI uses.

The host model is the natural-language layer. This app exposes two read-only tools on the MCP server that is already deployed at `POST /mcp`. No new service, no new database, no Gemini call, and no credit charge.

**Status:** not started

---

## Success criteria

- Adding the existing connector URL (`https://<app-domain>/mcp`) is enough. No new infrastructure.
- A plain-English question makes the host model call a tool, receive rows, and answer in conversation.
- The same filters the UI supports produce the same rows, including distance, women's and men's leagues, and Eastern times.
- Relative dates ("this weekend", "next week", "today") use a US Eastern anchor at any time of day.
- Callers cannot submit SQL. Every query goes through the existing validated query builder.
- A bad filter value comes back as a tool error the model can correct, and is not silently dropped.

## Non-goals

- Changing the in-app Ask feature (`POST /sports-schedules/api/nl-query`), `GET /sports-schedules/api/query`, or `flask sports_schedules agent-query`.
- Write access to the schedule data.
- Geocoding a city name into a zip code.
- A new date mode the UI does not have (`tomorrow`, calendar month, `year`).
- Replacing the hand-rolled JSON-RPC handler with the official MCP Python SDK.
- Requiring a bearer token. claude.ai connectors cannot send custom headers, and a required secret would break "paste the URL."

---

## What already exists

### Data

DoltHub table `` `combined-schedule` ``, read by `DoltHubClient().execute_sql(sql)` in `app/core/dolthub_client.py`. The token and repo settings stay in `DOLTHUB_API_TOKEN`, `DOLTHUB_OWNER`, `DOLTHUB_REPO`, and `DOLTHUB_BRANCH`.

Columns: `primary_key`, `sport`, `level`, `league`, `date`, `day`, `time`, `home_team`, `road_team`, `location`, `home_city`, `home_state`.

`gender` is not a column. `query_builder.py` derives it from `league` using `WOMEN_LEAGUE_CODES` in `app/projects/sports_schedule_admin/core/leagues.py` (`WNBA`, `NWSL`, `NCAAW`, `NCHW`, `NCSW`). `time` is Eastern. The UI label is "Time (ET)".

### Query logic

All of this lives in `app/projects/sports_schedules/` and is the behavior the tools must reuse.

- `core/query_builder.py` — `build_sql(params) -> (sql, error)`. Allowlisted dimensions and low-cardinality filters, escaped `LIKE` for free-text filters, limit clamped to 1..5000. Invalid dimension names and invalid low-cardinality values are ignored. That is safe for the checkbox UI and wrong for a model, so the new runner validates before calling `build_sql`.
- `core/distance_prepare.py` — `prepare_distance_filter(params)` and `apply_post_sql_distance(rows, params, dpr)`. Zip plus radius. Uses the Heroku Postgres tables `ss_zip_codes` and `ss_geocode_cache`, and Nominatim (1.1s sleep per uncached city, and a 10s timeout on the lookup itself). Needs a Flask app context. SQL `LIMIT` is applied before the mileage check, so a small limit can drop in-radius games. `flask sports_schedules agent-query` already over-fetches for this reason.
- `commands.py` — `flask sports_schedules warm-geocache` already fills `ss_geocode_cache` for every distinct city/state in the table and skips pairs that are cached. Run it before relying on radius queries. This plan does not add a second warm command.
- `core/sample_queries.py` — `config_to_params(config, anchor_date)` resolves `this_weekend`, `today`, `next_week`, `last_n`, `next_n`, and `future` from the anchor. `_compute_this_weekend(anchor_ymd)` returns the Friday–Sunday range.
- `core/constants.py` — `SPORTS`, `LEVELS`, `DAYS`, `GENDERS`, `US_STATE_CODES` (includes DC and Canadian provinces), `LEAGUE_CODES`, `LOW_CARDINALITY_OPTIONS`, `HIGH_CARDINALITY_FILTERS`, `FILTER_ONLY_FIELDS`, `DIMENSION_LABELS`. Display names come from `sports_schedule_admin/core/leagues.py`.
- `core/nl_prompt.py` — `STATE_NAME_TO_CODE` and the rules the in-app prompt already teaches Gemini (full team names, date modes, gender). The MCP tool descriptions carry the same rules. The prompt module itself stays as it is.
- `routes.py` — `GET /sports-schedules/api/query` is public and returns `{rows, sql, distance_filtered}`. It does not resolve relative date modes; a `date_mode` without concrete dates adds no date predicate. `POST /sports-schedules/api/nl-query` requires login, spends one credit, calls Gemini, and returns a config rather than rows.

### Date semantics

These match `query_builder.py` and `config_to_params`. The anchor is the Eastern calendar date the runner computes.

| `date_mode` | Window |
|---|---|
| `today` | Anchor only |
| `this_weekend` | Friday–Sunday containing the anchor on Fri/Sat/Sun; otherwise the upcoming Friday–Sunday |
| `next_week` | Anchor through anchor+6 days, inclusive |
| `next_n` | Anchor through anchor+n−1. Requires `date_n` > 0 |
| `last_n` | Anchor−n+1 through anchor. Requires `date_n` > 0 |
| `future` | Anchor+1 through 2099-12-31. Excludes today |
| `on_or_after` | `date_exact` through 2099-12-31 |
| `exact` | `date_exact` only |
| `range` | `date_start` through `date_end` |

The UI also has an empty date mode ("None") and `query_builder.py` still accepts `year` for old saved URLs. The tools expose neither. An omitted date mode in `build_sql` becomes `WHERE` with no date predicate and `ORDER BY date ASC`, which returns the oldest rows in the table.

`config_to_params` defaults its anchor to `datetime.utcnow()` when the caller does not pass one. On a Sunday evening in the US that UTC date is already Monday, so "this weekend" jumps to the next Friday. `build_sql` has the same UTC fallback for `future`, `next_week`, `next_n`, and `last_n` when `anchor_date` is empty. The runner always passes an Eastern anchor. Fixing Ask, the digest, and `agent-query` is a follow-up and is out of this work.

`date_n` in the UI is 1..365. The runner uses the same bound.

### Distance

`near` is `{zip, radius}`. The UI radii are 10, 25, 50, 100, and 250. `prepare_distance_filter` looks the zip up in `ss_zip_codes`, restricts `home_state` to nearby states, sets `include_international` so venues with a blank state stay eligible, runs SQL, then drops rows outside the radius. Helper columns `home_city` and `home_state` are added for that check and stripped afterward unless they were requested.

Unknown zip: `prepare_distance_filter` returns `Zip code '<zip>' not found.` The tool surfaces that string.

No candidate states, or a caller state list that does not overlap them: `early_empty`. Return zero rows, not an error.

`apply_post_sql_distance` skips the mileage check when `count` is true, so a count-plus-radius query is only a state prefilter. The tool rejects that combination.

A city name with a distance ("within 50 miles of Boston") is not a radius query. `home_city` is a contains match. The tool does not call Nominatim on free text.

`filter_rows_by_distance` geocodes every distinct city in the SQL result. A cold cache plus Heroku's 30-second router limit can cut the request off. `warm-geocache` is the normal fix. The runner also passes a cap into that function so a few new cities after a sync cannot hang the request. See Execution.

### either_team

Each value matches home or road. Multiple values are ANDed. `["Celtics", "Knicks"]` means those teams play each other. It does not mean "Celtics or Knicks." More than two values cannot match a real game. There is no "team A or team B" filter.

### MCP server

`app/projects/mcp/routes.py` is a hand-rolled JSON-RPC endpoint. The blueprint is registered at `/mcp` in `app/__init__.py`. `POST /mcp` handles `initialize` (protocol `2024-11-05`), `notifications/initialized`, `tools/list`, and `tools/call`. It is CSRF-exempt and has no auth. Tool definitions are the `MCP_TOOLS` list. `tools/call` dispatches `TOOL_HANDLERS[name](**args)` from `tools.py` and returns `json.dumps(result)` as text content. Today the only tools are `get_personal` and `get_work`.

A handler exception is returned with `isError: true` and `str(e)` as the text. A normal return value is `isError: false`, even if the dict contains an `"error"` key. Sports failures must use a dedicated exception (below) so the model sees a tool error and the message cannot include a DoltHub URL or token.

`GET /mcp/` renders `templates/mcp/index.html`. The module docstring says MCP clients should get 405; the code serves the landing page. Leave that behavior. Clients that already connect for the bio tools keep working. Update the docstring so it describes the landing page.

`serverInfo.name` is `mcp-bio`. Change it to `gmich` when the sports tools are registered.

---

## Approach

Add a schedule runner inside the sports-schedules package, then a thin MCP wrapper that calls it. The web route and the CLI keep their own copies of the pipeline for this work. A later cleanup can point them at the runner. Doing that now risks changing answers the UI and the weekly curator already return.

The runner owns Eastern time, strict validation, name normalization, the radius over-fetch, and the response shape. The MCP module owns tool schemas, descriptions, tool errors, rate limiting, and logging. The runner does not import Flask request objects or JSON-RPC types.

### Files

New:

- `app/projects/sports_schedules/core/run_query.py` — `run_schedule_query(arguments) -> ScheduleQueryResult`
- `app/projects/mcp/sports_tools.py` — `get_schedule_options()`, `query_schedules(**kwargs)`, `schedule_mcp_tools()`
- `tests/sports_schedules/test_run_query.py`
- `tests/mcp/test_sports_tools.py`

Edit:

- `app/projects/mcp/tools.py` — register the two handlers. Add `McpToolError`.
- `app/projects/mcp/routes.py` — append `schedule_mcp_tools()` to `MCP_TOOLS`. Catch `McpToolError` and return `isError: true` with that message only. Rename `serverInfo.name` to `gmich`. Fix the module docstring.
- `app/projects/mcp/templates/mcp/index.html` — list the new tools and a few example questions.
- `app/projects/sports_schedules/core/geocode.py` — optional `max_seconds` argument on `filter_rows_by_distance`. The default stays unlimited, so `/api/query` and `agent-query` keep their current behavior. Keep the per-entry cache commit in `citystate_to_coords`.
- `app/projects/sports_schedules/core/distance_prepare.py` — optional `max_seconds` on `apply_post_sql_distance`, forwarded to `filter_rows_by_distance`. Default `None` leaves the web UI and `agent-query` uncapped.

Leave alone:

- `app/projects/sports_schedules/routes.py`
- `app/projects/sports_schedules/commands.py` (`agent-query` is what the weekly curator runs; it still uses a UTC anchor, and repeated `--team` flags are ANDed as a matchup). `warm-geocache` stays as it is.
- `core/nl_prompt.py`, `core/query_builder.py`, `core/sample_queries.py`
- The bio tool behavior

---

## Runner: `run_schedule_query`

### Anchor

```text
today_et = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
```

Pass `today_et` into `config_to_params` as `anchor_date`. Ignore any `anchor_date` the caller sends.

### Arguments

Accept a dict shaped like the tool arguments below. Coerce a single string to a one-item list for every filter and for `dimensions`. Ignore unknown top-level keys. Reject unknown filter keys.

`dimensions` defaults to `["date", "time", "league", "home_team", "road_team"]`. Every name must be a key of `DIMENSION_LABELS` and must not be in `FILTER_ONLY_FIELDS` (`either_team`, `near`). An unknown or filter-only dimension is an error that lists the valid names. The runner does not add columns on its own. `count: true` may be combined with an empty dimension list, which returns a single `# Games` total.

`limit` defaults to 100. Clamp to 1..500. `build_sql` allows 5000; the runner clamps first. Include the applied limit in the result.

`sort_column` must be one of the selected dimensions, or `# Games` when `count` is true. `sort_dir` is `asc` or `desc`. An unknown sort column is an error. Omit both to keep the query builder's default (`date` ascending when `date` is selected).

`date_mode` is required and is one of the eight modes in the table above. Also require:

- `exact` and `on_or_after`: `date_exact` as `YYYY-MM-DD`
- `range`: `date_start` and `date_end` as `YYYY-MM-DD`, start on or before end
- `next_n` and `last_n`: `date_n` as an integer 1..365

### Filters

Low-cardinality keys: `sport`, `league`, `level`, `gender`, `day`, `home_state`. High-cardinality keys: `home_team`, `road_team`, `home_city`, `location`. Plus `either_team` and `near`.

Normalize before allowlist checks:

- `home_state`: accept a code in any case, or a full name from `STATE_NAME_TO_CODE` in `nl_prompt.py` (`Massachusetts` → `MA`, including DC and Canadian provinces).
- `league`: accept a code in any case, the display name in any case, or the display name with a trailing parenthetical removed (`English Premier League (EPL)` matches `English Premier League`).
- `sport`, `level`, `day`: case-insensitive match to the allowed value.
- `gender`: `M` / `W`, plus `men`, `mens`, `men's`, `male` → `M` and `women`, `womens`, `women's`, `ladies`, `female` → `W`.

If any value still does not match, return an error that quotes the bad value and the allowed codes. Do not drop it and continue.

If `gender` is only `W` and every selected league is outside `WOMEN_LEAGUE_CODES`, or `gender` is only `M` and every selected league is inside that set, return an error explaining the contradiction. Setting `gender` together with a mixed league list is fine. Setting `gender` on a single-gender league that agrees with it is fine. The tool description still tells the model not to set `gender` when the league already implies it.

`either_team`: 1 or 2 non-empty strings. Zero after trimming is "no filter." Three or more is an error that explains the matchup rule.

`near`: `zip` is a 5-digit string. `radius` snaps to the nearest of 10, 25, 50, 100, 250. Ties round toward the larger value. Report `radius_used`. Reject a missing zip, a non-numeric radius, and a radius ≤ 0.

Reject `count: true` together with `near`. The message says distance counts are not supported and the model should request rows instead.

### Execution

1. Validate and normalize into the config dict `config_to_params` already accepts (`dimensions` may be a list; `build_sql` accepts a list or a comma-separated string).
2. `params = config_to_params(config, anchor_date=today_et)`.
3. `dpr = prepare_distance_filter(params)`. On `dpr.error`, return that message. On `dpr.early_empty`, return zero rows with the resolved date range and applied filters.
4. Choose the SQL limit. With a distance filter active, set `params["limit"]` to `min(max(requested_limit * 2, 500), 2000)` before `build_sql`. That formula is only for `near`, because that is the only path that drops rows after `LIMIT`. Without `near`, set the SQL limit to `requested_limit + 1` so truncation is exact, and do not ask DoltHub for the larger radius page.
5. `sql, err = build_sql(params)`. A builder error becomes a tool error. This should be rare once validation has passed.
6. `result = DoltHubClient().execute_sql(sql)`. If `"error"` is in the result, log the server-side message and return a generic "Unable to load schedules. Try again." Do not include `result["error"]` in the tool payload.
7. `rows = apply_post_sql_distance(...)`, passing `max_seconds=15` when a distance filter is active. One cap is enough: a Nominatim lookup can take the full 10s timeout, so a count of lookups does not keep the request under Heroku's 30s router limit. `filter_rows_by_distance` raises once time spent in uncached lookups reaches 15 seconds, and it does not start another lookup after that. Cache hits do not count, including a stored miss (`lat`/`lon` null). The runner turns that into "This radius search needs geocoding that would time out. Try again shortly." Return no rows. A short list presented as a full answer is worse than an error. The wording is there so the model retries once, rather than telling the user it failed for good or calling the tool again in a loop. `citystate_to_coords` commits each lookup, success or miss, before the next one, so a capped call keeps the cities it finished and a retry continues. Leave that per-entry commit in place. Do not hold the cache writes until the request ends.
8. Keep the row order `build_sql` returns. Set `truncated`, then slice to `requested_limit`. Without `near`, `truncated` is true only when SQL returned the extra row. With `near`, `truncated` is true when SQL returned as many rows as the over-fetch cap (more in-radius games may exist past that page) or when the post-filter count is greater than `requested_limit`.

Record `date_range_used` from the dates `build_sql` would bind (`date_start` / `date_end` after `config_to_params` for relative modes, or the mode's computed window). For `future` and `on_or_after`, `end` is `2099-12-31`.

### Result

`ScheduleQueryResult` holds row dicts internally, so the distance step stays simple:

- `rows` as a list of dicts
- `row_count` (length after the slice)
- `truncated`
- `date_range_used`: `{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}`
- `applied`: dimensions, filters after normalization, `date_mode`, `limit`, and `radius_used` when a radius was snapped or used
- `sql` for tests and server logs

The MCP wrapper omits `sql`. It serializes `rows` as `columns` plus arrays, in dimension order, so a 100-row payload does not repeat every key on every row. `# Games` is a column when `count` is true. `date_range_used` and `applied` stay objects. Nothing depends on this shape yet, so this is the format to ship.

On failure the runner raises `ScheduleQueryError` with a short, model-actionable message. It does not raise with SQL, tokens, or request URLs. Unexpected exceptions are caught at the MCP boundary and replaced with the generic load-failure message; the real exception is logged.

Distance filtering needs `db.session`. The MCP request already runs inside an app context. Tests that call the runner with `near` need an app context too. Do not call the runner from a background thread without one.

---

## Tool: `get_schedule_options`

No arguments. Returns JSON built from the constants so it cannot drift:

- `today`: the Eastern date the runner will use as the anchor
- `leagues`: `{code, name, women}` from `LEAGUE_CODES`, `LEAGUE_DISPLAY_NAMES`, and `WOMEN_LEAGUE_CODES`
- `sports`, `levels`, `genders` (`M`, `W`), `days`, `states`
- `dimensions`: selectable columns, and `filter_only`: `either_team`, `near`
- `date_modes`: the eight modes, each with the one-line window from the table above
- `radius_options`: 10, 25, 50, 100, 250
- `notes`: the same rules as the `query_schedules` description (full names, matchup AND, which date mode to use for "upcoming", zip required for radius, Eastern times, gender). The notes say that some smaller college conferences are missing from the database, and that an empty result is not proof that no game exists. There is no per-league date-coverage query.

The description is one line: returns the allowed leagues, states, date modes, and today's Eastern date. Tell the model, in the other tool's description, that it does not have to call this first. It should call this when it needs `today` to fill `exact`, `on_or_after`, or `range` ("tomorrow", "next month", "March 15"). Clients cache `tools/list`, so today's date must not be written into a tool description.

## Tool: `query_schedules`

`schedule_mcp_tools()` builds the JSON Schema from `constants.py` and `leagues.py`. Enums:

- dimension names, excluding filter-only fields
- `sport`, `league`, `level`, `gender`, `day`, `home_state`
- `date_mode`
- `radius` on `near`
- `sort_dir`: `asc`, `desc`

Schema shape:

- `dimensions`: array of strings
- `filters`: object, all keys optional
  - `sport`, `league`, `level`, `gender`, `day`, `home_state`: arrays of the enum
  - `home_team`, `road_team`, `home_city`, `location`: arrays of strings
  - `either_team`: array of strings, min 1, max 2
  - `near`: `{zip: string, radius: enum}`
- `date_mode`: enum
- `date_exact`, `date_start`, `date_end`: string, `YYYY-MM-DD`
- `date_n`: integer
- `count`: boolean
- `limit`: integer
- `sort_column`: string
- `sort_dir`: enum

The schema is a hint. The runner still accepts full state names, league display names, and an off-list radius, and still rejects bad values. Models pass strings where the schema says arrays; the runner coerces those.

### Description

Put the rules in the `query_schedules` description. Other clients never see the in-app Gemini prompt.

- Prefer a relative `date_mode`. The server resolves it in US Eastern time. Do not send `anchor_date`.
- For `tomorrow`, `next month`, or a named day, call `get_schedule_options` and read `today`, then send `exact`, `on_or_after`, or `range`. There is no month mode and no year mode.
- `next_week` and `next_n` include today. `future` starts tomorrow. For "upcoming" or "when do the X play", use `next_n` (for example 30, or 365 for a remaining season inside a year). That includes a game later today and does not require looking up today's date. `date_n` cannot exceed 365, so a longer horizon is `on_or_after` with today's Eastern date from `get_schedule_options`. Do not use `future` for those questions.
- `this_weekend` is Friday–Sunday: the current weekend on Friday, Saturday, and Sunday, otherwise the upcoming one.
- A date mode is required.
- Team, city, and location filters are case-insensitive contains matches and need full names. `OKC` fails; use `Oklahoma City` or `Thunder`. `NYC` → `New York`. `KC` → `Kansas City`. `DC` → `Washington`. `LA` → `Los Angeles`. `SF` → `San Francisco`. `PHX` → `Phoenix`.
- One `either_team` value means that team is home or away. Two values mean they play each other. There is no "Celtics or Knicks" filter; that is two queries.
- "In New Jersey" is `home_state: ["NJ"]`. That is the home team's state. It does not include New Jersey teams playing away.
- `near` needs a 5-digit US zip and a radius of 10, 25, 50, 100, or 250. A city plus a mileage is a `home_city` contains match, or a request back to the user for a zip. Do not invent a zip.
- `gender` is `M` or `W` and is derived from the league. Set it when the user says men's or women's. Do not set it only because the league is already single-gender, such as `WNBA`. Women's college basketball is `gender: ["W"]`, `sport: ["basketball"]`, `level: ["college"]`.
- Times in the rows are Eastern.
- An empty `rows` array means this database had no match. Some smaller college conferences are missing entirely. Do not tell the user that no such game exists.
- Default columns are `date`, `time`, `league`, `home_team`, `road_team`. For a radius query, also request `home_city`, `home_state`, and `location`.
- `count: true` groups by the dimensions and adds `# Games`. It cannot be combined with `near`.
- `limit` defaults to 100 and is capped at 500. When `truncated` is true, say that more matching games were not shown.

Include four examples in the description:

- "What games are in NJ this weekend?" → `filters.home_state: ["NJ"]`, `date_mode: "this_weekend"`, dimensions `date`, `time`, `league`, `home_team`, `road_team`
- "MLB games near 10001 in the next 30 days" → `filters.league: ["MLB"]`, `filters.near: {zip: "10001", radius: 50}`, `date_mode: "next_n"`, `date_n: 30`, plus city, state, and location in the dimensions
- "When do the Celtics play the Knicks?" → `filters.either_team: ["Celtics", "Knicks"]`, `date_mode: "next_n"`, `date_n: 365`
- "Women's college basketball within 50 miles of 07928 in the next two weeks" → `gender: ["W"]`, `sport: ["basketball"]`, `level: ["college"]`, `near: {zip: "07928", radius: 50}`, `date_mode: "next_n"`, `date_n: 14`

### Tool payload

```json
{
  "columns": ["date", "time", "league", "home_team", "road_team"],
  "rows": [["2026-11-07", "7:00 PM", "NHL", "Devils", "Rangers"]],
  "row_count": 1,
  "truncated": false,
  "date_range_used": {"start": "2026-11-06", "end": "2026-11-08"},
  "applied": {
    "dimensions": ["date", "time", "league", "home_team", "road_team"],
    "filters": {"home_state": ["NJ"]},
    "date_mode": "this_weekend",
    "limit": 100
  }
}
```

`radius_used` is present on `applied` only when `near` was used. `sql` is not in this payload.

`query_schedules` catches `ScheduleQueryError` and re-raises `McpToolError` with the same message. Any other exception is logged and becomes `McpToolError("Unable to load schedules. Try again.")`.

`routes.py` catches `McpToolError` inside `tools/call` and returns `isError: true` with that message as the text content. It must not attach the raw exception string for this case.

---

## Rate limit and logging

Both live in the MCP wrapper, not in the runner.

In memory, per worker, 30 `query_schedules` calls per client IP per rolling minute. Over the limit, raise `McpToolError` with "Rate limit exceeded. Try again in a minute." and do not call DoltHub. `get_schedule_options` is not limited.

There is no `ProxyFix` in this app. On Heroku `request.remote_addr` is the router, so a limiter built on it is one bucket shared by every caller. Read the client from `X-Forwarded-For` and use the last entry, which is the address the Heroku router appended. Earlier entries are client-supplied. When the header is absent (local dev), fall back to `request.remote_addr`. A single global cap is not the intent: one caller would lock everyone else out.

That last-entry rule holds only while Heroku is the last proxy. A CDN in front would make the last entry the CDN's address and collapse every caller into one bucket again. Checked 2026-11-08: `https://gregmichnikov.com/mcp/` responds with `server: Heroku` and `via: heroku-router`, and no CDN headers. If a proxy is added later, revisit which hop to trust.

The counter is per Gunicorn worker, and `Procfile` is `gunicorn run:app` with `WEB_CONCURRENCY` choosing the worker count. The effective ceiling is 30 per minute multiplied by workers and dynos.

Prune the dict. A public endpoint keyed by IP will otherwise grow without bound. Follow `app/core/auth.py`: on a timer, drop timestamps outside the one-minute window and delete keys that are left empty.

After a successful query, write a `LogEntry` with `actor_id=None`, `project="sports_schedules"`, `category="MCP Query"`, and a description that includes the row count and whether a distance filter was used. Do not put the caller's free-text team strings in a way that fails the request; a short description is enough. If the commit fails, log it and still return the rows.

Capture a PostHog event `sports_mcp_query` with `distinct_id="mcp"`, `row_count`, and `distance_filtered`, matching the style of `sports_query_run` in `routes.py`. Swallow PostHog failures.

---

## Tests

`tests/sports_schedules/test_run_query.py`, with `DoltHubClient.execute_sql` mocked:

- New Jersey plus `this_weekend` produces SQL containing `home_state` `NJ` and the Friday–Sunday `BETWEEN` for a frozen Eastern anchor.
- Freeze time at Monday 00:30 UTC, which is still Sunday evening in New York. `this_weekend` is that Sunday's weekend, not the following Friday.
- `Massachusetts` normalizes to `MA`. An unknown league returns an error and does not call DoltHub.
- `either_team` with three names returns an error. Two names produce two ANDed contains checks.
- `gender: ["W"]` together with `league: ["NBA"]` returns an error.
- Omitted `date_mode` returns an error and does not call DoltHub.
- `limit` above 500 is clamped. Without `near`, SQL is asked for `requested_limit + 1`. `truncated` is true when that extra row comes back, and false when the count equals `requested_limit` exactly.
- A `near` query sets the state prefilter, asks SQL for the over-fetch cap rather than `requested_limit + 1`, applies the post-SQL distance step, and slices back to the requested limit. Mock `prepare_distance_filter` / `apply_post_sql_distance` if the zip tables are not available. Also assert that a mocked "zip not found" message is returned unchanged.
- Spending 15 seconds in uncached Nominatim lookups during a radius query raises the timeout error and returns no rows. Lookups committed before the cap stay in `ss_geocode_cache`.
- `count` plus `near` returns an error.
- A DoltHub result of `{"error": "https://secret.example/token"}` becomes the generic load message. The secret string is absent from the exception message.

`tests/mcp/test_sports_tools.py`, using the Flask test client against the MCP blueprint:

- `tools/list` includes `get_personal`, `get_work`, `get_schedule_options`, and `query_schedules`, and each sports tool's `inputSchema` is an object.
- `get_schedule_options` returns leagues, states, and `today`, and does not call DoltHub.
- A `query_schedules` call with a bad league returns `isError: true` and a message that names the bad value.
- A successful call, with DoltHub mocked, returns `isError: false` and a payload with `columns`, `rows` as arrays, `date_range_used`, and `applied`, and with no `sql` key.
- The rate-limit bucket key is the last `X-Forwarded-For` entry. A spoofed first entry is ignored. With no header, the key is `request.remote_addr`.
- After the prune interval, timestamps outside the one-minute window are gone and an IP with no remaining timestamps is removed from the dict.

Existing `tests/sports_schedules/test_routes.py` still passes.

---

## Phases

Stop at the end of each phase and confirm the checks below before starting the next one.

### Phase 1 — Runner

- [ ] Add `app/projects/sports_schedules/core/run_query.py` with validation, the Eastern anchor, `limit + 1` truncation, radius over-fetch, the geocode cap, and `ScheduleQueryResult` / `ScheduleQueryError`.
- [ ] Add optional `max_seconds` on `filter_rows_by_distance` and thread it through `apply_post_sql_distance`. The default stays unlimited.
- [ ] Add `tests/sports_schedules/test_run_query.py` and run it.
- [ ] Run `tests/sports_schedules/test_routes.py` and confirm it still passes.

Nothing user-facing changes in this phase. The check is the test run: the Sunday-evening anchor, the rejected bad league, exact truncation without a radius, the radius over-fetch, and the geocode cap.

### Phase 2 — MCP tools

- [ ] Add `McpToolError` and catch it in `routes.py` without putting other exception text on that path.
- [ ] Add `sports_tools.py`, register both handlers, and append `schedule_mcp_tools()` to `MCP_TOOLS`.
- [ ] Set `serverInfo.name` to `gmich`. Fix the module docstring so GET is described as the landing page.
- [ ] Add the per-IP limit using the last `X-Forwarded-For` entry, prune expired keys, and write the `LogEntry` and the PostHog capture.
- [ ] Update the landing page tool list and add example questions.
- [ ] Add `tests/mcp/test_sports_tools.py` and run it, plus the Phase 1 tests.

Local protocol check, with the Flask app running. This is separate from the Phase 3 client gate. `POST /mcp` with `initialize`, then `notifications/initialized`, then `tools/list`, then `tools/call` for `get_schedule_options`, a New Jersey `this_weekend` query, and a bad league. The bad league is `isError: true`. The landing page lists the four tools. Bio `get_personal` still returns data. `curl` is enough. MCP Inspector is fine too.

### Phase 3 — Live clients

This is a required gate. The transport is unchanged, so a connector that cannot complete a query means this work is not done. Deploy first, and run `flask sports_schedules warm-geocache` so radius queries hit the cache.

Add the connector in claude.ai and ask:

- "What games are in NJ this weekend?"
- "Women's college basketball within 50 miles of 07928 in the next two weeks"
- "How many games per league are there in Massachusetts next month?"
- "When do the Celtics play the Knicks?"

Run one of those from a second client, Cursor or ChatGPT. Compare one radius result to the same zip and radius in the web UI. A failure in only one client is a transport bug to fix before calling this done.

---

## Follow-ups (not this work)

- Pass an Eastern anchor from `api_nl_query`, the weekly digest, and `agent-query`. They still use `datetime.utcnow()`.
- Point `GET /sports-schedules/api/query` and `agent-query` at `run_schedule_query` once the MCP path has been live and the results match.
- Same-day kickoff order. `build_sql` orders `time` lexicographically, so `12:00 PM` sorts after `1:00 PM`. The page fixes that in the browser. Leave the SQL order in this work.
- If a real MCP client fails the POST-only handshake, then look at GET content negotiation or the official SDK. Do not do that preemptively. The bio tools already use this transport.

---

## Acceptance checklist

- [ ] `tools/list` shows `get_personal`, `get_work`, `get_schedule_options`, and `query_schedules`
- [ ] "NJ this weekend" uses the current Eastern Friday–Sunday range, including on a Sunday evening
- [ ] A radius query over-fetches, then matches the web UI for the same zip and radius within the returned page
- [ ] Invalid league, state, or a missing date mode is a tool error and does not hit DoltHub
- [ ] The tool payload uses `columns` and array `rows`, includes `truncated`, `date_range_used`, and `applied`, and omits SQL
- [ ] A non-radius result sets `truncated` only when more than `limit` rows existed
- [ ] `get_schedule_options` returns leagues, states, and today's Eastern date without calling DoltHub
- [ ] A DoltHub failure returns a generic message with no token or URL
- [ ] A radius query that hits the geocode cap returns an error and no rows, and cities looked up before the cap stay cached
- [ ] The rate limit keys off the last `X-Forwarded-For` entry and drops expired IP entries
- [ ] Phase 1 and Phase 2 tests pass, and `tests/sports_schedules/test_routes.py` still passes
- [ ] A local `initialize`, `tools/list`, and `tools/call` round trip succeeds before deploy
- [ ] The landing page lists the new tools
- [ ] claude.ai and one other client can ask a question and get rows
