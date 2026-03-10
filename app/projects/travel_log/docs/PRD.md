# Travel Log — Product Requirements (v1)

## Overview

A lightweight, location-aware travel journal within an existing portfolio web app. Users log places they visit while traveling with minimal friction, then revisit and enrich entries later. Core value: **capture the moment quickly, reflect and add detail when you have time.**

The app should be simple enough to use in the field — standing in line, walking between sites, sitting on a train. If it asks too much in the moment, no one will bother.

## Architecture (High Level)

| Component     | Technology              | Purpose                                   |
| ------------- | ----------------------- | ----------------------------------------- |
| App server    | Flask on Heroku         | API, business logic, serves frontend      |
| Database      | Heroku Postgres         | Collections, entries, user data           |
| Photo storage | Cloudflare R2           | Compressed photos (presigned upload)      |
| Place finding | Google Places API (New) | Nearby Search + Text Search               |
| Auth          | Existing app auth       | Handled by parent web app                 |

See `INITIAL_SPEC.md` for technical details (API usage, R2 flow, cost estimates).

---

## Collections

Collections group entries (e.g. "Tokyo 2026", "Portugal Summer"). Entries always belong to a collection.

- Users must have **at least one collection** before they can log places
- New users are prompted to create a collection on first visit
- When starting to log, the **default collection** is the one used for the most recently created or edited entry
- A **subtle control** to change collection is available while logging (e.g. during place selection or on the creation form)
- Users can **rename** and **delete** collections
- **Delete collection:** Deletes the collection and all its entries. Confirmation dialog must show how many entries will be deleted (e.g. "Are you sure? This will permanently delete 12 entries.")
- Collections are ordered by **last modified** (when an entry was added/edited, or the collection itself was edited)

---

## Place Logging (Core Flow)

### Prerequisites

User must have at least one collection. Default collection = most recently used (by create/edit).

### Two Ways to Find a Place

**Browse flow (no typing):**

- User taps "Log This Place"
- App gets GPS via `navigator.geolocation.getCurrentPosition()`
- Fires Nearby Search with a **narrow radius first** (~200m); if fewer than 3 results, widen and retry
- Displays list of nearby places
- **Filter out** places with `businessStatus` != `OPERATIONAL` (client-side)
- Default: unfiltered. When many results, user can **filter by category** (Food & Drink, Shop, Attraction, Other) or **type to search**
- User taps the correct place

**Search flow (user types):**

- User taps search box and types: place name fragment, generic term ("latte", "ramen"), or full name
- App fires Text Search with `locationRestriction` (rectangle around user's coordinates)
- Uses narrow box first; widens if too few results
- Displays matching results
- **Filter out** places with `businessStatus` != `OPERATIONAL` (request `places.businessStatus` in field mask; filter client-side)
- User taps the correct place

**Both flows (client-side):**

- Sort results by distance from user's exact coordinates (API doesn't guarantee order)

### Creation Form

- **Minimal for v1:** Place name, address, and visited_date (name/address pre-filled from selection; visited_date defaults from lat/lng or today — all editable so users can log places from days ago)
- User taps "Save"
- **Notes and photos are added via Edit**, not at creation — keeps the flow fast (avoids photo upload delay, works on slow connections, lowers cognitive load)

### What Gets Stored

- `place_id` (Google; allowed to cache)
- `lat`, `lng` (from API or null when lookup fails)
- `user_name`, `user_address` (user's text — we never cache Google's names/addresses)
- `notes` (optional; usually added later via Edit)
- `visited_date` (date when user was there; default from lat/lng timezone when available, otherwise creation date; editable)
- `created_at`, `updated_at` (system timestamps)
- Photos: R2 object keys (added in Edit)

### Fallbacks (Error Recovery)

When things fail, the app must not lose the user's intent to log something:

- **Places API fails:** Allow user to type place name (and optionally address) so they can save something. No `place_id`, coordinates null
- **GPS fails:** Allow name-only entry; no coordinates
- **Offline:** v1 handles failures minimally — retry on reconnect, basic form entry when API unavailable. No IndexedDB/offline queue

**Out of scope for v1:** A dedicated "add place manually" flow for places not in Google. Focus on the Google-backed flow first.

---

## Journal View

### Collections Page

- Lists all collections
- Ordered by **last modified** (entry add/edit or collection rename)
- Each collection shows preview (e.g. entry count, most recent entry)
- Tap a collection → collection detail page

### Collection Detail Page

- Lists all entries in that collection
- Ordered by **most recent activity** (`updated_at`; set on create and on every edit)
- Each entry shows: place name, address, visited date, notes preview, photo thumbnails
- Tap an entry → view/edit

---

## Entry Editing

- Edit: name, address, notes, visited date
- Add/remove photos
- Delete entry
- **Photos:** Save immediately when a photo is uploaded (don't require user to hit Save again — avoids data loss)

---

## Photo Upload

- Client-side compression (HTML Canvas): resize to ~1200–1600px long edge, JPEG 70–80%
- Upload via presigned URL directly to R2 (bypasses Heroku timeout)
- Flow: browser requests presigned URL from Flask → uploads to R2 → sends key to Flask → Flask saves with entry
- No photos at creation; add in Edit

---

## Google Places API — Key Constraints

- Store only: `place_id`, lat/lng. Never cache place names, addresses, or other "Google Maps Content"
- User selects from results → we pre-fill editable form → user's text is what we save
- When displaying Places API results (the selection list), show Google logo/attribution
- Use Basic tier fields only in field mask (no rating, reviews, hours — those cost more)
- Include `places.businessStatus` in field mask for both Browse and Search (needed to filter out closed/temporarily closed places)

---

## Category Filtering (Reference)

When the user filters by category in the browse flow, use these `includedTypes` groupings. See [Places API place types](https://developers.google.com/maps/documentation/places/web-service/place-types) for the full list.

**Food & Drink:** `restaurant`, `cafe`, `bar`, `bakery`, `coffee_shop`, `ice_cream_shop`, `meal_takeaway`

**Shopping:** `store`, `shopping_mall`, `book_store`, `clothing_store`, `grocery_store`, `convenience_store`

**Attractions:** `tourist_attraction`, `museum`, `art_gallery`, `historical_landmark`, `park`, `amusement_park`, `zoo`, `aquarium`

**Other / All:** No `includedTypes` filter — return everything nearby. Filter out unhelpful types client-side (e.g. `route`, `locality`, `political`, `real_estate_agency`).

---

## Data Model (Conceptual)

**Collections**

- `id`, `user_id`, `name`, `created_at`, `updated_at`

**Entries**

- `id`, `user_id`, `collection_id`, `place_id` (nullable), `lat`, `lng` (nullable)
- `user_name`, `user_address`, `notes`
- `visited_date` (date only; default from lat/lng timezone when available, otherwise creation date)
- `created_at`, `updated_at`

**Entry Photos**

- `id`, `entry_id`, `r2_key`, `sort_order`, `created_at`

---

## Out of Scope (v1)

- Map view (pins on a map)
- Sharing (read-only links)
- Social features
- Google Photos integration
- Full offline-first PWA (service worker, sync queue)
- Dedicated "add place manually" flow (for places not in Google)
