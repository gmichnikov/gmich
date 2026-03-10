# Travel Journal — Project Specification (v1)

## 1. Project Goal

Build a lightweight, location-aware travel journal that lives within an existing portfolio web app. Users log places they visit while traveling with minimal friction, then can revisit and enrich their entries later. The core value proposition is: **capture the moment in two taps, reflect and add detail when you have time.**

The app should be simple enough that people actually use it in the field — standing in line, walking between sites, sitting on a train. If it asks too much in the moment, no one will bother.

---

## 2. Architecture

| Component     | Technology                           | Purpose                                    |
| ------------- | ------------------------------------ | ------------------------------------------ |
| App server    | Flask on Heroku                      | API layer, business logic, serves frontend |
| Database      | Heroku Postgres (existing paid tier) | Journal entries, user data, trip metadata  |
| Photo storage | Cloudflare R2                        | Compressed photo files                     |
| Place finding | Google Places API (New)              | Location search and identification         |
| Auth          | Existing app auth                    | Already handled by the parent web app      |

---

## 3. Features — v1 (Build These)

### 3.1 Place Logging (Core Flow)

Two ways to find a place when creating a log entry:

**Browse flow (no typing required):**

- User taps "Log This Place"
- Optionally selects a category (e.g. "Food & Drink", "Shop", "Attraction", "Other") to filter results
- App grabs GPS coordinates via `navigator.geolocation.getCurrentPosition()`
- Fires a Nearby Search (New) request with `includedTypes` based on category
- Displays a short list of nearby places
- User taps the correct one

**Search flow (user types):**

- User taps a search box and types anything — a place name fragment ("greg"), a generic term ("latte", "ramen"), or a full name
- App fires a Text Search (New) request with `locationRestriction` (tight rectangle around user's coordinates)
- Displays matching results
- User taps the correct one

**In both cases:**

- Once the user selects a place, a form appears with the place name and address pre-filled in **editable** text fields, plus an empty notes field
- User can tweak the text or leave it as-is, then taps "Save"
- What gets stored is the user's content (not Google's cached data) plus the `place_id` and coordinates

### 3.2 Data Stored Per Entry

```
place_id        — Google place ID (explicitly allowed to cache)
lat             — latitude from the API response
lng             — longitude from the API response
user_name       — place name as entered/confirmed by user
user_address    — address as entered/confirmed by user
notes           — free text (can be empty, added later)
timestamp       — auto-generated at creation time
photos          — array of R2 object keys
trip_id         — foreign key to a trip (see Trip Grouping)
```

### 3.3 Photo Upload

- Client-side compression before upload using HTML Canvas API
- Resize to ~1200–1600px on the long edge
- JPEG quality 70–80%
- Typical result: 5–8MB phone photo → 150–400KB
- Upload via presigned URL directly to Cloudflare R2 (bypasses Heroku dyno — important because Heroku has 30-second request timeout and limited memory)
- Flow: browser requests presigned URL from Flask → Flask generates it via boto3/R2 → browser uploads compressed image directly to R2 → browser tells Flask the object key → Flask saves key in Postgres with the entry

### 3.4 Journal View

- Chronological list of entries, grouped by trip
- Each entry shows: place name, address, timestamp, notes preview, photo thumbnails
- Tapping an entry opens it for viewing and editing

### 3.5 Entry Editing

- Users can edit any entry after creation: change the name/address, add/edit notes, add/remove photos
- Users can delete entries
- This supports the "capture now, reflect later" workflow — create a minimal entry (just place + timestamp) in the moment, then add notes and photos back at the hotel

### 3.6 Trip Grouping

- Simple trip label (e.g. "Tokyo 2026", "Portugal Summer")
- When starting to log, user can select an existing trip or create a new one
- Entries are tagged with a trip_id
- Journal view filters/groups by trip
- Without this, multiple trips become an undifferentiated list that's hard to navigate

### 3.7 Offline / Poor Connectivity Handling

Travelers frequently have bad internet. The app must never lose an entry.

