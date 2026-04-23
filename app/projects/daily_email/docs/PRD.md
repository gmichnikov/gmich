# Daily Email — Product Requirements Document

## 1. Overview

**Vision:** Each signed-in user receives one **HTML morning digest email** per day, assembled from multiple data sources. Content is **user-configurable within fixed caps and guardrails** so the product stays predictable for cost, API quotas, latency, and email size.

**Origin:** This product evolves the ideas in [`initial_idea.md`](initial_idea.md) (single script, static config, cron) into a **multi-tenant Flask app**: per-user settings, database-backed preferences, centralized scheduling, and delivery via **Mailgun** (same family of patterns as elsewhere in the hub).

**Design principle:** *Wide menu, narrow portions* — users choose **which modules** appear and **how much** of each (e.g. up to N locations, N tickers, N teams), not unbounded lists.

### 1.1 Resolved product decisions

| Topic | Decision |
|--------|----------|
| **Send time** | User chooses **when** the digest is sent, interpreted in **their own timezone**. The UI must **always show that timezone** next to the time control (and anywhere “next send” / “last send” is summarized) so it is unambiguous. Timezone should align with the hub user profile field used elsewhere (e.g. same as Reminders). **Delivery expectation:** copy must state that the email **may arrive within about an hour after** the chosen time, because sends are batched on an hourly scheduler. |
| **Scheduler** | **Heroku Scheduler** runs **every hour**, determines which users are due for a send in that run, and sends those digests. |
| **Section order** | **Fixed product order** (no user reordering). **v1 order:** weather → stocks → sports scores → Ashby jobs (§1.2). Only **enabled** sections appear. |
| **Delivery provider** | **Mailgun** for outbound mail. |
| **Test send** | **Costs one credit**, same as a real digest send (aligned with Reminders “test now” behavior). |
| **Partial failures** | A failed fetch or render for **one module must not block** the rest: omit or replace that section, log the error, **still send** the email. If **every** module fails, see **“All modules fail”** above. |
| **Google Calendar** | **Out of scope** until a later phase (no OAuth / agenda in early releases). |
| **Storing email body** | **Do not persist** full HTML or plaintext of sent digests. OK to store **metadata only** (see §8). |
| **Credits** | Each successful digest send consumes **one hub credit**, same conceptual model as **Reminders** (and AI projects). If the user has **0 credits**, behavior should match the established hub pattern (e.g. skip send, log, surface in UI — mirror Reminders semantics). |
| **All modules fail** | **Still send** the email: a short **“nothing loaded”** digest (explain that sections could not be fetched; link to settings). **Credit:** **deduct one credit** for that send (same as a populated digest), so behavior stays simple and matches user expectation of “I got my daily email.” |
| **Credit deduct timing** | **Recommended:** deduct **one credit only after Mailgun accepts the message** (HTTP success / 2xx from the send API), same spirit as “don’t charge if we never handed off to the provider.” If Reminders already use a different hook, **match Reminders exactly** for one consistent rule across the hub. |
| **Idempotency & DST** | **Recommended:** one successful digest **per user per local calendar date** (in `User.time_zone`), enforced with a unique constraint or atomic “mark sent for local_date” **before** calling Mailgun. DST: use **IANA timezone** (e.g. `America/New_York`) and let the zone database define the local calendar day; avoid “fixed UTC offset” for users who observe DST. |
| **Third-party API keys** | **Resolved:** **shared hub keys** per vendor (`config` / env), with **caching and per-user caps** so no single user burns the quota. “BYO key” is a later power-user feature if ever needed. |
| **Mailgun integration** | **Resolved:** **reuse** the existing Mailgun paths and patterns already used elsewhere in this web app (same domain, credentials, and proven delivery). |
| **Weather locations** | **Resolved:** **geocode** city/ZIP → **lat/lon**, store coordinates + display label; forecast calls use coordinates (e.g. **Open-Meteo Geocoding** + Open-Meteo forecast — see §7.2). |
| **Compliance (was “List-Unsubscribe huh?”)** | Means: bulk/marketing-style mail often needs a **visible unsubscribe / manage email** path and sometimes specific **email headers** so inbox providers (Gmail, etc.) trust you. For a **signed-in, opted-in daily utility** digest, requirements are usually lighter than cold marketing, but you should still use a **clear From**, **reply or preferences link**, and follow Mailgun’s guidance for your domain (SPF/DKIM already on your sending domain). |
| **Heroku “many emails at once”** | See **§7.1** — not inherently bad at small/medium scale; watch **dyno timeout** and Mailgun rate limits. |

