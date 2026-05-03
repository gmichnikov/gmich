# Distance-Based Filtering for Sports Schedule App

## Problem

A Python Flask web application displays sports event schedules pulled from a **DoltHub** database (`combined-schedule` table) via read-only HTTP queries. Each event record stores a **city and state** as its location (`home_city`, `home_state`). There is currently no way for users to filter events by proximity — a user interested in events near them has no way to narrow results by distance.

The goal is to add a filter to the UI where a user can enter a **zip code** and a **radius** (e.g. 25, 50, 100 miles) and see only events within that distance.

---

## Constraints

- Hosted on **Heroku**, which has an ephemeral filesystem — any files written at runtime are wiped on dyno restart.
- Event data lives in **DoltHub** (`combined-schedule`), which is queried read-only over HTTP. We cannot add columns to that table or do distance filtering inside that query.
- App's **Heroku Postgres** only stores saved queries, digest settings, and user preferences — not event rows.
- Event locations are stored as **city/state strings** (`home_city`, `home_state`), not coordinates.
- The solution should avoid large external data uploads or complex infrastructure changes.

---

## Architecture Reality vs. Original Doc

The original draft of this doc assumed events lived in Heroku Postgres and proposed:
- Backfilling lat/lon directly onto the events table
- Using the Postgres `earthdistance` extension for DB-side distance filtering

**Neither of those applies.** Because events come from DoltHub and are fetched into Python, distance filtering must happen **in Python after the DoltHub fetch**, using coordinates looked up from a local Postgres cache.

---

## Proposed Solution Overview

The solution has three parts:

1. **Convert the user's zip code to coordinates** using a lookup table stored in Heroku Postgres
2. **Geocode event city/state to coordinates** on demand, caching results in Heroku Postgres
3. **Filter events by distance in Python** after fetching from DoltHub

---

## Part 1: Zip Code → Coordinates

### Approach: One-Time Import into Postgres

Load the free [simplemaps US zip code dataset](https://simplemaps.com/data/us-zips) (~33,000 rows, ~3MB CSV) into a dedicated `ss_zip_codes` table in Heroku Postgres as a one-time import. At query time, look up the user's zip to retrieve lat/lon instantly with no external API call.

**Storage impact:** The table uses roughly 5–8MB. Even on the smallest Heroku Postgres plan (Essential-0, 1GB limit) this is under 1% of available space. No cost or storage concern.

**Columns needed:** `zip TEXT PRIMARY KEY, city TEXT, state TEXT, lat FLOAT, lon FLOAT`

**Tech involved:** Heroku Postgres, simplemaps free dataset, a one-time CLI import command.

### Why Not Nominatim for Zip Lookup?

Nominatim can geocode zip codes but is an external HTTP call per request, adds latency, and is less reliable for raw US zips than a local dataset. The Postgres lookup is instant and has no external dependency.

### Why Not pgeocode?

`pgeocode` downloads and caches its data to the local filesystem on first use. Because Heroku's filesystem is ephemeral, this cache would be wiped on every dyno restart.

---

## Part 2: Geocoding Event City/State

### Approach: On-Demand Cache in Postgres

Add a `ss_geocode_cache` table: `(city TEXT, state TEXT) → (lat FLOAT, lon FLOAT)`. After fetching events from DoltHub, check each unique `(home_city, home_state)` pair against this cache. If a pair is missing, call **Nominatim** (geopy) and store the result. Future requests for the same city/state hit the cache instantly.

This is lazy-population: the cache warms up over time as different city/state pairs are encountered. Since the number of distinct venues in sports schedules is finite and relatively small, it will fill up quickly and stabilize.

**Nominatim usage note:** Free service, 1 request/second rate limit. For a small set of distinct cities this is fine.

**Tech involved:** `geopy` Python library, Nominatim geocoding API (free, no API key required), Flask-Migrate for the schema change.

---

## Part 3: Filtering Events by Distance in Python

Once the user's coordinates and event coordinates are both available, filter in Python using **geopy's** `geodesic` distance function. This is applied after the DoltHub fetch.

### Optimization: State Pre-Filter

Before sending the DoltHub query, convert the user's zip to lat/lon and determine which US states fall within (or near) the requested radius. Pass those states as an additional `home_state IN (...)` filter in the DoltHub SQL. This reduces the number of rows returned from DoltHub before Python-side filtering, keeping the approach fast.

For example, a 50-mile radius around a zip in northern Virginia would pre-filter to VA, MD, and DC — ruling out all other states before the DoltHub fetch.

**Tech involved:** `geopy` Python library, state boundary approximation (bounding box or list of nearby states derived from the zip table).

---

## End-to-End Flow

When a user submits a zip code + radius filter:

1. Look up zip in `ss_zip_codes` → user lat/lon
2. Determine candidate states within radius (bounding box approximation using the zip table)
3. Add `home_state IN (...)` pre-filter to the DoltHub SQL query
4. Fetch matching events from DoltHub
5. For each unique `(home_city, home_state)` in results, get coordinates from `ss_geocode_cache` (geocode and cache if missing)
6. Filter events in Python: keep only those where `geodesic(user_coords, event_coords).miles <= radius`
7. Return filtered results to the UI

---

## Summary Table

| Step | Action | Where |
| ---- | ------ | ------ |
| Schema change | Add `ss_zip_codes` and `ss_geocode_cache` tables | Heroku Postgres (Flask-Migrate) |
| One-time import | Load simplemaps zip CSV into `ss_zip_codes` | CLI command (`flask ss-import-zips`) |
| Zip lookup | Look up user's zip → lat/lon | Python (routes.py) |
| State pre-filter | Narrow DoltHub query to nearby states | query_builder.py |
| City geocoding | On-demand geocode city/state + cache | Python (new geocode helper) |
| Distance filter | Filter fetched events by geodesic distance | Python (routes.py or filter helper) |
| UI | Zip input + radius dropdown in filter form | Jinja template + JS |

No external data uploads beyond a one-time small CSV import. No API keys. No additional Heroku add-ons. No filesystem dependencies.
