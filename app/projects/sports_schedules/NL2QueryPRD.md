# Sports Schedules — Natural Language to Query (NL2Query) PRD

## Overview

Add a **natural language query** feature for Sports Schedules. Logged-in users can type questions in plain English (e.g., "When do the Celtics play this week?" or "NBA games in Boston next weekend"), and an LLM translates them—when possible—into the JSON query config format used by the existing query builder. The result loads into the form and runs the query, or the user is shown an explanation if translation is not possible.

---

## Goals

1. Lower the barrier for non-technical users to explore schedule data.
2. Complement the existing visual query builder (users can refine after NL translation).
3. Leverage LLM capability to interpret varied phrasing (teams, locations, date expressions).
4. Provide clear feedback when a question cannot be converted to a valid query.

---

## Out of Scope (Explicitly)

- **Anonymous users:** Feature is gated by login.
- **Natural language over saved-query results:** We translate to config, not to SQL or free-form answers.
- **Follow-up / conversational context:** Single-turn only; no chat memory.
- **Export / summarization in NL:** Only config translation. Results display as the existing table.

---

## Core Requirements

### 1. Access Control

- **Logged-in users only.** Show "Ask a Question" only when `current_user.is_authenticated`.
- **Insufficient credits:** If `current_user.credits < 1`, disable or hide the NL option, or show it with a message ("Insufficient credits") and prevent submit. Match the pattern used by chatbot/ask_many_llms.
- Anonymous users see the existing UI without NL entry; no redirect or upsell in V1.

### 2. Input / Output Flow

1. User types a natural language question in a text input (max 500 characters).
2. User submits (e.g., button click or Enter). **Do not submit** if the question is empty or whitespace-only.
3. Backend sends the question to an LLM with a structured prompt that includes:
   - Schema description (dimensions, filters, date modes).
   - Example NL → JSON pairs (few-shot).
   - Instructions to return valid config JSON or an explanation of why it's not possible.
4. Backend parses LLM response:
   - **Success:** Valid config → load into form, update URL, run query (same as loading a saved query).
   - **Failure:** Show user-friendly message (e.g., "I couldn't turn that into a schedule query. Try something like 'Celtics games this week' or 'NBA in Boston next weekend.'").

### 3. LLM Responsibilities

- **Translate** natural language into the project's query config format (same structure as `_parse_query_params` / `build_sql`).
- **Consider** whether the question can be answered as a schedule data query. If off-topic, subjective, or not representable, return `{ "error": "human-readable reason" }` instead of guessing.
- **Refuse** when the question is ambiguous, outside the schema, or not representable (e.g., "What's the best game to watch?" or "Tell me a joke").
- **Return structured output:** Exactly one of:
  - `{ "config": {...} }` — when the question is translatable. The `config` object is the full query config (see below). No `error` key.
  - `{ "error": "human-readable reason" }` — when the question cannot be answered as a schedule query (off-topic, subjective, ambiguous, or not representable). No `config` key.
- **Mutually exclusive:** Never return both `config` and `error` in the same response.

### 4. Query Config Format (Target)

Same as saved queries and URL params:

```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {
    "league": ["NBA"],
    "home_city": ["Boston"],
    "either_team": ["Celtics"]
  },
  "date_mode": "next_week",
  "date_n": null,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**Key constraints for the LLM:**

- `dimensions`: Comma-separated list of valid column names (exclude `either_team`—filter-only).
- **Low-cardinality filters:** `sport`, `league`, `level`, `day`, `home_state` — values must come from allowed lists (e.g., leagues: NBA, NHL, MLB, NCAAM, etc.; states: MA, CA, NJ, etc.).
- **High-cardinality filters:** `home_team`, `road_team`, `location`, `home_city` — free-form "contains" search strings.
- **`either_team`:** Array of team name substrings; matches home OR road.
- **Date modes:** `exact`, `today`, `on_or_after`, `this_weekend`, `range`, `future`, `next_week`, `last_n`, `next_n`.
- **Date params:** `date_exact`, `date_start`, `date_end`, `date_n`, `anchor_date` per mode.
- `count`: boolean; when true, can omit dimensions for total count.
- `limit`: 1–5000 (default 500).

### 5. Date Filter Specification (LLM Must Follow)

All dates use **YYYY-MM-DD** format. The server passes **today's date** (e.g., `2026-02-20`) in the prompt. The LLM uses it to resolve relative expressions ("tomorrow", "this weekend", etc.).

| `date_mode` | Description | LLM must provide | LLM may omit | Server fills |
|-------------|-------------|-------------------|--------------|--------------|
| `exact` | Single date | `date_exact` (YYYY-MM-DD) | — | — |
| `today` | Games on today's date | — | `date_exact` | Server uses anchor as `date_exact` |
| `on_or_after` | From a date onward | `date_exact` (YYYY-MM-DD) | — | — |
| `this_weekend` | Fri–Sun of current/next weekend | — | `date_start`, `date_end` | Server computes from anchor |
| `range` | Start and end date (inclusive) | `date_start`, `date_end` (YYYY-MM-DD) | — | — |
| `future` | All games from tomorrow onward | — | `anchor_date` | Server uses today as anchor |
| `next_week` | Next 7 days from anchor (anchor through anchor+6) | — | `anchor_date` | Server uses today as anchor |
| `last_n` | Past N days ending at anchor | `date_n` (integer > 0) | `anchor_date` | Server uses today as anchor |
| `next_n` | Next N days from anchor | `date_n` (integer > 0) | `anchor_date` | Server uses today as anchor |
| `year` | All games in a calendar year | `date_year` (integer, e.g., 2026) | — | — |

**Rules:**
- For `exact`, `on_or_after`, `range`: LLM must output concrete YYYY-MM-DD dates. Use today's date (from prompt) to resolve "tomorrow", "March 15" (assume current year if not stated), etc.
- For `this_weekend`, `future`, `next_week`, `last_n`, `next_n`: LLM may omit `anchor_date`; server fills with today.
- For `this_weekend`: LLM may omit `date_start` and `date_end`; server computes Friday–Sunday from anchor.
- For `last_n` and `next_n`: `date_n` must be a positive integer (e.g., 7, 14, 30).

---

## Sample Queries for Few-Shot Prompt

These examples showcase the full range of capabilities. They should be included in the LLM prompt to teach the translation format.

### Team Filters

| Natural Language | Key Config Elements |
|------------------|---------------------|
| "Celtics games this week" | `either_team: ["Celtics"]`, `date_mode: "next_week"` |
| "When do the Red Sox play?" | `either_team: ["Red Sox"]`, `date_mode: "future"` or `next_week` |
| "Lakers vs Warriors" | `either_team: ["Lakers", "Warriors"]` (matchup) |
| "Yankees home games next month" | `home_team: ["Yankees"]`, `date_mode: "next_n"`, `date_n: 30` |
| "Bruins away games" | `road_team: ["Bruins"]`, `date_mode: "future"` |

### Location Filters

| Natural Language | Key Config Elements |
|------------------|---------------------|
| "Games in Boston this weekend" | `home_city: ["Boston"]`, `date_mode: "this_weekend"` |
| "NBA games in New Jersey" | `league: ["NBA"]`, `home_state: ["NJ"]` |
| "Pro hockey in Michigan next week" | `league: ["NHL"]`, `home_state: ["MI"]`, `date_mode: "next_week"` |
| "College basketball in Massachusetts" | `level: ["college"]`, `sport: ["basketball"]`, `home_state: ["MA"]` |
| "Games at Madison Square Garden" | `location: ["Madison Square Garden"]` |

### League / Sport / Level

| Natural Language | Key Config Elements |
|------------------|---------------------|
| "NBA next 7 days" | `league: ["NBA"]`, `date_mode: "next_week"` |
| "All MLB games tomorrow" | `league: ["MLB"]`, `date_mode: "exact"`, `date_exact: <tomorrow>` |
| "College football this weekend" | `level: ["college"]`, `sport: ["football"]`, `date_mode: "this_weekend"` |
| "NHL and NBA in the next 2 weeks" | `league: ["NHL", "NBA"]`, `date_mode: "next_n"`, `date_n: 14` |
| "How many pro basketball games are there next month?" | `level: ["pro"]`, `sport: ["basketball"]`, `date_mode: "next_n"`, `date_n: 30`, `count: true`, `dimensions: ""` |

### Date Expressions

| Natural Language | Key Config Elements |
|------------------|---------------------|
| "Games on March 15" | `date_mode: "exact"`, `date_exact: "2026-03-15"` (or param for year) |
| "Games from Feb 20 to Feb 28" | `date_mode: "range"`, `date_start`, `date_end` |
| "Games this weekend" | `date_mode: "this_weekend"` |
| "Games in the next 14 days" | `date_mode: "next_n"`, `date_n: 14` |
| "All future games" | `date_mode: "future"` |
| "Last week's NBA games" | `league: ["NBA"]`, `date_mode: "last_n"`, `date_n: 7` |

### Aggregations

| Natural Language | Key Config Elements |
|------------------|---------------------|
| "How many Celtics games are there?" | `either_team: ["Celtics"]`, `count: true`, `dimensions: ""` |
| "Count of NBA games by date" | `league: ["NBA"]`, `count: true`, `dimensions: "date"` |
| "Games per league in Massachusetts next month" | `home_state: ["MA"]`, `count: true`, `dimensions: "league"`, `date_mode: "next_n"`, `date_n: 30` |

### Combined Filters

| Natural Language | Key Config Elements |
|------------------|---------------------|
| "Celtics home games in Boston this weekend" | `home_team: ["Celtics"]`, `home_city: ["Boston"]`, `date_mode: "this_weekend"` |
| "College basketball in New Jersey next week" | `level: ["college"]`, `sport: ["basketball"]`, `home_state: ["NJ"]`, `date_mode: "next_week"` |
| "Saturday NBA games in California" | `day: ["Saturday"]`, `league: ["NBA"]`, `home_state: ["CA"]` |

### Edge Cases / Refusals (Include in Prompt)

| Natural Language | Expected Behavior |
|------------------|-------------------|
| "What's the best game to watch?" | Refuse — subjective, not in schema |
| "When is the Super Bowl?" | May translate if data exists; otherwise refuse if event not in combined-schedule |
| "Tell me a joke" | Refuse — off-topic |
| "All games" | Could translate: no filters, `date_mode: "future"` or `next_n` with large N |
| "Michigan vs Ohio State" | Translate: `either_team: ["Michigan", "Ohio State"]` |

### Full JSON Examples (Include in Few-Shot Prompt)

Assume **today is 2026-02-20** when interpreting relative dates. Examples 1–9 cover date modes; 10–13 add team matchup, multi-filter, multi-city, and broad location queries (with league/sport as dimensions); 14–15 are count queries.

**1. "Celtics games this week"** — `next_week`, `either_team`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"either_team": ["Celtics"]},
  "date_mode": "next_week",
  "date_n": null,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**2. "Games in Boston this weekend"** — `this_weekend`, `home_city`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"home_city": ["Boston"]},
  "date_mode": "this_weekend",
  "date_n": null,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**3. "Games on March 15"** — `exact`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {},
  "date_mode": "exact",
  "date_n": null,
  "date_exact": "2026-03-15",
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**4. "Champions League games from Feb 20 to Feb 28"** — `range`, `league`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"league": ["CL"]},
  "date_mode": "range",
  "date_n": null,
  "date_exact": null,
  "date_start": "2026-02-20",
  "date_end": "2026-02-28",
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**5. "When do the Red Sox play?"** — `future`, `either_team`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"either_team": ["Red Sox"]},
  "date_mode": "future",
  "date_n": null,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**6. "Last week's NBA games"** — `last_n`, `league`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"league": ["NBA"]},
  "date_mode": "last_n",
  "date_n": 7,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**7. "Yankees home games next month"** — `next_n`, `home_team`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"home_team": ["Yankees"]},
  "date_mode": "next_n",
  "date_n": 30,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**8. "MLB games today"** — `today`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"league": ["MLB"]},
  "date_mode": "today",
  "date_n": null,
  "date_exact": "2026-02-20",
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**9. "College hockey games from March 1 onward"** — `on_or_after`, `level`, `sport`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"level": ["college"], "sport": ["hockey"]},
  "date_mode": "on_or_after",
  "date_n": null,
  "date_exact": "2026-03-01",
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**10. "When do the Red Sox play the Yankees?"** — `either_team` matchup (both teams)
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"either_team": ["Red Sox", "Yankees"]},
  "date_mode": "future",
  "date_n": null,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**11. "Show me college basketball games in New Jersey in the next week"** — `next_week`, `level`, `sport`, `home_state`
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"level": ["college"], "sport": ["basketball"], "home_state": ["NJ"]},
  "date_mode": "next_week",
  "date_n": null,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**12. "When do the Celtics play in Philly or DC?"** — `either_team`, `home_city` (multiple cities)
```json
{
  "dimensions": "date,time,home_team,road_team",
  "filters": {"either_team": ["Celtics"], "home_city": ["Philadelphia", "Washington"]},
  "date_mode": "future",
  "date_n": null,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**13. "What games are in New Jersey this weekend?"** — `this_weekend`, `home_state`; include `league` and `sport` as dimensions so user sees what type of games
```json
{
  "dimensions": "date,time,league,sport,home_team,road_team",
  "filters": {"home_state": ["NJ"]},
  "date_mode": "this_weekend",
  "date_n": null,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": false,
  "limit": 500,
  "sort_column": "",
  "sort_dir": "asc"
}
```

**14. "Count of NBA games by date last week"** — `count`, `dimensions: "date"`, `last_n`, `league`
```json
{
  "dimensions": "date",
  "filters": {"league": ["NBA"]},
  "date_mode": "last_n",
  "date_n": 7,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": true,
  "limit": 500,
  "sort_column": "# Games",
  "sort_dir": "desc"
}
```

**15. "Games per league in Massachusetts next month"** — `count`, `next_n`, `home_state`, `dimensions: "league"`
```json
{
  "dimensions": "league",
  "filters": {"home_state": ["MA"]},
  "date_mode": "next_n",
  "date_n": 30,
  "date_exact": null,
  "date_start": null,
  "date_end": null,
  "date_year": null,
  "anchor_date": null,
  "count": true,
  "limit": 500,
  "sort_column": "# Games",
  "sort_dir": "desc"
}
```

---

## Decisions (Finalized)

### 1. LLM Provider & Model

- **Use existing LLM infrastructure** in the web app (e.g., `ask_many_llms` LLMService or equivalent).
- **Model:** `gemini-3-flash-preview`. Reuse the same `genai.Client` + `GOOGLE_API_KEY` pattern used elsewhere.

### 2. Prompt Design

- **Few-shot with examples:** Include sample NL → JSON pairs in the prompt to teach the translation format.
- **Prompt size:** Keep the prompt reasonably sized; avoid making it enormous. Trim if token limits become an issue.

### 3. Anchor Date Handling

- **Server provides today's date.** The current date (YYYY-MM-DD) is passed from the server into the prompt. The LLM cannot reliably compute dates; it uses the provided anchor.
- **Server fills `anchor_date`** when absent in the LLM response (same as saved-query behavior).

### 4. Response Format

- **LLM outputs the same JSON format** used by the project. The response is immediately loadable into the UI query form and runnable. Either `{ "config": {...} }` or `{ "error": "..." }`.

### 5. Ambiguity Handling

- **LLM does its best.** We use "contains" searches anyway; multiple matches are acceptable. No clarification flow in V1.

### 6. Rate Limiting / Cost Control

- **Use existing credits system.** Each NL query costs **1 credit** on the user's account (same as chatbot, ask_many_llms, etc.). No separate rate limiting; credits handle it.

### 7. UI Placement

- **"Ask a Question"** option above the filter bar. Clicking opens a **modal** where the user types their question and submits.

### 8. Error Messages / Refusals

- **LLM must consider** whether the question can be answered as a schedule query. If off-topic, too hard, or not representable, return a structured `{ "error": "..." }` message.
- **Hold off** on detailed error-message UX for now; LLM provides the refusal text.

### 9. Low-Cardinality Allowed Values

- **Include full lists in the prompt** so the LLM uses correct values. Sources: `constants.SPORTS`, `constants.LEVELS`, `constants.DAYS`, `constants.US_STATE_CODES`, `constants.LEAGUE_CODES` + `LEAGUE_DISPLAY_NAMES`. Server still validates and strips invalid values.

### 10. Prompt Schema (Low-Cardinality Values to Include)

The prompt must include these allowed values so the LLM outputs valid config:

- **sport:** basketball, hockey, football, baseball, soccer
- **level:** pro, college, minor
- **day:** Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
- **home_state:** Use 2-letter codes only. When the user says "New Jersey", "California", "Massachusetts", etc., the LLM must map to NJ, CA, MA, etc. Include a state-name→code mapping in the prompt (or the full list of codes) so the LLM outputs valid values. Canadian provinces: AB, BC, ON, QC, etc.
- **league:** All codes from `LEAGUE_CODES` with display names for mapping (e.g., NBA, NHL, MLB, NCAAM, NCAAW, EPL, AAA, AA, …). LLM should use the **code** (e.g., NBA) not the display name.

---

## Clarifications (Resolved)

1. **Exact date + year:** LLM decides the year given the **current full date** passed from the server (e.g., "March 15" → 2026-03-15 when today is 2026-02-20).

2. **Today's date in prompt:** Yes. Server passes today's date (YYYY-MM-DD) into the prompt so the LLM can resolve "tomorrow", "this weekend", etc.

3. **League/sport representations:** LLM must know how we represent leagues and sports (e.g., NBA, NHL, NCAAM, NCAAW, basketball, hockey). Include league codes and sport values in the prompt.

4. **Either_team vs home_team/road_team:** Yes, include examples in the few-shot prompt so the LLM distinguishes ("Celtics games" → `either_team`, "Celtics home games" → `home_team`).

5. **Default dimensions:** No hard defaults. LLM uses judgment. For most queries, `date`, `time`, `road_team`, `home_team` make sense, but not always.

6. **Default date when none stated:** Use **`future`** (all games from tomorrow onward).

7. **API key:** Already in `.env` (same `GOOGLE_API_KEY` used for other Gemini calls).

8. **Logging:** Use existing admin-style logging throughout the site (e.g., `LogEntry` or equivalent) for NL input and outcome (config or error). **Include input and output tokens** when the LLM returns them (Gemini provides these in `usage_metadata`). Log format should capture: question (or truncated), outcome (config success / error type), and `input_tokens`, `output_tokens` when available.

9. **Testing:** Don't worry for now.

---

## Technical Considerations

- **Backend endpoint:** New route, e.g. `POST /sports-schedules/api/nl-query` with body `{ "question": "..." }`.
- **Auth:** `@login_required`; return 401 if not authenticated.
- **CSRF:** Include `X-CSRFToken` header in the POST request (same pattern as other API calls in the app).
- **Input validation:** Do not send empty questions. Client must disable submit when question is empty or whitespace-only. Max question length: **500 characters**. Server should validate and return 400 if empty or over limit.
- **Credits:** Check `current_user.credits >= 1` before calling LLM. **Deduct only on success:** when the LLM returns valid config, `build_sql(config_to_params(config))` succeeds, and the config is returned to the client. Do **not** deduct on: LLM refusal (`error`), malformed JSON, `build_sql` failure, or API/network errors. Use existing `LogEntry` pattern for credit use.
- **Logging:** Each NL query should be logged with `LogEntry` (project: sports_schedules, category: NL Query or Credit Usage). Include the question (truncate if very long), outcome (config success / refusal / error), and **input_tokens** and **output_tokens** when the LLM returns them (e.g., from Gemini `usage_metadata`). Store tokens in the log description string, e.g. `"NL query: 'Celtics games' → config. input_tokens=1200, output_tokens=85"` or `"NL query: 'joke' → error (refused). input_tokens=800, output_tokens=42"`.
- **LLM reuse:** Use existing Gemini client (e.g., from `ask_many_llms` LLMService or equivalent). Model: `gemini-3-flash-preview`. API key: `GOOGLE_API_KEY` in `.env`.
- **Today's date:** Pass today's date (YYYY-MM-DD) in the request body or prompt so the LLM can resolve relative dates.
- **Validation:** Run `build_sql(config_to_params(config))` before returning; if it fails, treat as LLM error and return fallback message.
- **Config → form:** On success, the returned config must **populate the UI** the same way as when a user clicks a sample query: call `ssLoadQueryAndRun(config)` (or equivalent), which loads the config into the form, updates the URL, and runs the query. Same flow as saved/sample queries.
- **Malformed JSON:** If the LLM returns invalid or unparseable JSON, do not retry. Show the raw response in the UI or at least log it to the console so the developer can debug and fix the prompt. **JSON extraction:** The LLM may wrap JSON in markdown (e.g., ` ```json ... ``` `). The server must extract the JSON object before parsing—e.g., look for the first `{` and matching `}`, or strip markdown fences.
- **Config merge:** Use `config_to_params(config, anchor_date)` (from `sample_queries`) to merge LLM config with defaults. This fills `anchor_date`, computes `date_start`/`date_end` for `this_weekend`, etc., before passing to `build_sql`.
- **UI:** "Ask a Question" link/button above filter bar; opens modal with text input and submit button. **Loading state:** Show spinner or disabled state while awaiting the API response. **Modal on success:** Close modal and load config into form (same as sample query). **Modal on error:** Keep modal open, show error message in the modal.
- **Credits in modal:** Show user's credit count in the modal (e.g., "1 credit per question • You have X credits") so they know before submitting.
- **API response schema:**
  - **Success (200):** `{ "config": {...}, "remaining_credits": N }`
  - **LLM refusal (200):** `{ "error": "human-readable message" }` — LLM decided the question cannot be answered
  - **Malformed JSON (200):** `{ "error": "Could not parse response", "raw": "..." }` — include raw for debugging
  - **build_sql failure (400):** `{ "error": "Could not run that query" }`
  - **Insufficient credits (400):** `{ "error": "Insufficient credits" }`
  - **Validation (400):** `{ "error": "Question is required" }` or `{ "error": "Question must be 500 characters or less" }`
  - **Unauthenticated (401):** `{ "error": "Login required" }`
- **CSS prefix:** All new classes for the modal and NL UI must use the `ss-` prefix to avoid collisions with other projects.
- **Prompt size:** Keep the few-shot prompt reasonably sized; avoid making it enormous. If token limits become an issue, trim examples or schema details.

---

## Success Criteria

- Logged-in users can type a natural language question and, when translatable, see the query run and results.
- When not translatable, user sees a clear message and example phrasings.
- Translated configs produce valid SQL and return results (or empty set) without errors.
- Anonymous users do not see or access the NL input.

---

## Next Steps

1. **Create implementation plan** (NL2QueryPLAN.md).
2. **Implement** in phases.