### 1.2 v1 modules (product scope — locked)

Digest **v1** includes **exactly these four sections**, in this **fixed order** (each can be disabled per user unless noted):

| # | Module | Summary |
|---|--------|---------|
| 1 | **Weather** | Open-Meteo; locations via geocode → stored lat/lon; limits **§4.3**. |
| 2 | **Stocks** | Quotes / day change for user-chosen tickers (e.g. yfinance); limits **§4.3**; no trading advice copy. |
| 3 | **Sports scores** | ESPN scoreboard **per league**, filtered to user’s **chosen teams**; **§4.2** + limits **§4.3**. |
| 4 | **Job listings (Ashby)** | **§4.1** + limits **§4.3**. |

**Not in v1:** headlines, local events, Google Calendar, Greenhouse/Lever job boards — backlog only unless promoted later.

---

## 2. Does the customization premise make sense?

**Yes.** Caps such as “up to 3 weather locations” are the right pattern because they:

- Bound third-party API calls and caching complexity per user per send.
- Keep the email readable and a consistent length band.
- Make abuse and operational cost easier to reason about than “unlimited rows.”

**Location model for weather:** Prefer **lat/lon** (or a single resolved point) internally for Open-Meteo; let the UI accept **city search**, **ZIP/postal** (country-aware), or “use my profile location” with one canonical geocode step. Document that ZIP/city resolution may be approximate.

---

## 3. What the initial idea implied but did not spell out (gaps)

| Topic | Initial idea | Product implications |
|--------|----------------|------------------------|
| **Identity** | Single recipient in config | Per-user digest; tie sends to `User` and verified email. |
| **“Morning”** | Fixed 5am | **Per-user send time** (and timezone from profile or digest-specific override). “5am” is one default, not universal. |
| **API keys** | Keys in `.env` | **NewsAPI and similar:** either hub-managed keys with strict per-user quotas, or optional “bring your own key” later. Document rate limits and caching. |
| **Google Calendar** | OAuth in a script | **Per-user OAuth** (tokens stored encrypted, refresh flow, reconnect UX). High effort; likely a later phase. |
| **Partial failure** | Script can fail as a whole | **Resolved:** omit failed sections; do not fail the whole email for one bad module (see §1.1). |
| **Unofficial / fragile APIs** | ESPN “undocumented” | Treat as **best-effort**; document risk; prefer official or licensed APIs where budget allows; graceful degradation. |
| **yfinance** | Free portfolio | Clarify **non-guarantee** of data accuracy and **Yahoo ToS**; cap tickers; no real-time trading claims. |
| **Jobs** | Ashby/Greenhouse/Lever | Per-user **company slugs + keyword filters**; cap companies and max rows per send; respect robots/API terms. |
| **Privacy** | N/A | Job filters and locations can be sensitive. **Resolved:** do not store full email contents; still decide what minimal **metadata** to retain for support and “last send” UX (§8). |
| **Legal / email hygiene** | N/A | Even “transactional” digests often need **one-click preferences** and clear identification of sender; align with host policy. |
| **Observability** | Cron only | **Send logs**, per-section timing, last-success timestamps in UI (“Weather last updated …”). |

---

## 4. v1 module detail

See **§1.2** for the four modules. Shared UX: **per-module on/off**, **caps** (**§4.3**), **partial failure** per section.

**Section ordering:** **Fixed** — weather → stocks → sports → jobs (§1.1).

**Master toggles:** Global **digest on/off** and optional **in-browser preview** (no send, **no credit**, not persisted — §9).

### 4.1 Jobs — Ashby only (v1)

**Input**

