# Sports Schedules — NL2Query Implementation Plan

This plan implements the Natural Language to Query feature as specified in `NL2QueryPRD.md`. The feature allows logged-in users to ask questions in plain English; an LLM translates them into the query config format; the config loads into the form and runs the query.

**Status:** Phase 1 ✅ Phase 2 ✅ Phase 3 🔲 Phase 4 🔲

---

## Relevant Files

- `app/projects/sports_schedules/routes.py` — Add `POST /api/nl-query` route; update index route to pass `credits` for modal. Imports: `login_required`, `LogEntry`, `config_to_params`, `build_nl_prompt`, `call_nl_llm`.
- `app/models.py` — `LogEntry` for audit logging.
- `app/projects/sports_schedules/templates/sports_schedules/index.html` — Add "Ask a Question" button, modal markup, modal JS.
- `app/projects/sports_schedules/static/css/sports_schedules.css` — Styles for `ss-nl-*` modal and button.
- `app/projects/sports_schedules/core/nl_prompt.py` (new) — Prompt builder: schema, few-shot examples, allowed values. Builds full prompt with today's date.
- `app/projects/sports_schedules/core/nl_service.py` (new) — Calls Gemini (`gemini-3-flash-preview`), returns `(content, metadata)` with `input_tokens`, `output_tokens`.
- `app/projects/sports_schedules/core/sample_queries.py` — Use `config_to_params()` for merging config with anchor date.
- `app/projects/sports_schedules/core/query_builder.py` — Use `build_sql()` to validate config before returning.
- `app/projects/sports_schedules/core/constants.py` — Source for `SPORTS`, `LEVELS`, `DAYS`, `US_STATE_CODES`, `LEAGUE_CODES`, `LEAGUE_DISPLAY_NAMES` (via leagues).

### Notes

- All new CSS classes use the `ss-` prefix.
- No database migrations; feature uses existing `User.credits` and `LogEntry`.
- `GOOGLE_API_KEY` must be set in `.env`.
- **Model:** Use `gemini-3-flash-preview` only; no fallback to other models.
- **Few-shot examples:** Use examples 1–15 from PRD §Full JSON Examples as-is, including Example 4 with `league: ["CL"]` (Champions League)—we have this code in our league set.

---

## Phase 1: NL Prompt & LLM Service

### 1.1 Create Prompt Builder Module

- [x] Create `app/projects/sports_schedules/core/nl_prompt.py`
- [x] Define `build_nl_prompt(question: str, today_ymd: str) -> str` — returns a single string (no separate system/user blocks; Gemini accepts concatenated prompt).
  - [x] **Order:** Instructions → schema → date spec → allowed values → few-shot examples → user question.
  - [x] Include system instructions: translate NL to JSON config or return `{ "error": "..." }` if not answerable.
  - [x] Include today's date: "Today's date is {today_ymd}" so LLM can resolve "tomorrow", "this weekend", etc. (Few-shot examples can use fixed 2026-02-20.)
  - [x] Include full schema: dimensions, filters (low + high), date modes, date params per mode.
  - [x] Include date filter spec table (from PRD §5): what LLM must provide vs may omit for each `date_mode`.
  - [x] Include allowed values for low-cardinality:
    - [x] **sport:** from `constants.SPORTS`
    - [x] **level:** from `constants.LEVELS`
    - [x] **day:** from `constants.DAYS`
    - [x] **home_state:** from `constants.US_STATE_CODES`; add brief state-name→code mapping (e.g., "New Jersey" → NJ) if not obvious.
    - [x] **league:** from `constants.LEAGUE_CODES` with `LEAGUE_DISPLAY_NAMES` for mapping.
  - [x] Include few-shot examples: NL question → full JSON config. Use examples 1–15 from PRD §Full JSON Examples (with today=2026-02-20 for relative dates in examples).
  - [x] Keep prompt reasonably sized; trim examples if needed.
  - [x] Append user question at end.