- If the Places API call fails: let the user type a place name manually, store coordinates and timestamp, skip the Google lookup. They get a slightly less polished entry but don't lose the moment.
- Photo uploads should queue in the background and retry. The user shouldn't have to wait for uploads to complete before continuing to use the app. IndexedDB or the browser Cache API can hold photos temporarily.
- If GPS fails (rare, but possible indoors): let the user type the place name and search without coordinates, or skip location entirely and add it later.
- Core principle: **the timestamp and the user's intent to log something are the most valuable things. Everything else can be refined later.**

---

## 4. Features — Not in v1 (Defer These)

| Feature                                 | Why defer                                                                                                                                                                                                                             |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Map view** (pins on a map for a trip) | High-impact polish feature but not essential for core logging. Needs a mapping library (Leaflet + OpenStreetMap tiles = free, Google Maps JS API = costs money). Build this in v2.                                                    |
| **Sharing**                             | Read-only web link with map and timeline is the most compelling format. But the core loop of logging → viewing your own journal must work first. Raises questions about privacy controls, what to include, public vs. private URLs.   |
| **Social features**                     | Comments, likes, following other travelers — way out of scope for v1.                                                                                                                                                                 |
| **Google Photos integration**           | Google deprecated key parts of the Photos Library API in March 2025. The new Picker API only lets users select and import copies — no "reference" linking. Not worth the OAuth complexity and Google app verification process for v1. |
| **Offline-first PWA**                   | Full service worker with offline place search, local database, sync queue. Important for real-world usage but significant engineering effort. v1 should handle failures gracefully but doesn't need to work fully offline.            |

---

## 5. Google Places API — What to Use and How

### 5.1 API Setup

- Google Cloud project with Places API (New) enabled
- API key with billing enabled (required even for free tier)
- No OAuth consent screen needed — Places API uses simple API key auth
- Free tier: 10,000 billable events per month per Essentials SKU

### 5.2 Cost Control

Pricing is based on **which fields you request in the field mask**, not which API you call. Nearby Search and Text Search cost the same when requesting the same fields.

The field mask for this app should only include Basic tier fields:

```
places.displayName,places.formattedAddress,places.location,places.id,places.types,places.businessStatus
```

Do NOT request Pro/Enterprise fields (rating, reviews, opening hours, phone number, website) unless needed — they trigger higher-tier billing.

Estimated cost: ~$0.005–0.007 per log entry (one API call). A 10-day trip with 5 entries/day = ~$0.25–0.35 per user per trip.

### 5.3 Nearby Search (New) — Browse Flow

Used when the user selects a category and wants to see what's nearby.

```bash
curl -X POST -d '{
  "includedTypes": ["restaurant", "cafe", "bar", "bakery", "coffee_shop", "ice_cream_shop", "meal_takeaway"],
  "locationRestriction": {
    "circle": {
      "center": {"latitude": 40.7408, "longitude": -74.3831},
      "radius": 200
    }
  }
}' \
-H "Content-Type: application/json" \
-H "X-Goog-Api-Key: YOUR_KEY" \
-H "X-Goog-FieldMask: places.displayName,places.formattedAddress,places.location,places.id,places.types,places.businessStatus" \
"https://places.googleapis.com/v1/places:searchNearby"
```

**Notes:**

- `locationRestriction` with `circle` is a hard boundary (not a bias)
- `includedTypes` filters to relevant categories — see Section 5.6 for type groupings
- Radius of 200m is good for dense urban areas; may need to widen for suburban areas
- Filter out `businessStatus` != `OPERATIONAL` client-side
- Sort results by distance from user's exact coordinates client-side (API doesn't guarantee distance-based ordering)
- If fewer than 3 results, automatically widen radius and retry

### 5.4 Text Search (New) — Typed Search Flow

Used when the user types a search term (name fragment or generic term like "latte").

```bash
curl -X POST -d '{
  "textQuery": "latte",
  "locationRestriction": {
    "rectangle": {
      "low": {"latitude": 40.7386, "longitude": -74.3862},
      "high": {"latitude": 40.7430, "longitude": -74.3800}
    }
  }
}' \
-H "Content-Type: application/json" \
-H "X-Goog-Api-Key: YOUR_KEY" \
-H "X-Goog-FieldMask: places.displayName,places.formattedAddress,places.location,places.id,places.types" \
"https://places.googleapis.com/v1/places:searchText"
```

**Notes:**