- User pastes a **public Ashby job board URL** (common host patterns include `jobs.ashbyhq.com/...` and `{org}.ashbyhq.com`) **or** a **company slug** string if easier to validate.
- Optional **filter phrase** (e.g. `Product Manager`): use it to **narrow listings** (recommended v1 rule: **case-insensitive substring match** on job **title**; optionally also **department** if the JSON exposes it). If the phrase is empty, include all open roles up to the cap.

**Fetch**

- Public JSON (no API key): `https://api.ashbyhq.com/posting-api/job-board/{companySlug}`  
- Implementation resolves URL → **`companySlug`** (document supported URL shapes; reject malformed input in UI).

**Email behavior**

- List **up to 12** matching jobs (§4.3), with title + link (and team/location if present).
- **Omit the section** (or show “no matching roles”) when there are zero matches — product choice; either is fine as long as copy is clear.

**Later (not v1):** additional boards per user, Greenhouse/Lever, keyword sets per board — see [`initial_idea.md`](initial_idea.md).

### 4.2 Sports scores — ESPN (v1, aligns with existing hub code)

**How ESPN is organized in this repo**

- The **scoreboard** endpoint is **per league**, not per team:  
  `https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard`  
  with optional `dates=YYYYMMDD-YYYYMMDD` (see `ESPNClient.LEAGUE_MAP` and `sports_scores` — e.g. `basketball` + `nba` for NBA).
- The API returns **all games in that league** for the date window; there is no “give me only these teams” parameter on that URL.
- **Teams** still matter for the product: you store the user’s **followed teams**, then **filter** the scoreboard JSON to games where home or away matches one of those teams (same idea as “my games” from a league-wide feed).

**User choice: teams (not whole leagues)**

- **League-only** would mean “every NBA game **yesterday and today**” — still too noisy for a digest unless you add arbitrary caps.
- **Recommended v1 UX:** user adds **watch entries** as **league + team** (e.g. pick league from codes you support, then pick team from that league’s roster — same building blocks as `ESPNClient.fetch_teams` / schedule admin). Stored as e.g. **`league_code` + `espn_team_id`** (or stable slug) per row.
- **Fetch strategy:** for each **distinct `league_code`** among the user’s teams, call the scoreboard **once** with `dates=` covering **yesterday and today on the user’s local calendar** (in `User.time_zone`): `YYYYMMDD-YYYYMMDD` for those two calendar days, inclusive). Then **filter** the response to games involving any of that user’s teams in that league. Many teams in the same league ⇒ **one** HTTP call per league per send.

**Reuse:** Prefer sharing / mirroring patterns from `app/projects/sports_scores/` and `app/projects/sports_schedule_admin/core/espn_client.py` rather than inventing a second ESPN integration.

**Implementation note:** ESPN returns games keyed by **calendar dates** in the request; late games or non-US timezones can occasionally look odd vs “what I watched last night.” Document edge cases if needed; v1 follows **user-local yesterday + today** as the product rule.

### 4.3 v1 limits (proposed defaults — adjust after dogfooding)

These keep email size, API fan-out, and yfinance/ESPN load predictable. All are **per user** unless noted.

| Module | Limit | Rationale |
|--------|--------|-----------|
| **Weather** | **≤ 3** saved locations | Open-Meteo calls scale with locations; three cities is plenty for a digest. |
| **Weather** | **One** forecast “bundle” per location per send | Today + short outlook (e.g. 7-day strip) in **one** logical section; AQI optional toggle v1. |
| **Stocks** | **≤ 10** tickers | yfinance is unofficial/delayed; small list stays readable and fast. |
| **Stocks** | Validate symbols server-side | Reject garbage input; show “invalid symbol” in settings, not in email. |
| **Sports** | **≤ 10** team watches (`league_code` + team) | Enough for fans; keeps filter work and email rows bounded. |
| **Sports** | **v1 leagues:** NFL, NBA, MLB, NHL only | Matches `sports_scores` / `espn_parser` support today; expand later via `LEAGUE_MAP` if needed. |
| **Sports** | **≤ ~25** game rows in the **email** (not code) | One row ≈ one game (teams + score or status). If there are more matches after filtering, truncate and optionally add “+ N more” / link to ESPN. |
| **Sports** | Show games **yesterday + today** (user’s zone) involving watched teams | Prefer **final / post** rows for readability; **in-progress** (live) and **scheduled** (upcoming today) optional in v1 with clear labels. |
| **Ashby jobs** | **1** board (URL or slug) per user | Simplest v1; slug length bound by DB field (e.g. 255). |
| **Ashby jobs** | Filter phrase **≤ 100** characters | Enough for “Product Manager” / “Backend Engineer”; prevents absurd payloads. |
| **Ashby jobs** | **≤ 12** listings in the email | Rest omitted with “see full board” link to their Ashby URL. |

