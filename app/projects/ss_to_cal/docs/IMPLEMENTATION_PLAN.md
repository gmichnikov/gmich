# SS to Cal — Implementation Plan

Implementation order and checkpoints for SS to Cal v1.

**References:** All product behavior → [prd.html](./prd.html). If code and PRD disagree, update whichever is wrong — don't let them drift silently.

**No database in v1.** Do not run `flask db migrate` for this project. Finish each phase's **Manual checks** before starting the next one.

---

## How to use this document

- **Phases 1–6** are delivery milestones: complete one phase, run its checks, then move on.
- The **Tasks** section at the bottom is the same work broken into checkbox items for day-to-day tracking.
- **PRD §** references map to sections in `prd.html` (Overview = §01, User flow = §03, … Scope = §12).

**Build priority:** **PWA installable → share POST works on Android → vision extraction → review form → Google Calendar URL → error states.** Validate the share sheet on a real phone **before** wiring Gemini — that is the riskiest integration.

**PRD alignment:** Section **[PRD traceability](#prd-traceability)** maps PRD sections to phases.

---

## At a glance: milestones

| Phase | Deliverable | PRD pointer |
| ----- | ----------- | ----------- |
| **1** | PWA shell: manifest, service worker, icons, install vs standalone UI | §07, §10, NFR-03, NFR-04 |
| **2** | Share target route: `POST /ss-to-cal/share` → dummy review form (no LLM) | §03 steps 1–2, FR-01, FR-08 |
| **3** | Server image resize + Gemini extraction (`gemini-3-flash-preview`) | §07, FR-02, NFR-01, NFR-02 |
| **4** | Review form: fields, amber highlights, validation, timezone | §04, FR-03–FR-05, FR-07 |
| **5** | Google Calendar URL builder (client-side) | §09, FR-06 |
| **6** | Error states, offline shell, success-criteria test pass | §06, §08, §11 |

**Deferred from v1:** database/models, event history, Sonnet fallback (unless Phase 6 testing fails), manual file upload on index, iOS, Outlook/.ics, credits/rate limiting.

---

## Repo conventions

- Blueprint **`ss_to_cal`** at **`/ss-to-cal`** (already registered).
- CSS classes prefixed **`sstc-`** so styling doesn't collide with other hub projects.
- Static assets under the blueprint **`static/`** folder (served at `/ss-to-cal/static/…`); templates under **`templates/ss_to_cal/`**.
- **`log_project_visit('ss_to_cal', ...)`** on **`GET /ss-to-cal/`** (already on index route).
- **`GET /ss-to-cal/`** — `@login_required`. **`POST /ss-to-cal/share`** — auth checked **manually** in the view (do **not** use `@login_required` on `/share`; it redirects and drops the multipart body). Manifest + service worker served **without** auth.
- **`POST /ss-to-cal/share`** is **`@csrf.exempt`** (Android share POST has no CSRF token).
- Env vars: **`GOOGLE_API_KEY`** (required for Phase 3+). **`POSTHOG_API_KEY`** (already in hub — used for extraction analytics + LLM cost). **`ANTHROPIC_API_KEY`** only if switching to Sonnet fallback.

---

## Likely modules (end state)

| File | Role |
| ---- | ---- |
| `routes.py` | `/`, `/share`, `/manifest.webmanifest`, `/sw.js` |
| `extraction.py` | Gemini vision call, system prompt, JSON parse |
| `logging_utils.py` | `LogEntry` + PostHog capture for each share/extraction |
| `image_utils.py` | Decode upload, resize to max 1600px long edge, optional JPEG recompress |
| `templates/ss_to_cal/index.html` | Install instructions (browser) vs ready copy (standalone PWA) |
| `templates/ss_to_cal/share.html` | Review form (returned from share POST) |
| `templates/ss_to_cal/share_login.html` | Unauthenticated share landing (HTTP 200, no redirect) |
| `static/ss_to_cal.css` | Prefixed styles (blueprint `static_folder`) |
| `static/ss_to_cal.js` | Form validation, amber field logic, Google Calendar URL |
| `static/sw.js` | Cache app shell only |
| `static/icons/icon-192.png` | PWA icon |
| `static/icons/icon-512.png` | PWA icon |

Reuse patterns from:

- **`app/projects/docs_demo/gemini_service.py`** — simple Gemini call shape (vision uses PostHog client instead)
- **`app/projects/sports_schedules/core/nl_service.py`** — `PostHogGeminiClient`, model id `gemini-3-flash-preview`, token metadata from `usage_metadata`
- **`app/projects/sports_schedules/routes.py`** — `LogEntry` + `posthog.capture()` dual logging on NL queries

Do **not** reuse Helper's text-only Claude pipeline for vision. For Sonnet fallback, reuse **`app/projects/helper/claude.py`** JSON parse helper only.

---

## Observability (required)

Log **every share POST** — this is the meaningful "tool used" event (not just the index visit).

### Two channels (match hub conventions)

| Channel | Purpose |
| ------- | ------- |
| **`LogEntry`** (DB) | Visible in hub admin activity log; permanent audit trail |
| **PostHog** | Analytics dashboards, LLM observability, cost tracking |

### What to log

**Authenticated extraction** (`category=Extraction`):

| Field | Source |
| ----- | ------ |
| `outcome` | `success` \| `no_event_found` \| `parse_failed` \| `api_error` \| `timeout` \| `image_error` |
| `latency_ms` | Wall clock for entire `/share` handler (resize + API + parse) |
| `api_latency_ms` | Gemini call only (optional but useful) |
| `model` | e.g. `gemini-3-flash-preview` |
| `input_tokens`, `output_tokens` | `response.usage_metadata` |
| `confidence` | From parsed JSON when present |
| `fields_populated` | Count of non-null extracted fields (title, date, …) |
| `image_width`, `image_height` | After resize — not original upload size |
| `error_code` | PRD §06 code when applicable |

**Unauthenticated share** (`category=Share`, `outcome=not_logged_in`) — no LLM call, no tokens.

**Index visit** — already handled by `log_project_visit('ss_to_cal', …)` on `GET /`.

### Implementation sketch

```python
# logging_utils.py
def log_share_extraction(*, actor_id, outcome, latency_ms, model=None,
                         input_tokens=0, output_tokens=0, confidence=None,
                         fields_populated=0, image_width=None, image_height=None,
                         error_code=None, api_latency_ms=None):
    # 1. LogEntry with human-readable description (like sports_schedules NL Query)
    # 2. posthog.capture("ss_to_cal_extraction", distinct_id=str(actor_id), properties={...})
```

**Gemini client** — use `posthog.ai.gemini.Client` (not plain `google.genai.Client`) so PostHog AI observability records **cost per call** automatically. Pass `posthog_distinct_id=str(current_user.id)` and `posthog_properties={"project": "ss_to_cal"}`.

**Privacy** — never log screenshot bytes, raw model response, or extracted title/location text in `LogEntry.description`. Metadata only.

**Cost** — rely on PostHog LLM analytics for dollar amounts; include token counts in `LogEntry` description for quick scanning (same as `chatbot` / `sports_schedules`). Optional: append rough `est_cost_usd` in description using Gemini list pricing × tokens if you want it in the admin log without opening PostHog.

---

## Hub integration notes

**Blueprint** — already in `app/__init__.py` and `app/projects/registry.py` (`auth_required: true`).

**Unauthorized share POST** — default Flask-Login redirect drops the multipart body. **Required pattern for `/share`:**

- Do **not** decorate `/share` with `@login_required`.
- At the top of the view: `if not current_user.is_authenticated:` → render **`share_login.html`** with HTTP **200**.
- Alternatively, extend `app/__init__.py` `unauthorized_handler` for `/ss-to-cal/share` only — but manual check in the route is simpler and keeps logic in the project.

**Share/review templates** — consider a **minimal layout** for `share.html` (no hub navbar clutter on mobile). `index.html` can keep extending `base.html`.

**Manifest MIME type** — serve `manifest.webmanifest` with `Content-Type: application/manifest+json`.

**Service worker scope** — register with scope `/ss-to-cal/`; cache only static shell + index HTML (not `/share` responses).

**HTTPS** — share target requires production HTTPS or ngrok for dev testing on Android.

---

## Phase 1 — PWA shell (installable)

Goal: user can install SS to Cal to the home screen; app detects standalone vs browser tab.

### Work

1. **`GET /ss-to-cal/manifest.webmanifest`** — return JSON from PRD §07 (name, scope, icons, `share_target`). Can be a static file or Flask route with correct MIME type.
2. **`GET /ss-to-cal/sw.js`** — minimal service worker: cache `ss_to_cal.css`, `ss_to_cal.js`, icons; network-first for `/share`.
3. **Icons** — add `icon-192.png` and `icon-512.png` under `static/icons/` (manifest paths must match).
4. **`index.html`** — link manifest; register service worker in a small inline script or `ss_to_cal.js`.
5. **Install detection** — if `display-mode: standalone` (or `navigator.standalone` where relevant), show short "Share a screenshot to SS to Cal" copy. Otherwise show PRD §10 install steps (Chrome Android → log in → Add to Home Screen → test share sheet).
6. **Base template** — ensure `base.html` doesn't break standalone (viewport meta already present).

### Manual checks

- [ ] On Android Chrome, open **`/ss-to-cal/`** while logged in.
- [ ] Chrome offers **Add to Home Screen** (or three-dot menu works).
- [ ] Installed app opens **standalone** (no URL bar).
- [ ] In browser tab, index shows **install instructions**; in standalone, shows **ready** copy.
- [ ] DevTools → Application → Manifest validates (icons, scope, share_target present).
- [ ] Service worker registers without errors.

**Stop here.** Share target won't appear useful until Phase 2, but install + manifest must work first.

---

## Phase 2 — Share target (no LLM)

Goal: screenshot → Share → SS to Cal → review form page. **This is the critical path.**

### Work

1. **`POST /ss-to-cal/share`** — `@csrf.exempt` only (no `@login_required`; see Hub integration notes).
2. Read multipart field **`image`** (per manifest `params.files[].name`).
3. Validate: file present, MIME `image/*`, reasonable size cap (e.g. 10 MB before resize).
4. If **not authenticated** (`not current_user.is_authenticated`): render **`share_login.html`** with HTTP **200**; log `LogEntry(category=Share, outcome=not_logged_in)`.
5. If authenticated: for now, **skip LLM** — render **`share.html`** with placeholder/empty fields and optionally show "Image received" confirmation (do not persist image to disk).
6. Embed empty extraction JSON in page for JS: `{ title: null, date: null, startTime: null, endTime: null, location: null, description: null, timezone: null, confidence: null }`.
7. Manifest `share_target.action` is **`/ss-to-cal/share`** (Phase 1 manifest).

### Manual checks (Android phone, HTTPS)

- [ ] Log in, install PWA, take a screenshot, tap **Share** → **SS to Cal** appears in list.
- [ ] Tapping it opens the app and lands on **review form** (even if fields are empty).
- [ ] If logged out, share shows **login prompt page** (not a broken redirect).
- [ ] Restart Chrome once if share target missing after install (known Android quirk).

**Stop here.** Do not proceed to Gemini until this flow works reliably.

---

## Phase 3 — Image processing + Gemini extraction

Goal: share POST returns form pre-filled from real screenshot content.

### Work

1. **`image_utils.py`** — open upload with **Pillow** (`Pillow` is not in `requirements.txt` today — add it, or confirm an existing image lib in the hub before Phase 3). Resize so longest edge ≤ **1600px**; output JPEG at sensible quality for API upload.
2. **`extraction.py`**:
   - Model: **`gemini-3-flash-preview`**
   - Client: **`posthog.ai.gemini.Client`** with `GOOGLE_API_KEY` + `_posthog` (mirror `sports_schedules/core/nl_service.py`)
   - Send image + PRD §07 **system prompt (verbatim)** + user message ("Extract event details from this screenshot.")
   - Pass `posthog_distinct_id=str(current_user.id)`, `posthog_properties={"project": "ss_to_cal"}`
   - Parse first JSON object from response (reuse helper-style parsing).
   - Return `(parsed_dict, metadata)` where metadata has `input_tokens`, `output_tokens`, `api_latency_ms`.
   - Preserve **`confidence`** from response for UI (PRD §04).
   - Map `{"error": "no_event_found"}` → empty fields + banner (FR-03 / §06 `NO_EVENT_FOUND`) — still show the form.
   - Never store image bytes after request completes (NFR-02).
3. **`logging_utils.py`** — call from `/share` on every outcome (success and failure); write `LogEntry` + `posthog.capture("ss_to_cal_extraction", …)`.
4. **`POST /share`** — time the handler; after resize, call `extraction.py`; pass result into `share.html` as embedded JSON; always log before returning response.
5. Log failures server-side; do not expose raw model output in HTML (FR-02).
6. Target **&lt;5s** on LTE (NFR-01); add timeout (e.g. 30s). On failure, render **`share.html`** with an inline **`API_ERROR`** or **`PARSE_FAILED`** banner (basic handling here; full copy polish in Phase 6).

### Manual checks

- [ ] Share a **confirmation email** screenshot — title + date populate correctly.
- [ ] Share a **WhatsApp** message — null or partial fields OK; no invented dates.
- [ ] Share a **non-event** image — form opens empty with message, not a dead end.
- [ ] `GOOGLE_API_KEY` unset → clear error, not 500 stack trace in UI.
- [ ] Response time feels acceptable on phone network.

**Stop here.** Evaluate extraction quality on PRD §08 screenshot types before polishing UI.

---

## Phase 4 — Review form UI

Goal: user can verify/edit extracted fields; button gating works.

### Work

1. **`share.html`** — form fields: title, date, start time, end time, location, description, timezone.
2. **`ss_to_cal.js`**:
   - Pre-fill from embedded extraction JSON.
   - **Amber highlight** + label "Required" on null title/date; "Please verify" on null optional fields when overall **`confidence`** is `medium` or `low` (PRD §04 — schema has one global `confidence`, not per-field).
   - If model returns a **`timezone`** value, pre-fill it; if it differs from device default, highlight amber + "Please verify" (PRD §04 timezone row).
   - **Low confidence banner** when `confidence === "low"`.
   - **Disable "Add to Google Calendar"** until title and date both non-empty (FR-05).
   - Timezone field always visible; default **`Intl.DateTimeFormat().resolvedOptions().timeZone`** when model returns null (FR-07).
   - Start time empty → all-day hint ("Leave blank for all-day event"). End time optional; if start set but no end, Google Calendar defaults to 1 hour (PRD §04).
3. **`ss_to_cal.css`** — amber field styles, form layout (mobile-first), prefixed classes.
4. All fields editable; form always shown after extraction (FR-03).

### Manual checks

- [ ] Required fields highlighted when null; button disabled until filled.
- [ ] Filling title + date enables button immediately.
- [ ] Low-confidence extraction shows top banner.
- [ ] Timezone shows device default; user can change it.
- [ ] Layout usable on phone in standalone PWA.

**Stop here.** Calendar button can be a no-op or `alert` until Phase 5.

---

## Phase 5 — Google Calendar URL

Goal: one tap opens pre-filled Google Calendar event form.

### Work

1. **`ss_to_cal.js`** — build URL per PRD §09:
   - Base: `https://calendar.google.com/calendar/render?action=TEMPLATE`
   - `text`, `details`, `location` — URL-encoded
   - **Timed events:** convert local date+time+timezone to UTC; format `YYYYMMDDTHHMMSSZ/…`
   - **All-day:** `dates=YYYYMMDD/YYYYMMDD` with end date = day after start (Google requirement)
2. **"Add to Google Calendar"** — `window.open(url)` or `location.href = url`.
3. Handle edge cases: end time without start time (ignore or default), invalid timezone (fall back to device TZ).

### Manual checks

- [ ] Timed event: Google Calendar opens with correct title, date, time, location, description.
- [ ] All-day event (no start time): correct all-day behavior in Google Calendar.
- [ ] Timezone change on form affects UTC conversion correctly.
- [ ] Special characters in title/location encode properly.

**Stop here.** Full happy path should work end-to-end.

---

## Phase 6 — Error states, offline shell, success criteria

Goal: PRD §06 covered; §11 success criteria met on real screenshots.

### Work

1. Inline error UI (no `alert()`):
   - `OFFLINE` — service worker / `navigator.onLine` where applicable; message per PRD
   - `API_ERROR`, `PARSE_FAILED` — retry affordance where possible (note: share POST can't retry same image easily; retry may mean "go back and share again")
   - `IMAGE_TOO_LARGE` / decode failures
2. Offline: app shell loads from service worker; extraction shows offline message when network unavailable.
3. Collect **≥10 representative test screenshots** covering PRD §08 categories (8 source types — use multiple examples where helpful). Score title+date accuracy: **8/10** must pass without user correction (PRD §11).
4. **Zero invented dates** — if Gemini hallucinates, consider **`claude-sonnet-4-6`** fallback (PRD Model selection) before more prompt tuning.
5. Remove placeholder copy from index; final polish on install instructions.

### Manual checks

- [ ] Each error code in PRD §06 has correct message + recovery copy.
- [ ] **8/10** representative screenshots extract title+date correctly (§11).
- [ ] **Zero** invented dates/times not visible in screenshot (§11).
- [ ] Extraction completes in **&lt;5s** on LTE for typical screenshots (§11).
- [ ] Share sheet → review → Calendar works as one smooth flow.
- [ ] Each extraction writes `LogEntry` + PostHog event with latency and tokens.

---

## PRD traceability

| PRD section | Phase(s) |
| ----------- | -------- |
| §01 Overview | All |
| §02 Problem | — (context only) |
| §03 User flow | 2–5 |
| §04 Missing fields | 4 |
| §05 FR-01 share target | 1–2 |
| §05 FR-02 extraction | 3 |
| §05 FR-03 always show form | 3–4 |
| §05 FR-04 amber highlights | 4 |
| §05 FR-05 button gating | 4 |
| §05 FR-06 Calendar URL | 5 |
| §05 FR-07 timezone | 4 |
| §05 NFR-05 observability | 2, 3 |
| §05 FR-08 auth | 2 |
| §06 Error states | 2, 3, 6 |
| §07 Model selection | 3, 6 (Sonnet fallback if needed) |
| §08 Screenshot types | 3, 6 (testing) |
| §09 Calendar integration | 5 |
| §10 Install flow | 1 |
| §11 Success criteria | 6 |
| §12 Scope / non-goals | — (defer DB, email, iOS, etc.) |

---

## Testing on Android (dev)

Share target requires **HTTPS** reachable from the phone.

1. Deploy to Heroku staging/production, **or** run locally with **ngrok** (or similar) tunneling to Flask.
2. Open tunneled **`/ss-to-cal/`** in Chrome Android — not desktop emulation.
3. Log in → install PWA → test share from Gallery/Screenshots app.

Desktop Chrome DevTools can simulate manifest and service worker but **cannot** fully replace real share-sheet testing.

---

## Tasks (checkbox tracker)

### Phase 1 — PWA shell

- [ ] Add `manifest.webmanifest` route or static file
- [ ] Add `sw.js` with shell cache list
- [ ] Add 192 + 512 icons
- [ ] Link manifest + register SW from index
- [ ] Standalone vs browser UI split on index
- [ ] Manual: install on Android, manifest validates

### Phase 2 — Share target stub

- [ ] `POST /ss-to-cal/share` with `@csrf.exempt` (manual auth check, not `@login_required`)
- [ ] Multipart `image` handling + basic validation
- [ ] `share_login.html` for unauthenticated (200) + `LogEntry` for `not_logged_in`
- [ ] `share.html` dummy form
- [ ] Manual: share screenshot on phone → form opens

### Phase 3 — Extraction

- [ ] `image_utils.py` resize (max 1600px)
- [ ] `extraction.py` + PostHog Gemini client + PRD prompt
- [ ] `logging_utils.py` — LogEntry + `ss_to_cal_extraction` PostHog event
- [ ] JSON parse + `no_event_found` handling
- [ ] Wire into `/share`; embed JSON in template; log all outcomes
- [ ] Manual: email + WhatsApp + non-event screenshots

### Phase 4 — Review form

- [ ] All form fields + amber/required/verify styling
- [ ] Low-confidence banner
- [ ] Button enable/disable logic
- [ ] Device timezone default
- [ ] Manual: edit fields, gating works

### Phase 5 — Calendar URL

- [ ] UTC conversion for timed events
- [ ] All-day date format
- [ ] URL encode all params
- [ ] Manual: open Google Calendar, verify pre-fill

### Phase 6 — Polish

- [ ] All §06 error states
- [ ] Offline shell behavior
- [ ] §08 fixture test pass (8/10, zero invented dates)
- [ ] Sonnet fallback only if needed

---

## Open questions (defer unless blocked)

| ID | Question | Default for v1 |
| -- | -------- | -------------- |
| OQ-01 | Multi-event screenshots — note in UI? | Extract most prominent only; no UI note (PRD §12) |
| OQ-02 | Include `est_cost_usd` in LogEntry description? | Optional; PostHog is source of truth for cost; tokens in LogEntry are enough for v1 |
| OQ-03 | Retry on API_ERROR from share POST | "Share again" copy; no in-memory image retry |
| OQ-04 | `share.html` extends `base.html` or minimal layout? | Minimal layout for share/review (recommended) |

---

## Explicitly out of scope (v1)

Per PRD §12: database/models, event history, email, iOS/Safari, Calendar API OAuth, Outlook/.ics, multi-event extraction, recurring events, analytics dashboard, separate user accounts.
