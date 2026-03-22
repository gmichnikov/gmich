# Travel Log — Implementation Plan

This plan follows the PRD and breaks implementation into small, testable phases. Each phase ends with manual testing steps before moving on.

---

## Relevant Files

- `app/projects/travel_log/__init__.py` — package marker
- `app/projects/travel_log/models.py` — Collection, Entry, EntryPhoto models
- `app/projects/travel_log/routes.py` — blueprint and all routes
- `app/projects/travel_log/services/places.py` — Google Places API proxy (server-side)
- `scripts/tlog_backfill_place_details.py` — one-off backfill of place-detail columns via Place Details (New) using `place_id`
- `app/projects/travel_log/services/r2.py` — R2 presigned URL generation
- `app/projects/travel_log/templates/travel_log/` — all templates
- `app/projects/travel_log/static/` — CSS (`tlog.css`), JS for place logging and photo upload
- `app/__init__.py` — blueprint registration, model imports
- `app/projects/registry.py` — project registry entry

---

## Environment & Dependencies

**New env vars needed:**

- `GOOGLE_PLACES_API_KEY` — for Places API (New)
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` — for Cloudflare R2

**New Python deps:** `boto3`, `timezonefinder` (for lat/lng → timezone)

**Implementation notes:**

- Places API is proxied through Flask (keeps API key server-side). Browser calls `/api/places/*`.
- For JSON API routes (`/api/places/*`, `/api/photos/*`): pass CSRF token in header (e.g. `X-CSRFToken` from meta tag).
- R2: private bucket; presigned URLs for upload and download.

---

## Cloudflare R2 Setup (Prerequisite for Phase 6)

**Why R2 over S3?** R2 has zero egress fees — when users view their photos, there's no per-GB charge. S3 charges ~$0.09/GB for downloads, which adds up for a photo-heavy journal. Both use the same boto3/presigned URL pattern. R2 is recommended for this use case. (S3 is simpler only if you already have an AWS account and expect minimal traffic.)

**Setup steps:**

- [ ] Create Cloudflare account at https://dash.cloudflare.com/sign-up
- [ ] In left sidebar: **R2 Object Storage** → **Overview**
- [ ] Click **Create bucket** — name it (e.g. `gmich-travel-log`)
- [ ] Go to **R2** → **Manage R2 API Tokens** → **Create API token**
  - [ ] Permissions: Object Read & Write
  - [ ] Specify bucket or allow all (for single-bucket app, bucket-scoped is fine)
  - [ ] Copy: Access Key ID, Secret Access Key
- [ ] Account ID: find in R2 Overview or right sidebar of any R2 page
- [ ] Add to `.env`:
  ```
  R2_ACCOUNT_ID=your_account_id
  R2_ACCESS_KEY_ID=your_access_key
  R2_SECRET_ACCESS_KEY=your_secret_key
  R2_BUCKET_NAME=gmich-travel-log
  ```
- [ ] R2 endpoint for boto3: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`

**CORS (required for browser photo uploads):**  
The browser PUTs directly to the presigned R2 URL (cloudflarestorage.com). That is a cross-origin request, so the bucket must have CORS configured. If you see "Failed to fetch" or "Upload to storage failed" when adding photos, add CORS:

1. Cloudflare Dashboard → **R2** → select your bucket → **Settings**
2. Find **CORS policy** and add:

```json
[
  {
    "AllowedOrigins": ["http://127.0.0.1:5518", "http://localhost:5518"],
    "AllowedMethods": ["PUT", "GET", "HEAD"],
    "AllowedHeaders": ["Content-Type", "Content-Length"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

3. For production, add your real app origins (e.g. `https://yoursite.com`).

**Manual verification:**

- [ ] Use boto3 in Python shell to list bucket (or upload a test file)
- [ ] Confirm credentials work before starting Phase 6
- [ ] Add CORS policy if testing photo upload from browser

---

## Phase 1: Database Models & Collections CRUD ✅

### 1.1 Database Models

- [x] Create `models.py` with:
  - [x] `Collection` model
    - [x] `id`, `user_id` (FK to User), `name` (VARCHAR 255), `created_at`, `updated_at`
    - [x] `last_modified` — denormalized; updated when entry added/edited or collection renamed (for ordering)
    - [x] Relationship to Entry
    - [x] `__repr__`
  - [x] `Entry` model
    - [x] `id`, `user_id`, `collection_id` (FK, nullable=False)
    - [x] `place_id` (VARCHAR 255, nullable), `lat` (Float, nullable), `lng` (Float, nullable)
    - [x] `user_name` (VARCHAR 255, nullable=False), `user_address` (Text, nullable), `notes` (Text, nullable)
    - [x] `visited_date` (Date, nullable=False) — default from lat/lng timezone or creation date
    - [x] `created_at`, `updated_at`
    - [x] Relationship to Collection, EntryPhoto
    - [x] `__repr__`
  - [x] `EntryPhoto` model
    - [x] `id`, `entry_id` (FK, ON DELETE CASCADE), `r2_key` (VARCHAR 255), `sort_order` (Int, default 0), `created_at`
    - [x] `__repr__`
- [x] Add index on `Entry(collection_id)`, `Entry(user_id)`, `Collection(user_id)`, `Collection(last_modified)`
- [x] Import models in `app/__init__.py`

**Manual Testing 1.1:**

- [x] Run `flask db migrate -m "Add travel log models"`
- [x] Review migration — check columns, FKs, CASCADE on entry_photos
- [x] Run `flask db upgrade`
- [x] Verify tables exist with correct schema

---

### 1.2 Collections List & First-Time Flow

- [x] Update `GET /travel-log/` (index) route:
  - [x] If user has **zero collections** → redirect to "create first collection" flow (or render collections page with prominent empty state)
  - [x] Otherwise: query user's collections ordered by `last_modified DESC`
  - [x] For each collection: entry count, most recent entry preview (if any)
  - [x] Pass to template
- [x] Create `templates/travel_log/index.html` (Collections page)
  - [x] Page title "Travel Log"
  - [x] List of collections (name, entry count, last modified / preview)
  - [x] Empty state: "Create your first collection to start logging places"
  - [x] "New Collection" button
  - [x] "Log Place" button (disabled or hidden if no collections?)
  - [x] Use `tlog-` CSS prefix

**Manual Testing 1.2:**

- [x] Navigate to `/travel-log/` as new user (no collections) — see empty state
- [x] Verify login required

---

### 1.3 Create Collection

- [x] Implement `GET /travel-log/collections/new` — render create form
- [x] Implement `POST /travel-log/collections/create`
  - [x] Validate name not empty
  - [x] Create Collection, set `last_modified = created_at`
  - [x] Flash success, redirect to index (or to Log Place flow?)
- [x] Create `templates/travel_log/collections/new.html`
  - [x] Name input, Submit, Cancel
  - [x] `tlog-` prefix

**Manual Testing 1.3:**

- [x] Create a collection — verify it appears on index
- [x] Create second collection — verify both listed, ordered by last_modified

---

### 1.4 Rename & Delete Collection

- [x] Implement `GET /travel-log/collections/<id>/edit` — render rename form
- [x] Implement `POST /travel-log/collections/<id>/update` — update name, set `last_modified`, redirect
- [x] Implement `POST /travel-log/collections/<id>/delete`
  - [x] Verify ownership
  - [x] Count entries that will be deleted
  - [x] Delete collection (cascade deletes entries and entry_photos)
  - [x] Flash success, redirect to index
- [x] Create `templates/travel_log/collections/edit.html` (rename form)
- [x] Add delete button with **confirmation dialog**: "Are you sure? This will permanently delete N entries." (N = actual count)

**Manual Testing 1.4:**

- [x] Rename a collection — verify change persists
- [x] Delete empty collection — verify removed
- [x] Create collection with entries (Phase 2), then delete — verify confirmation shows entry count, and entries are gone after confirm

---

## Phase 2: Journal View (Collections & Entries List) ✅

### 2.1 Collection Detail Page

- [x] Implement `GET /travel-log/collections/<id>` route
  - [x] Verify ownership (404 if not)
  - [x] Query entries for this collection, ordered by `updated_at DESC`
  - [x] **updated_at** must be set on entry creation and updated on entry edit and photo add/remove (for correct ordering)
  - [x] Pass collection and entries to template
- [x] Create `templates/travel_log/collections/show.html`
  - [x] Collection name in header
  - [x] List of entries: place name, address, visited_date, notes preview (truncated), photo count/thumbnails
  - [x] Empty state: "No entries yet. Log your first place."
  - [x] "Log Place" button
  - [x] "Back to Collections" link
  - [x] `tlog-` prefix

**Manual Testing 2.1:**

- [x] Click collection from index — collection detail loads
- [x] Empty collection shows empty state
- [x] Verify 404 for other user's collection

---

### 2.2 Entry Placeholder (Create Without Places API)

- [x] For testing Phase 2, add a minimal "Create Test Entry" route or seed script
  - [x] OR: skip until Phase 4; Phase 2 can be tested with empty list and manual DB insert
- [x] Entry display: place name, address, visited_date, notes preview, "No photos" or photo thumbnails
- [x] Tap entry → goes to edit page (Phase 5)

**Manual Testing 2.2:**

- [x] Insert test entry via Flask shell or minimal form — verify it displays on collection detail
- [x] Verify ordering by updated_at

---

## Phase 3: Google Places API Service ✅

### 3.1 Config & Places Service

- [x] Add `GOOGLE_PLACES_API_KEY` to `config.py` (from env)
- [x] Create `app/projects/travel_log/services/` directory (with `__init__.py`)
- [x] Create `app/projects/travel_log/services/places.py` (see INITIAL_SPEC 5.3, 5.4, 5.6)
  - [x] Function `search_nearby(lat, lng, radius_m=200, included_types=None)`
    - [x] POST to `https://places.googleapis.com/v1/places:searchNearby`
    - [x] Field mask: `places.displayName,places.formattedAddress,places.location,places.id,places.types,places.businessStatus`
    - [x] `locationRestriction.circle` with center and radius
    - [x] If `included_types`: pass as `includedTypes` array; if "other" or None: no includedTypes, filter out types `route`, `locality`, `political`, `real_estate_agency`
    - [x] Return list of places; filter out `businessStatus != OPERATIONAL`; sort by distance from (lat, lng)
    - [x] If fewer than 3 results and radius < 500: retry with wider radius
  - [x] Function `search_text(query, lat=None, lng=None, box_size_m=400)`
    - [x] POST to `https://places.googleapis.com/v1/places:searchText`
    - [x] Field mask: same as above
    - [x] If lat/lng provided: build `locationRestriction.rectangle` from coordinates and box_size (use longitude offset formula for latitude)
    - [x] If lat/lng absent: omit `locationRestriction` — user includes location in query (e.g. "coffee Tokyo")
    - [x] Filter `businessStatus != OPERATIONAL`; when lat/lng present, sort by distance; otherwise return as-is
    - [x] If fewer than 3 results: widen box and retry (optional)
  - [x] Error handling: log failures, return empty list or raise
- [x] Category type mappings (from PRD): Food & Drink, Shopping, Attractions, Other (no filter)

**Manual Testing 3.1:**

- [ ] In Flask shell, call `search_nearby(40.74, -74.38, 200)` — verify results
- [ ] Call `search_text("coffee", 40.74, -74.38)` — verify results
- [ ] Verify OPERATIONAL filter works (if any closed place in results)
- [ ] Verify API key from env

---

### 3.2 Places API Proxy Endpoints

- [x] Implement `POST /travel-log/api/places/nearby` (JSON API)
  - [x] Expect JSON: `{ "lat": float, "lng": float, "radius": int?, "category": str? }`
  - [x] category: "food", "shopping", "attractions", "other" (or null)
  - [x] Call `search_nearby`, return JSON list of places
  - [x] `@login_required`
- [x] Implement `POST /travel-log/api/places/search` (JSON API)
  - [x] Expect JSON: `{ "query": str, "lat": float?, "lng": float? }` — lat/lng optional (for GPS-failure flow)
  - [x] If lat/lng present: call `search_text` with `locationRestriction`
  - [x] If lat/lng absent: call `search_text` with query only (no locationRestriction)
  - [x] `@login_required`
- [x] Ensure fetch requests include CSRF token in header (e.g. `X-CSRFToken` from meta tag)

**Manual Testing 3.2:**

- [ ] `curl` or Postman: POST search with valid lat/lng — verify JSON response
- [ ] POST search with query only (no lat/lng) — verify results (GPS-failure flow)

---

## Phase 4: Log Place UI (Browse, Search, Create) ✅

### 4.1 Log Place Page Structure

- [x] Implement `GET /travel-log/log` route
  - [x] Require at least one collection (redirect to create-first if none)
  - [x] Default collection = most recently used: query last Entry by current_user → its collection_id; if no entries yet, use most recently modified collection
  - [x] Pass collections list and default_collection_id to template
- [x] Create `templates/travel_log/log.html`
  - [x] **Subtle collection selector** — dropdown or link to change collection (default visible but not prominent)
  - [x] Two modes: Browse (no typing) and Search (typed)
  - [x] Browse: "Log This Place" button → triggers GPS → calls `/api/places/nearby` → shows results
  - [x] Search: search input → on input/debounce → calls `/api/places/search` with query + GPS
  - [x] When many results: category filter buttons (Food & Drink, Shop, Attraction, Other)
  - [x] Results list: place name, address, distance (server returns already filtered and sorted)
  - [x] **Google logo/attribution** when displaying Places results
  - [x] Selecting a place → show creation form: name, address, visited_date (all editable; visited_date defaults from lat/lng or today, user can override — supports logging places days later)
  - [x] `tlog-` prefix

**Manual Testing 4.1:**

- [x] Navigate to `/travel-log/log` — page loads
- [x] Grant GPS — Browse shows nearby places
- [x] Type in search — Search shows results
- [x] Select place — creation form appears with pre-filled name/address
- [x] Change collection via subtle control — verify selection persists

---

### 4.2 Client-Side: GPS, API Calls, Place Selection

- [x] Create `static/travel_log/log.js` (or similar)
  - [x] `navigator.geolocation.getCurrentPosition()` — get lat/lng; handle errors (show message, enable search-without-GPS or manual fallback)
  - [x] Fetch `/api/places/nearby` with lat, lng, radius (start 200), category
  - [x] If results < 3: retry with radius 400
  - [x] Fetch `/api/places/search` with query + lat/lng when GPS available; with query only when GPS failed (user includes location in search)
  - [x] Render results (server returns filtered, sorted); on tap → show form with place data
  - [x] Error handling: API failure → show "Add manually" fallback form (name, address only)

**Manual Testing 4.2:**

- [x] Test Browse flow on real device or with location mock
- [x] Test Search flow with "coffee", "restaurant"
- [x] Test GPS denied — search with query only works (e.g. "coffee Tokyo"); manual form available
- [x] Test API error — fallback form appears

---

### 4.3 Create Entry Backend

- [x] Implement `POST /travel-log/entries/create`
  - [x] Expect: `collection_id`, `user_name`, `user_address`, `place_id` (optional), `lat`, `lng` (optional), `visited_date` (optional — from form, or default)
  - [x] Validate: collection belongs to user, user_name not empty
  - [x] Default `visited_date` when not provided: if lat/lng present, derive from timezone (timezonefinder) → today in that TZ; else use creation date. User can override via form.
  - [x] Create Entry, update collection `last_modified`
  - [x] Flash success, redirect to collection detail
- [x] Add `timezonefinder` to requirements.txt
- [x] Helper: `get_visited_date_default(lat, lng)` → use timezonefinder to get IANA zone, then `datetime.now(ZoneInfo(zone)).date()`

**Manual Testing 4.3:**

- [x] Submit creation form — entry created, redirects to collection
- [x] Verify visited_date default from lat/lng when available
- [x] Verify visited_date default from today when no lat/lng
- [x] Override visited_date at creation (e.g. log yesterday's lunch) — verify saved correctly
- [x] Verify collection last_modified updated
- [x] Test manual fallback (no place_id, no lat/lng)

---

## Phase 5: Entry View & Edit ✅

### 5.1 Entry Detail / Edit Page

- [x] Implement `GET /travel-log/entries/<id>` route
  - [x] Fetch entry, verify ownership (404 if not)
  - [x] Pass entry (with photos) to template
- [x] Implement `POST /travel-log/entries/<id>/update`
  - [x] Validate ownership
  - [x] Update: user_name, user_address, notes, visited_date
  - [x] Update collection `last_modified`
  - [x] Flash success, redirect to collection
- [x] Implement `POST /travel-log/entries/<id>/delete`
  - [x] Verify ownership, delete entry (cascade photos), update collection last_modified
  - [x] Flash success, redirect to collection
- [x] Create `templates/travel_log/entries/edit.html`
  - [x] Editable: name, address, notes, visited_date (date picker)
  - [x] Photos section placeholder (Phase 6)
  - [x] Delete button with confirmation
  - [x] Save button
  - [x] Back to collection link

**Manual Testing 5.1:**

- [x] View entry — edit form loads with correct data
- [x] Edit and save — changes persist
- [x] Delete entry — removed from collection, redirects
- [x] Try editing another user's entry — 404

---

## Phase 6: Photo Upload (R2) ✅

### 6.1 R2 Service & Presigned URLs

- [x] Add `boto3` to requirements.txt
- [x] Add R2 env vars to config (from env)
- [x] Create `app/projects/travel_log/services/r2.py`
  - [x] Configure boto3 client for R2 (endpoint, credentials)
  - [x] `generate_presigned_upload_url(key, expires_in=300)` — PUT URL for browser upload
  - [x] `generate_presigned_download_url(key, expires_in=3600)` — GET URL for displaying photo
  - [x] Key format: `travel_log/{user_id}/{entry_id}/{uuid}.jpg`
- [x] Implement `POST /travel-log/api/photos/presign` (JSON)
  - [x] Expect: `{ "entry_id": int }`
  - [x] Verify entry belongs to user
  - [x] Generate key, presigned upload URL
  - [x] Return `{ "upload_url": str, "key": str }`
- [x] Implement `POST /travel-log/api/photos/confirm`
  - [x] Expect: `{ "entry_id": int, "key": str }`
  - [x] Verify entry belongs to user
  - [x] Create EntryPhoto, set sort_order (append)
  - [x] Update entry `updated_at`, collection `last_modified`
  - [x] Return success (photo saved immediately — no extra "Save" needed)

**Manual Testing 6.1:**

- [ ] In Flask shell, generate presigned URL — verify format
- [ ] Call presign endpoint — get URL
- [ ] Upload a file to the URL with curl — verify it lands in R2
- [ ] Call confirm — verify EntryPhoto created

---

### 6.2 Photo Display URLs

- [x] When rendering entry (edit or collection list): for each photo, generate presigned **download** URL server-side
- [x] Add helper or template logic: `get_photo_view_url(photo)` → presigned GET URL
- [x] Include in entry JSON or template

**Manual Testing 6.2:**

- [ ] Upload photo, view entry — image loads from R2 via presigned URL

---

### 6.3 Client-Side Photo Upload

- [x] Create `static/travel_log/photo_upload.js` (or in edit page)
  - [x] File input (accept image)
  - [x] On select: compress via Canvas (resize long edge to 1200px, JPEG 0.8)
  - [x] Request presign from `/api/photos/presign`
  - [x] PUT compressed blob to presigned URL
  - [x] Call `/api/photos/confirm` with key
  - [x] On success: append photo to UI, no page reload
  - [x] Error handling: show message, allow retry
  - [x] Support multiple photos (add more)
- [x] Add "Remove" for each photo
  - [x] Implement `POST /travel-log/entries/<id>/photos/<photo_id>/delete`
  - [x] Delete EntryPhoto (R2 object can be orphaned for now, or add cleanup job later)
- [x] Photos save **immediately** on upload — no "Save" button needed for photos
- [x] Photo lightbox: click to view larger, prev/next, Escape to close
- [x] Photo remove confirmation: "Are you sure?"
- [x] Save button disabled until form changes (photos autosave)

**Manual Testing 6.3:**

- [ ] Upload photo on edit page — appears immediately
- [ ] Upload multiple — all appear
- [ ] Remove photo — disappears, DB updated
- [ ] Test with large image (5MB) — verify compression reduces size
- [ ] Test on mobile — capture from camera works

---

## Phase 7: Error Recovery & Fallbacks ✅

### 7.1 Places API Failure

- [x] When `/api/places/nearby` or `/api/places/search` returns error or empty:
  - [x] Show fallback form: user can type place name and optionally address
  - [x] Submit creates entry with `place_id`=null, `lat`/`lng`=null
  - [x] `visited_date` defaults to creation date (no lat/lng to derive timezone)

**Manual Testing 7.1:**

- [ ] Simulate API failure (wrong key, network error) — fallback form appears
- [ ] Submit fallback form — entry created, displays correctly

---

### 7.2 GPS Failure

- [x] When `getCurrentPosition` fails or is denied:
  - [x] Show message: "Location not available. You can search by name (include location in your search, e.g. 'coffee Tokyo' or 'ramen Myeongdong Seoul') or add manually."
  - [x] **Search flow without GPS:** Call Text Search with query only (no `locationRestriction`). User includes location in the query string — e.g. "latte Shibuya", "pizza Hoboken NJ" — and gets results. Less precise than GPS-constrained search but still useful.
  - [x] `search_text(query)` in places service supports no lat/lng, no rectangle; Text Search accepts query-only.
  - [x] Manual form: name, address, visited_date (default today) — always available as fallback

**Manual Testing 7.2:**

- [ ] Deny GPS — search box allows query; try "coffee Tokyo" — verify results
- [ ] Verify manual form still available when no results or user prefers it

---

### 7.3 Photo Upload Failure

- [x] If presign fails: show "Upload failed, please try again"
- [x] If PUT to R2 fails: show retry option (user can try another file)
- [x] Don't block user from continuing to edit other fields

**Manual Testing 7.3:**

- [ ] Simulate R2 failure — error shown, user can still save other edits

---

## Phase 8: Polish & Integration ✅

### 8.1 Timestamps (last_modified, updated_at)

- [x] Ensure `collection.last_modified` is updated on: entry created, entry updated (incl. photo add/remove), collection renamed
- [x] Ensure `entry.updated_at` is set on create and updated on: entry field edits, photo add, photo remove (for correct ordering in collection detail)
- [x] Migration: backfill `last_modified` for existing collections (if any) — model defaults handle new data; optional data migration only if legacy rows exist

**Manual Testing 8.1:**

- [ ] Create entry → collection moves to top of list
- [ ] Edit entry → collection order updates
- [ ] Rename collection → order updates

---

### 8.2 Navigation & UX

- [x] Ensure "Log Place" is accessible from: index, collection detail
- [x] After creating entry: redirect to collection detail (not index)
- [x] Breadcrumbs or back links: Collection detail → Index
- [x] Mobile-friendly: touch targets (min-height 44px), readable text, tlog-page container

**Manual Testing 8.2:**

- [ ] Full flow: Index → Collection → Log Place → Create → back to Collection
- [ ] Full flow: Log Place → Create → Collection shows new entry
- [ ] Test on 375px viewport

---

### 8.3 Google Attribution

- [x] When displaying Places API results (place selection list): include attribution ("Powered by Google" link)
- [x] Reference: [Places API attribution](https://developers.google.com/maps/documentation/places/web-service/policies#attribution)

**Manual Testing 8.3:**

- [ ] Verify Google attribution visible in place selection UI

---

### 8.4 Edge Cases

- [x] User with no collections: clear empty state, CTA to create
- [x] Entry with no photos: show placeholder or "Add photos"
- [x] Long place names, long notes: truncate in list view (60 chars), full in edit
- [x] visited_date in past or future: allow (no validation)
- [x] CSRF on all forms
- [x] 404 for invalid entry/collection IDs (first_or_404)
- [x] 404 for other users' resources (not 403)

**Manual Testing 8.4:**

- [ ] Full user flow: Create collection → Log place (Browse) → Edit → Add photo → View in journal
- [ ] Full user flow: Log place (Search) → Create → Edit → Delete
- [ ] Delete collection with entries — confirm dialog, verify cascade
- [ ] Try accessing other user's collection/entry — 404

---

## Completion Checklist

- [x] All database models created and migrated
- [x] All routes return appropriate responses
- [x] All templates render correctly with `tlog-` CSS prefix
- [x] Login required on all routes
- [x] Ownership checks (404 for other users)
- [x] Places API proxy works (Browse + Search)
- [x] businessStatus filter applied
- [x] Results sorted by distance
- [x] visited_date default from lat/lng when available
- [x] R2 presigned upload works
- [x] Photo compression client-side
- [x] Photos save immediately on upload
- [x] Collection delete with confirmation (entry count)
- [x] Error recovery: API failure, GPS failure
- [x] Google attribution on place selection
- [x] Full flow testable end-to-end

---

## Future Enhancements (Post-V1)

- Map view (pins on a map)
- Sharing (read-only links)
- Dedicated "add place manually" flow
- R2 object cleanup job (delete orphaned objects)
- Full offline-first PWA
- Pretend I'm at coords