**Still soft:** exact weather fields (AQI on/off), whether Ashby empty section is omitted vs. explicit “no matches,” and sports “+ N more” link — tune in implementation.

---

## 5. Post–v1 / optional (not in v1 digest)

Candidates after the four v1 modules are stable:

- **Headlines** (NewsAPI), **local events**, **Google Calendar** — were in earlier sketches; explicitly **after** v1.
- **More job sources** — Greenhouse/Lever, multiple Ashby boards per user ([`initial_idea.md`](initial_idea.md)).
- **Commute / traffic**, **RSS rollups**, **package tracking**, **crypto**, **pollen/UV**, **developer digest**, **“on this day”**, **holidays/schools** — nice-to-have backlog only.

Prioritize modules that share **one auth model** (none or OAuth once) and **clear rate limits**.

---

## 6. User experience (high level)

### 6.1 Settings / onboarding

- **Wizard or tabbed settings:** pick modules → configure each within caps → set send time (with timezone + **~1 hour delivery window** copy) → send test email (rate-limited; **costs one credit**).
- **Validation:** geocode failures, invalid tickers, unknown teams, bad Ashby URL/slug — inline errors; do not block saving unrelated modules.

### 6.2 Digest email

- Single-column HTML, **mobile-friendly**, optional **plain-text multipart** later.
- **Header:** date, optional “primary” location name, link to **manage preferences**.
- **Cards:** one per enabled module; collapsed message if module skipped due to error (“Scores temporarily unavailable”).

### 6.3 In-app

- **Last sent** summary and **next scheduled** time.
- **Preview** (rendered HTML without sending) for power users.

---

## 7. Scheduling & delivery

- **Heroku Scheduler** invokes a job **once per hour** (exact UTC minute should be documented and kept stable, e.g. `:05` past each hour).
- Each run: compute **current local date/time** per user (from profile timezone + stored send-time preference), select users whose digest is **due** in that run’s logic window, who have digest enabled, sufficient credits, and **have not already received** a successful send for that **local calendar day** (idempotency).
- **User expectation:** UI explains that real delivery may fall **within about one hour after** the chosen time (hourly batching). Implementation maps “chosen time” to the correct hourly bucket in the user’s zone (implementation detail for engineering).
- **Partial failures:** build HTML per section; failed sections become placeholders; **transport failure** — align with Reminders: **charge credit only on successful send** (or successful Mailgun acceptance, per how Reminders defines it).
- **Retries:** bounded retries on transport failure; **must not double-send** the same calendar day’s digest or **double-charge** one credit for one digest.

### 7.1 Heroku Scheduler: sending many digests in one run

**Is that bad?** Often **no**, for modest user counts: the scheduler runs one command that loops due users, builds each message, calls Mailgun sequentially or with light concurrency.

**Heroku Scheduler time budget (important):** Per Heroku’s docs, a job started by Scheduler **must not run longer than its scheduling interval** — the dyno is **terminated after about that interval**. So a job that runs **every hour** has on the order of **~1 hour** of wall-clock time, not a 30-second web request cap. (Heroku still recommends enqueueing work to a **worker** if a task routinely takes “more than a couple of minutes”; that is guidance, not the hard ceiling above.)

**Rough order of magnitude — how many emails per run?**

There is **no single fixed number** without measuring your real digest (number of modules, cache hit rate, Mailgun latency). Ballpark for **sequential** sends:

| Avg wall-clock per user (build + Mailgun) | ~Digest emails per hour-long run |
|------------------------------------------|-----------------------------------|
| ~2 s | ~1,800 |
| ~5 s | ~720 |
| ~10 s | ~360 |
| ~20 s | ~180 |

Use `N ≈ 3600 / seconds_per_user` as a planning upper bound per hourly tick, then **subtract headroom** for slow APIs, retries, and Mailgun throttling. If **due users × latency** approaches the hour wall, **enqueue** remaining users to a worker, **shard** by user id across multiple scheduler jobs, or **spread** default send times in the product so everyone is not due in the same run.

**Other limits:**

- **Mailgun** — your plan’s **rate / burst** limits (check the Mailgun dashboard for the account); backoff or throttle if you see 429s.
- **Reliability** — Heroku notes Scheduler runs are **best-effort** and can occasionally be skipped; if digests become critical, a **clock/worker** pattern is the usual upgrade path.

**Mitigations (in order of complexity):** measure `seconds_per_user` in staging; sequential Mailgun with backoff; batching; worker + queue; shard scheduled jobs by `user_id % N`.

### 7.2 Weather: city/state vs coordinates

**Open-Meteo’s weather forecast API expects latitude and longitude**, not a freeform “City, ST” string in the forecast URL.

**Practical options:**

1. **Resolve once, store lat/lon** — User picks city or ZIP; app calls a **geocoding** step (Open-Meteo’s own **Geocoding API** is free and fits the stack, or another geocoder). Store coordinates + display label; forecast calls use **lat/lon only**.
2. **ZIP** — Postcodes are not lat/lon; you still **geocode ZIP → coordinates** (same pipeline).

You do not need a separate paid “geocoding vendor” if you use **Open-Meteo Geocoding** for city/ZIP → coordinates; you **do** need that **resolution step** somewhere unless the user picks a point on a map.

### 7.3 Many API calls per user — will it feel slow?

**Yes, if you run them one after another.** Five modules × 300–800 ms each is already **~1.5–4 s** before Mailgun, and slow or retried calls stretch that fast.

**Implementation expectations:**

1. **Fetch modules in parallel** where dependencies allow (e.g. weather, stocks, sports, Ashby jobs in one **async or thread pool** batch). Wall time for the digest build approaches **~max(module latencies)** plus a small constant, not the **sum** of all calls.
2. **Tight per-request timeouts** (and your existing **partial-failure** behavior) so one stuck provider does not block the whole digest for minutes.
3. **Reuse upstream data inside the hourly job** — coalesce identical fetches (see §9.1); optional TTL cache across runs is v2+ if needed.
4. **Geocode at save time** (store lat/lon), not on every send, so the send path does not add an extra geocoder round-trip per location per day unless the user changed settings.

**Bottom line:** multi-call digests are normal; **design for parallel fetches + timeouts + caching**, then re-measure `seconds_per_user` for §7.1 throughput.

### 7.4 Due-time and idempotency — recommended approach

**Goal:** Each hour the scheduler runs, decide who is **due** for a digest in that window, and send **at most one successful digest per user per local calendar day** (in `User.time_zone`).

**Why not only “compare `last_sent_at` to today”?** It can work if you define “today” carefully in the user’s IANA timezone, but edge cases are annoying: DST boundaries, clock skew, “what if the row is missing,” and **concurrent or overlapping runs** are cleaner with an **explicit sent-for-this-local-date** fact.

**Recommended pattern:**

1. **Store a send-hour preference** (v1: **integer `0–23`** in the user’s local wall clock, simplest with hourly Heroku). Optionally store minute later if the product allows finer times and you adjust the “due” rule.
2. **Each hourly job** (runs at a fixed UTC minute, e.g. `:07`):
   - For each candidate user, compute `now_local = datetime.now(ZoneInfo(user.time_zone))`, then `local_date = now_local.date()` and `local_hour = now_local.hour`.
   - **Due:** `digest_enabled` and `credits > 0` (or whatever Reminders does) and `local_hour == user.send_hour_local` (or your chosen mapping for the “within about an hour” promise).
   - **Already sent today:** there is a row (or completed status) for `(user_id, local_date)` — **not** “last_sent_at is today” alone unless that column is guaranteed unique per day.

