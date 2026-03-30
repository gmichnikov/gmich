# Sports Scores — Product Requirements Document

## Problem

Sports score pages on major sites (ESPN, etc.) are slow to load because of ads, trackers, heavy layouts, video modules, and unrelated content. Users who only want **current scores** wait too long for the signal in the noise.

## Goal

A **minimal, fast** page (or set of pages) that shows **live or near-live sporting event scores** with as little overhead as possible—optimized for time-to-readable-scores, not for engagement or ad inventory.

## Proposed direction

Use **ESPN’s scoreboard / event data** and render a **thin Flask UI** with prefixed CSS. **No login** for viewing; same data for everyone.

**Non-goals for v1** (unless explicitly pulled in later): news, articles, video, betting integrations, deep stats, fantasy, favorites, or account features; **extra ESPN calls** to backfill days with no stored games (empty days in the UI are fine; targeted fetches can wait).

---

## Existing ESPN integration in this repo

Reuse the same unofficial API pattern as **`ESPNClient`** in:

`app/projects/sports_schedule_admin/core/espn_client.py`

- **Base URL**: `https://site.api.espn.com/apis/site/v2/sports`
- **Scoreboard**: `GET .../{sport}/{league}/scoreboard` with `dates=YYYYMMDD` (see `fetch_schedule`).
- **Big-four league codes** in `LEAGUE_MAP`: **NFL**, **NBA**, **MLB**, **NHL** (paths: `football/nfl`, `basketball/nba`, `baseball/mlb`, `hockey/nhl`).

Sports Scores can import or factor shared helpers from that module rather than re-inventing URLs. Parsing for **live scores** may be lighter than the admin client’s schedule-to-DoltHub pipeline—implement the minimum needed for display.

---

## Fetch strategy (decided)

- **When to fetch**: On **user page load** (and manual browser refresh)—**no** periodic background job for v1.
- **Throttle**: At most **one upstream fetch per sport per minute** (minimum interval between ESPN calls for that sport). Enforced using the **existing app database**.
- **Exactly one upstream call per sport per refresh** (when the throttle allows a fetch): **v1** always uses a **single** `scoreboard` request per sport—no loops, no second request to fill in another calendar day.
- **Gaps are OK in v1**: If the DB has no games for a day in the “last 2–3 days” window, show that day empty (or omit it). **Do not** add more ESPN calls in v1 to backfill missing days; that can be a **later** enhancement.
- **Across sports**: Visiting NFL then NBA close together is fine—each sport has its own throttle. Hitting the same sport repeatedly within a minute should **not** call ESPN again.
- **Concurrency**: **Simplest approach**—no special locking for v1; acceptable for single-user / low traffic. Revisit if multiple workers cause duplicate upstream calls.

---

## Database as source of truth for the multi-day UI

- We **persist** scoreboard data in the **app database** (normalized game rows, or equivalent). The page that shows the **last 2–3 days** reads from **our DB**—still **one ESPN call** when we fetch, not one call per day.
- Each **successful** ESPN fetch **merges / upserts** into that store (by event/game id from the API). Over time the DB accumulates history; **v1** does not require a complete grid for every day.
- When the throttle **skips** fetching, we still render from **whatever we already have stored** for that sport (may be slightly stale; that’s acceptable within the 1-minute rule).

**Last fetch time per sport** is only for **throttling** the upstream call. **Stored games** are what we **display** whenever we skip a fetch or when building the multi-day list.

---

## What to store in the database (summary)

| Stored data | Purpose |
|-------------|--------|
| **Last fetch time per sport** | Enforce **≤ 1 ESPN call per sport per minute**. |
| **Game/event rows** (or durable merge of API payloads) | **Display** recent games (e.g. **2–3 day** window) from DB **without** extra ESPN requests. Updated when a fetch succeeds. |

---

## One sport at a time vs all sports on one page

**Recommendation for v1: one sport per screen, with clear navigation between sports.**

- ESPN-style APIs are **per league**: one request per sport for a given `dates` parameter. A combined “all sports” view would still require **up to four upstream calls** when cache is cold.
- **UI**: **Separate routes or tabs per sport** (NFL, NBA, MLB, NHL). Optional **date filter** on the multi-day list reads **only from the DB** (does not add ESPN calls). Only the **active** sport’s data loads on first paint; switching sport may trigger a fetch for that sport (subject to the 1-minute rule).
- **Date range displayed**: Show games from roughly the **past 2–3 days** from **database** rows for that sport (filtered by stored kickoff or game date). Days with no stored games appear empty in v1.

---

## Dates, “today,” and timezones (decided)

- **Single scoreboard request**: The lone `dates=` value for that request defaults to **UTC “today”** (unless you later add a control that changes only that parameter—still **one** request per fetch). Optional **browser-supplied timezone** (query param or cookie from JS) may adjust which calendar day counts as “today” for that default; **if missing or invalid, fall back to UTC**.
- **Game dates and kickoff instants** in data: Come from the **API** (source of truth).
- **Display of game times**: Show in **US Eastern (ET)** for consistency across the big four.

---

## Rendering: server vs client (decided)

- **Server-rendered**: Flask builds HTML on each request; user **refreshes the browser** to see newer scores.
- **Client polling**: JavaScript calls **our** JSON endpoint on an interval so scores update without a full reload.

**v1**: Server-rendered first. Client polling can be added later.

---

## Failure UX (decided)

**Whatever is simplest**: show last good cached scores if available, a clear message if nothing is available, and a normal browser refresh to retry.

---

## Decisions log (answers to PRD questions)

| # | Topic | Decision |
|---|--------|----------|
| 1 | Legal / ESPN use | Proceed; treat as acceptable for personal use. Revisit if usage or exposure changes. See existing **`ESPNClient`** usage in-repo. |
| 2 | Rate limits | **≤ 1 upstream fetch per sport per minute**; **stored games in DB** power the UI when we skip fetch; **last fetch time** only gates the upstream call. |
| 3 | Geography | **Identical** data worldwide for v1. |
| 4 | Sports | **NFL, NBA, MLB, NHL** first. |
| 5 | UI | **Separate pages or tabs per sport**; **by date**; ~**last 2–3 days** of games; favorites later. |
| 6 | Freshness vs fetch | **At most once per minute per sport** from ESPN for now. |
| 7 | Cache / throttle store | **Database**: last fetch time per sport + **persisted game rows** (or equivalent) so multi-day views and throttled loads read from DB (see **Database as source of truth**). |
| 8 | Client vs server updates | Server-rendered first (simplest). |
| 9 | Failure UX | Simplest acceptable behavior. |
| 10 | Traffic | Single user for now. |
| 11 | Hosting | No infra changes. |
| 12 | Auth | No login; same data for everyone. |
| 13 | Database | Throttle + cache columns/tables as above; exact schema at implementation. |

---

## Success metrics (draft)

- Time from navigation to **first meaningful paint** of scores (target TBD).
- Subjective: **fewer round-trips** than loading the full ESPN scoreboard page.
- Upstream calls stay within the **1/minute per sport** rule under normal use.

---

## Implementation notes (defer until build)

- **JSON → UI**: Document field paths used for scores once implemented (ESPN payloads can change).

---

## Document status

**v1 scope is set**: one ESPN `scoreboard` call per sport when fetching; persist games in DB; throttle at 1/min per sport; multi-day list from DB with empty days OK; no backfill fetches; server-rendered first; UTC default for `dates=` with optional browser tz; times shown in ET. **Next step**: models + migrations, then implementation.