- [x] Document output format: exactly `{ "config": {...} }` or `{ "error": "..." }`; no markdown, no extra text.

**Manual Testing 1.1:**
- [ ] Call `build_nl_prompt("Celtics games this week", "2026-02-20")` and verify prompt contains today, schema, examples, and question.
- [ ] Verify prompt length is manageable (e.g., < 8000 chars or token estimate).

---

### 1.2 Create NL LLM Service

- [x] Create `app/projects/sports_schedules/core/nl_service.py`
  - [x] Use `google.genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))`.
  - [x] Define `call_nl_llm(prompt: str) -> tuple[str, dict]`
    - [x] Call `gemini_client.models.generate_content(model="gemini-3-flash-preview", contents=prompt, config={"max_output_tokens": 2048})`. Use this model only; no fallback.
    - [x] Return `(response.text, metadata_dict)` where `metadata_dict` has `input_tokens`, `output_tokens` (from `usage_metadata` if available).
    - [x] Handle timeout (e.g., 60s); handle API errors; propagate exceptions.
  - [x] Do not add pricing/cost logic; tokens are for logging only.

**Manual Testing 1.2:**
- [ ] In Flask shell or test script: build prompt for "Celtics games this week", call `call_nl_llm(prompt)`.
- [ ] Verify response contains valid JSON with `config` or `error`.
- [ ] Verify `input_tokens` and `output_tokens` are present in metadata when Gemini provides them.

---

## Phase 2: Backend API

### 2.1 POST /api/nl-query Route

- [x] Add `POST /sports-schedules/api/nl-query` route in `routes.py`
- [x] Apply auth check; return 401 `{ "error": "Login required" }` if not authenticated.
- [x] Parse JSON body: `data = request.get_json()`; `question = (data.get("question") or "").strip()` (handle `data is None` → 400).
- [x] Validate input:
  - [x] If empty or whitespace-only → 400 `{ "error": "Question is required" }`
  - [x] If `len(question) > 500` → 400 `{ "error": "Question must be 500 characters or less" }`
- [x] Check credits: if `current_user.credits < 1` → 400 `{ "error": "Insufficient credits" }`
- [x] Compute today's date: `datetime.utcnow().strftime("%Y-%m-%d")` (or use user timezone if available; PRD allows server time for V1).
- [x] Build prompt: `prompt = build_nl_prompt(question, today_ymd)`
- [x] Call LLM: wrap `call_nl_llm(prompt)` in try/except. On exception → return 500 `{ "error": "Natural language search is temporarily unavailable." }`; do not deduct credits; log exception. Otherwise `content, metadata = ...`.
- [x] Extract JSON from `content`:
  - [x] Strip markdown code fences if present.
  - [x] Extract first JSON object: find first `{`, then scan with brace-counting until matching `}`; parse that substring. (Handles nested objects.)
  - [x] If parse fails → return 200 `{ "error": "Could not parse response", "raw": content[:2000] }`. Do not retry.
- [x] Check for `config` or `error` key:
  - [x] If `"error" in parsed`: return 200 `{ "error": parsed["error"] }`. Do not deduct credits. Log with tokens.
  - [x] If `"config" in parsed`: proceed to validation.
- [x] Merge config: `params = config_to_params(parsed["config"], today_ymd)` (from `sample_queries`). This fills `anchor_date` and computes `date_start`/`date_end` for `this_weekend`; other date fields come from the config.
- [x] Validate: `sql, err = build_sql(params)`
  - [x] If `err`: return 400 `{ "error": "Could not run that query" }`. Do not deduct credits. Log with tokens.
- [x] On success:
  - [x] Deduct 1 credit: `current_user.credits -= 1`
  - [x] Create `LogEntry` (actor_id=`current_user.id`, project=`sports_schedules`, category=`NL Query`, description=`"NL query: '{q}' → config. input_tokens={i}, output_tokens={o}. 1 credit used."`). Truncate question if long.
  - [x] `db.session.commit()`
  - [x] Return 200 `{ "config": parsed["config"], "remaining_credits": current_user.credits }`