3. **Idempotency / double-send prevention (use the database):**
   - Table e.g. `daily_email_send` with **`UNIQUE (user_id, digest_local_date)`** where `digest_local_date` is a **date** in that user’s zone (store the date you evaluated at send time, or store UTC instant plus denormalized `local_date` for indexing).
   - **Option A — claim then send:** `INSERT … ON CONFLICT DO NOTHING RETURNING id`. If no row returned, **skip** (another worker or an earlier partial run already claimed this day). If returned, build digest → Mailgun → on **2xx**, deduct credit and set `sent_at` / `status=completed`. On failure before charge, either **delete the claim** so a later run the same local day can retry, or leave `failed` and a manual/admin retry — pick one product rule.
   - **Option B — send then insert:** only insert after Mailgun success; risk is two processes both pass “no row yet” unless you use a **transaction + lock** per user. Prefer **Option A** or `SELECT … FOR UPDATE SKIP LOCKED` on a job queue.

4. **“Most recently sent”** can remain a **UI convenience** (`ORDER BY sent_at DESC LIMIT 1`) but **authoritative “already sent for this calendar day”** should be **`EXISTS` on `(user_id, digest_local_date)`** (or equivalent), not inferring from timestamp alone.

5. **Retries same day:** If the 7:00 run fails after claiming, decide whether the **8:00** run may retry (only if claim was rolled back or status `failed` allows retry). If you never roll back, user gets no digest that day — bad; usually **allow one retry** until local midnight if send failed.

This matches §1.1 idempotency intent and stays correct across DST if `digest_local_date` is computed with `zoneinfo` every time.

---

## 8. Data & configuration (conceptual)

Exact tables are out of scope for this PRD; conceptually the app needs:

- **User digest profile** — on/off, send time (see §7); **no stored section order** (fixed in code). Timezone from **user profile** unless you later add a digest-specific override.
- **Per-module JSON or normalized rows** — e.g. weather locations, tickers, team IDs, job board configs, each respecting caps.
- **OAuth tokens** — only when Calendar ships (later phase); encrypted at rest.
- **Send log / metadata (no full body)** — e.g. `sent_at` (UTC), **`digest_local_date`** for idempotency (see §7.4), `credit_charged`, optional **per-module** flags or short error codes (not full HTML). Enough to power “last sent”, “next send”, and debugging without storing content.

---

## 9. Cost, abuse, and fairness

- **Credits:** each **successful** daily digest send deducts **one** credit from the shared hub balance (same system as Reminders / AI projects). Document UX when balance is 0 (mirror Reminders).
- **Per-user caps** on modules (above) plus **global** per-IP/API rate limits on fetch workers.
- **Caching:** see **§9.1** (v1 does not require Redis or a new cache service).
- **Test send:** **Costs one credit** (§1.1). **In-browser preview** (no email): assume **no credit** and **not persisted** unless product changes.

### 9.1 Caching — v1 vs later

**v1 (no extra infra required): “coalesce inside the hourly run”**

- In one scheduler execution, **collect all upstream keys** you need (e.g. `(league_code, dates_param)` for ESPN, `(lat,lon, day)` for Open-Meteo, ticker symbol, Ashby `companySlug`).
- **Fetch each unique key once** into an in-memory dict for that process, then **reuse** when building each user’s email.
- That already cuts duplicate calls when many users share the same league, employer board, or ticker **without** Redis, Memcached, or a cache table.

**v1 optional (still simple): HTTP-friendly behavior**

- Respect **`Cache-Control` / ETags** where providers support them (`requests` session, small conditional-get wins).
- Short **timeouts** so bad rows do not hold the whole job (§7.3).

**v2+ (if load or quotas demand it): TTL cache across runs**

- e.g. **Redis** or a **`api_cache` table** (`key`, `body`, `expires_at`) for hot keys (same Ashby board, same scoreboard slice) with TTLs per vendor (15–60 min for jobs; tighter for scores if you ever run more than hourly).