- `locationRestriction` uses a `rectangle` (Text Search doesn't support `circle` for restriction)
- To build the rectangle from user coordinates: add/subtract ~0.002 lat and ~0.003 lng for a ~400m box (adjust lng offset based on latitude)
- This handles both specific names ("gregorio") and generic terms ("latte", "ramen", "barbecue")
- Works internationally — "barbecue" near Myeongdong, Seoul correctly returns Korean BBQ places
- Use `locationRestriction` (hard boundary), NOT `locationBias` (loose bias that returns results all over)

### 5.5 APIs We Tested But Don't Want to Use

| API                        | Why not                                                                                                                                                                                                                                                                                             |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Text Search (Legacy)**   | `location` and `radius` parameters act as a loose bias, not a restriction. Searching "latte" returned places all over the tri-state area instead of nearby coffee shops. The New API with `locationRestriction` rectangle solves this.                                                              |
| **Autocomplete**           | Good for place name fragments but fails for generic terms. Searching "latte" returned zero results because no places are literally named "latte." Only useful when the user knows the actual place name, which Text Search (New) handles equally well while also supporting generic terms.          |
| **Nearby Search (Legacy)** | Works but only accepts one `type` at a time. The New API supports `includedTypes` array for multiple types in one call. Legacy API also can't be enabled for new projects anymore.                                                                                                                  |
| **Place Details**          | Not needed for this app. Both Nearby Search and Text Search return all the fields we need (name, address, coordinates, place_id) in a single call. Place Details would only be needed for extra info like phone numbers, reviews, or full opening hours, which aren't relevant for a journal entry. |

### 5.6 Category Type Groupings

For the category filter buttons in the browse flow, these `includedTypes` groupings cover the main use cases:

**Food & Drink:**

```json
[
  "restaurant",
  "cafe",
  "bar",
  "bakery",
  "coffee_shop",
  "ice_cream_shop",
  "meal_takeaway"
]
```

This catches the broad categories. Subtypes like `ramen_restaurant`, `korean_restaurant`, etc. are automatically included because those places also have `restaurant` in their types.

**Shopping:**

```json
[
  "store",
  "shopping_mall",
  "book_store",
  "clothing_store",
  "grocery_store",
  "convenience_store"
]
```

**Attractions:**

```json
[
  "tourist_attraction",
  "museum",
  "art_gallery",
  "historical_landmark",
  "park",
  "amusement_park",
  "zoo",
  "aquarium"
]
```

**Other / All:**
No type filter — just use Nearby Search without `includedTypes` to return everything nearby. Filter out unhelpful types client-side (e.g. `route`, `locality`, `political`, `real_estate_agency`).

The full list of supported types is at: https://developers.google.com/maps/documentation/places/web-service/place-types

### 5.7 Google Terms Compliance

- **Allowed to store:** `place_id` (indefinitely, refresh if >12 months old), lat/lng coordinates
- **NOT allowed to store/cache:** place names, addresses, reviews, photos, or any other "Google Maps Content" from the API response
- **Our approach:** The user selects a place from API results, which pre-fills an editable form. What gets saved to the database is the user's own text content (from the editable fields), not a cached copy of Google's data. The `place_id` and coordinates are stored as allowed.
- **Attribution:** When displaying Places API results (the selection list), you must show the Google logo and any third-party attributions. This applies to the search/selection UI, not to the saved journal entries (which are user content).
- **Display requirement:** Places API results shown on a map must use a Google Map. If showing results without a map (e.g. as a list), include the Google logo.

---

## 6. Cloudflare R2 — Photo Storage

### 6.1 Why R2

- **Free tier:** 10GB storage, 1M upload operations, 10M download operations per month
- **Paid tier:** $0.015/GB/month
- **Zero egress fees:** When users view their journals or share them, serving photos costs nothing. This is the key advantage over AWS S3 ($0.09/GB egress) or Google Cloud Storage.
- **S3-compatible API:** Use `boto3` in Python (same library as AWS S3, just point at R2's endpoint)

### 6.2 Cost Estimate

With compressed photos averaging 300KB:

- 10GB free tier ≈ 33,000 photos before paying anything
- A typical trip (10 days, 5 places/day, 2 photos/place) = 100 photos ≈ 30MB
- 10GB free ≈ 330 trips before spending a dollar
- Beyond free tier, each trip costs ~$0.00045/month in storage

### 6.3 Upload Pattern

Photos should **not** flow through the Heroku dyno (30-second timeout, limited memory). Instead:

1. Browser compresses the image client-side
2. Browser requests a presigned upload URL from Flask
3. Flask generates a presigned URL via boto3 pointing at R2
4. Browser uploads the compressed image directly to R2
5. Browser sends the R2 object key to Flask
6. Flask saves the key in Postgres with the journal entry

### 6.4 Heroku Note

Heroku's filesystem is ephemeral — files written to disk disappear on dyno restart. Never store photos locally, even temporarily. Everything goes to R2.

---

## 7. Phone GPS Accuracy

- Modern smartphones in urban environments: typically **5–15 meters** accuracy
- With Wi-Fi assistance: can be even better
- In dense urban canyons (Manhattan, Myeongdong): signal reflections can degrade to 15–20m, but Wi-Fi helps compensate
- Newer phones with multi-frequency GNSS: can achieve **1.5–5 meters** in open sky
- **Practical implication for this app:** GPS alone won't tell you which specific shop you're in, but it will get you to the right block. Combined with a ~400m search box, the correct place will be in the result list. The user just needs to tap it.
- GPS cannot distinguish floors in a multi-story building — edge case for malls
- If GPS fails entirely (indoors, no signal): fall back to manual text entry

---

## 8. Database Schema (Sketch)

```sql
CREATE TABLE trips (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(255) NOT NULL,        -- "Tokyo 2026"
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE entries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    trip_id INTEGER REFERENCES trips(id),
    place_id VARCHAR(255),              -- Google place ID (allowed to cache)
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    user_name VARCHAR(255),             -- user-entered place name
    user_address TEXT,                  -- user-entered address
    notes TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE entry_photos (
    id SERIAL PRIMARY KEY,
    entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
    r2_key VARCHAR(255) NOT NULL,       -- Cloudflare R2 object key
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 9. Open Questions

### 9.1 Default Search Box Size

We tested a ~200m × 170m box in Myeongdong (Seoul) and got 4 clean results. A ~250m box in Chatham, NJ returned 6 results. But the user might not be standing exactly at the place (walking to it, already left, etc.). A ~400m box is probably safer as a default, with client-side distance sorting to keep the closest results on top. Could also start tight and widen automatically if fewer than 3 results come back. Needs real-world testing.

### 9.2 Category Buttons vs. No Categories

We discussed having category buttons (Food & Drink, Shop, Attraction, Other) to filter the Nearby Search. This produces much cleaner results than an unfiltered search. But it adds one extra tap to the flow. An alternative is to always show an unfiltered nearby list with smart client-side sorting/filtering (deprioritize types like `real_estate_agency`, sort by `userRatingCount` as a proxy for "is this a place someone would visit"). Needs UX testing.

### 9.3 Capture vs. Reflection UX

We agreed the creation flow should be minimal (two taps: category → place) and editing should be richer (add notes, photos). But we haven't designed the actual screens. Key questions:

- Does the "Save" screen after selecting a place show a notes field and photo uploader, or just save immediately and let the user add those later from the journal view?
- How does the user get back to an entry to add notes/photos? Notification reminder? Just open the journal?

### 9.4 Map Library for Future Map View

When we build the map view (v2), we need to choose between:

- **Leaflet + OpenStreetMap tiles:** Free, open source, no API key needed for tiles
- **Google Maps JavaScript API:** Costs money, but required if we want to display Places API results on a map (per Google's terms, Places results on a map must use a Google Map)
- Since the journal view displays user content (not live Places API results), Leaflet should be fine for the map view. Only the place-selection UI during logging would need Google Maps if showing results on a map.

### 9.5 Longitude Offset for Bounding Box

One degree of longitude varies by latitude (111km at equator, ~88km at 37°N Seoul, ~85km at 40°N NJ, ~0 at poles). The code that builds the `locationRestriction` rectangle from the user's coordinates needs to account for this. Formula: `lng_offset = desired_meters / (111320 * cos(latitude_in_radians))`. Not hard to implement, just needs to be done correctly.