- [x] Log all outcomes (refusal, parse error, build_sql error, LLM exception): same format with outcome type; no credit line when not deducted. Always include `actor_id=current_user.id` on `LogEntry`.
- [x] **CSRF:** Match saved-queries pattern — client sends `X-CSRFToken` header from `meta[name="csrf-token"]`; route does not use `@csrf.exempt`.

**Manual Testing 2.1:**
- [ ] Log in, ensure user has ≥1 credit. POST with valid question; verify 200 with `config` and `remaining_credits`.
- [ ] Verify credits decremented.
- [ ] Verify LogEntry created with tokens.
- [ ] POST with empty question → 400.
- [ ] POST with question length > 500 → 400.
- [ ] Log out and POST → 401.
- [ ] Use admin to set user credits to 0; POST → 400 "Insufficient credits".
- [ ] POST with off-topic question (e.g., "Tell me a joke") → 200 with `error`; credits not deducted.
- [ ] If LLM returns malformed JSON, verify 200 with `error` and `raw`; credits not deducted.
- [ ] If LLM raises (simulate by invalid API key or timeout): verify 500; credits not deducted.

---

## Phase 3: UI — Modal & Integration

### 3.1 Add "Ask a Question" Button & Modal Markup

- [ ] In `index.html`, inside `ss-main`, add "Ask a Question" section **above** `ss-saved-queries` (so it appears first for logged-in users).
- [ ] Only render when `is_authenticated` (use `{% if is_authenticated %}`).
- [ ] If `current_user.credits < 1`, show disabled state or message: "Insufficient credits" (match chatbot pattern).
- [ ] Add button: e.g. `<button type="button" class="ss-nl-ask-btn" id="ss-nl-ask-btn">Ask a Question</button>`
- [ ] Add modal structure (use `ss-` prefix for all classes):
  - [ ] Overlay: `ss-nl-modal-overlay` (hidden by default)
  - [ ] Modal: `ss-nl-modal` with:
    - [ ] Title: "Ask a question about the schedule"
    - [ ] Credits display: "1 credit per question • You have X credits" (pass `current_user.credits` from route).
    - [ ] Textarea or input: `ss-nl-input` (maxlength=500, placeholder="e.g., Celtics games this week")
    - [ ] Character count: "0 / 500"
    - [ ] Submit button: `ss-nl-submit`
    - [ ] Cancel/Close button
    - [ ] Error message area: `ss-nl-error` (hidden by default)
    - [ ] Loading spinner/state: `ss-nl-loading` (hidden by default)
- [ ] Update index route to pass `credits=current_user.credits if current_user.is_authenticated else 0`.

**Manual Testing 3.1:**
- [ ] Logged-in: "Ask a Question" button visible above Saved Queries.
- [ ] Anonymous: button not visible.
- [ ] Click opens modal with credits display.
- [ ] Modal has input, submit, cancel. Character count updates.

---

### 3.2 Modal JavaScript

- [ ] Add `ssInitNlModal()` and call it from the existing DOMContentLoaded / page-init logic when `is_authenticated`.
- [ ] Open modal: click `ss-nl-ask-btn` → show overlay and modal.
- [ ] Close modal: click overlay or Cancel → hide modal.
- [ ] Prevent submit when:
  - [ ] Input is empty or whitespace-only → show "Please enter a question" or disable submit.
  - [ ] Input length > 500 → enforce maxlength; disable submit if over.
- [ ] On submit:
  - [ ] Disable submit, show loading spinner.
  - [ ] POST to `{{ url_for('sports_schedules.api_nl_query') }}` with `{ "question": question }`.
  - [ ] Include `X-CSRFToken` header from `meta[name="csrf-token"]` (same pattern as saved-queries fetch).
  - [ ] Content-Type: application/json.