**Bottom line:** **cross-run TTL cache is not required for v1**; **per-run coalescing** should be in v1 from day one because it is cheap and matches “shared API keys + many users.”

---

## 10. Phasing (suggested)

**Product v1** = all four modules in §1.2. **Engineering** can still land in slices:

| Phase | Scope |
|-------|--------|
| **P0** | Auth-only shell (done); PRD + v1 module lock. |
| **P1** | Weather + Mailgun + Heroku hourly job + idempotency + credits + send metadata. |
| **P2** | Stocks + sports (with caps). |
| **P3** | Ashby jobs (URL/slug + optional title filter). |
| **Later** | Headlines, events, Calendar, extra job sources — not v1. |


---

## 11. Out of scope (initial)

- Unlimited locations, tickers, or feeds.
- Real-time intraday alerts (this is a **daily digest**, not a ticker).
- Social media DMs or SMS as primary channel.
- Selling aggregated user data.

---

## 12. Open questions (updated)

**Recently resolved:** ~1-hour delivery window, test send = 1 credit, fixed section order, Mailgun, **all modules fail → “nothing loaded” email + 1 credit**, **shared API keys + caps + cache (default)**, **idempotency/DST/credit timing recommendations** (§1.1, §7.1–7.2).

**Still open:**

1. **Sports — edge cases** — rare mismatches for late games / non-US TZ vs ESPN `dates=` (§4.2); leagues default **NFL/NBA/MLB/NHL** (§4.3).
2. **Plain-text multipart** — required for v1 or HTML-only first?
3. **Exact numeric caps** per module (final numbers)?
4. **Observability** — admin alerts when section failure rate spikes?
5. **Mailgun + compliance details** — exact headers and preference-link copy (implement with Mailgun + legal common practice for opted-in utility mail).

---

## 12.1 Critical to nail down before / during implementation

| Item | Why it matters |
|------|----------------|
| **“Due this hour” algorithm** | Precise rule mapping stored preference + `User.time_zone` → inclusion in a given Heroku run (must match user-facing window copy). |
| **Heroku timeout vs fan-out** | Worst-case users due in one hour; job must finish or chunk work (see §7.1). |
| **Match Reminders for credits** | Implement credit decrement on the **same event** Reminders uses after Mailgun handoff. |

---

## 13. What’s not addressed yet (checklist)

Use this as a gap list against implementation; many can stay “defaults until needed.”

| Area | Gap |
|------|-----|
| **Scheduler semantics** | Which UTC minute Heroku runs; exact “due this hour” mapping to user local time; DST edge cases (skipped/duplicate local hour). |
| **Idempotency** | Single source of truth so two hourly ticks never send two digests or charge two credits for the same local day. |
| **Credits = 0** | Exact UX copy and whether a “missed” digest is logged for the user. |
| **All modules fail** | **Resolved:** “nothing loaded” email + 1 credit (§1.1). |
| **API keys & quotas** | **Resolved:** shared hub keys + caps + cache (§1.1). |
| **Geocoding** | **Resolved:** city/ZIP → lat/lon (e.g. Open-Meteo Geocoding), store + label; see §1.1 and §7.2. |
| **Mailgun integration** | **Resolved:** reuse existing app Mailgun integration (§1.1); optional Mailgun tags for analytics later. |
| **Security** | Job/stock/location data in DB; any fields that should be encrypted. |
| **Abuse** | Max toggles on/off frequency; cap API fan-out per hourly run across all users. |
| **Worker model** | Scheduler runs a management command: timeout limits on Heroku; sync vs background job if digest generation grows slow. |
| **Modules v1 scope** | **Resolved:** weather, stocks, sports, Ashby jobs (§1.2). |
| **Internationalization** | Date formats, first day of week in weather strip; headline language N/A for v1. |
| **Accessibility** | HTML email contrast and structure; “view in browser” link optional. |
| **Support** | How you debug “my weather is wrong” without stored email body (metadata + external API logs only). |

---

## 14. References

- [`initial_idea.md`](initial_idea.md) — original script-shaped spec (sections, APIs, build order, config file).