- [ ] On success (200 with `config`):
  - [ ] Close modal.
  - [ ] Call `ssLoadQueryAndRun(config)` — this function lives in the same template's script (loads config into form, updates URL, runs query).
  - [ ] Store `remaining_credits` from response; when modal is reopened, show updated count.
- [ ] On error (200 with `error`, or 4xx):
  - [ ] Keep modal open.
  - [ ] Show error message in `ss-nl-error` (from `response.error`).
  - [ ] If `raw` present (malformed JSON), show in UI or log to console for debugging.
  - [ ] Re-enable submit, hide loading.
- [ ] On network/500 error: show "Natural language search is temporarily unavailable. Try the filters below." or similar.

**Manual Testing 3.2:**
- [ ] Submit "Celtics games this week" → modal closes, form populates with config, query runs, results appear.
- [ ] Submit "Tell me a joke" → modal stays open, error message shown; credits unchanged.
- [ ] Submit with empty input → submit disabled or validation message.
- [ ] Verify loading state during request.
- [ ] Verify malformed JSON response shows raw in console or UI.
- [ ] Verify credits display updates after successful query.

---

### 3.3 Styles

- [ ] Add styles in `sports_schedules.css` for:
  - [ ] `ss-nl-ask-btn` — button above Saved Queries.
  - [ ] `ss-nl-modal-overlay` — full-screen overlay, semi-transparent.
  - [ ] `ss-nl-modal` — centered modal, white background, shadow, max-width.
  - [ ] `ss-nl-input` — textarea/input styling.
  - [ ] `ss-nl-error` — error text styling (e.g., red).
  - [ ] `ss-nl-loading` — spinner or "Loading..." styling.
- [ ] Ensure mobile-friendly (modal usable on small screens).

**Manual Testing 3.3:**
- [ ] Modal looks correct on desktop and mobile.
- [ ] All interactive elements have adequate tap/click targets.

---

## Phase 4: Polish & Edge Cases

### 4.1 Insufficient Credits & Validation

- [ ] Verify insufficient-credits handling (built in 3.1): when `credits < 1`, button disabled or message shown; modal submit disabled.
- [ ] Verify server validation from 2.1: empty body, whitespace-only question, or length > 500 → 400 before any LLM call.

**Manual Testing 4.1:**
- [ ] Set user credits to 0; verify button disabled or message shown; API returns 400.
- [ ] POST with empty body, `question: "   "`, or length > 500 → 400.

---

### 4.2 Logging Audit

- [ ] Verify every NL query attempt is logged (success, refusal, parse error, build_sql error).
- [ ] Verify `input_tokens` and `output_tokens` included in log description when LLM returns them.
- [ ] On success, log includes "1 credit used" in description.

**Manual Testing 4.2:**
- [ ] Run a few queries (success, refusal); check LogEntry in admin or DB for project `sports_schedules`.
- [ ] Confirm token counts appear in descriptions.

---

### 4.3 Final Integration Test

- [ ] Anonymous user: no "Ask a Question" visible; can use rest of app normally.
- [ ] Logged-in user with credits: full flow works.
- [ ] Try sample questions from PRD: "Celtics games this week", "Red Sox vs Yankees", "College basketball in NJ next week", "What games are in New Jersey this weekend?"
- [ ] Try refusal: "Tell me a joke" → error shown, no credit deducted.
- [ ] Verify URL updates and query runs same as when loading a saved query.

**Manual Testing 4.3:**
- [ ] End-to-end: ask question → see results; ask off-topic → see error.
- [ ] Verify no regressions to saved queries, sample queries, or main query builder.

---

## Summary Checklist

- [x] Phase 1: Prompt builder + LLM service
- [x] Phase 2: API route with auth, credits, validation, logging
- [ ] Phase 3: Modal UI + JS integration + styles
- [ ] Phase 4: Edge cases, logging audit, final test
