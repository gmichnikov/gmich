# Travel Log — Implementation Plan

This plan follows the PRD and breaks implementation into small, testable phases. Each phase ends with manual testing steps before moving on.

---

## Relevant Files

- `app/projects/travel_log/__init__.py` — package marker
- `app/projects/travel_log/models.py` — Collection, Entry, EntryPhoto models
- `app/projects/travel_log/routes.py` — blueprint and all routes
- `app/projects/travel_log/services/places.py` — Google Places API proxy (server-side)
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

**Manual verification:**
- [ ] Use boto3 in Python shell to list bucket (or upload a test file)
- [ ] Confirm credentials work before starting Phase 6

---

## Phase 1: Database Models & Collections CRUD

### 1.1 Database Models

- [ ] Create `models.py` with:
  - [ ] `Collection` model
    - [ ] `id`, `user_id` (FK to User), `name` (VARCHAR 255), `created_at`, `updated_at`
    - [ ] `last_modified` — denormalized; updated when entry added/edited or collection renamed (for ordering)
    - [ ] Relationship to Entry
    - [ ] `__repr__`
  - [ ] `Entry` model
    - [ ] `id`, `user_id`, `collection_id` (FK, nullable=False)
    - [ ] `place_id` (VARCHAR 255, nullable), `lat` (Float, nullable), `lng` (Float, nullable)
    - [ ] `user_name` (VARCHAR 255, nullable=False), `user_address` (Text, nullable), `notes` (Text, nullable)
    - [ ] `visited_date` (Date, nullable=False) — default from lat/lng timezone or creation date
    - [ ] `created_at`, `updated_at`
    - [ ] Relationship to Collection, EntryPhoto
    - [ ] `__repr__`
  - [ ] `EntryPhoto` model
    - [ ] `id`, `entry_id` (FK, ON DELETE CASCADE), `r2_key` (VARCHAR 255), `sort_order` (Int, default 0), `created_at`
    - [ ] `__repr__`
- [ ] Add index on `Entry(collection_id)`, `Entry(user_id)`, `Collection(user_id)`, `Collection(last_modified)`
- [ ] Import models in `app/__init__.py`

**Manual Testing 1.1:**
- [ ] Run `flask db migrate -m "Add travel log models"`
- [ ] Review migration — check columns, FKs, CASCADE on entry_photos
- [ ] Run `flask db upgrade`
- [ ] Verify tables exist with correct schema

---

### 1.2 Collections List & First-Time Flow

- [ ] Update `GET /travel-log/` (index) route:
  - [ ] If user has **zero collections** → redirect to "create first collection" flow (or render collections page with prominent empty state)
  - [ ] Otherwise: query user's collections ordered by `last_modified DESC`
  - [ ] For each collection: entry count, most recent entry preview (if any)
  - [ ] Pass to template
- [ ] Create `templates/travel_log/index.html` (Collections page)
  - [ ] Page title "Travel Log"
  - [ ] List of collections (name, entry count, last modified / preview)
  - [ ] Empty state: "Create your first collection to start logging places"
  - [ ] "New Collection" button
  - [ ] "Log Place" button (disabled or hidden if no collections?)
  - [ ] Use `tlog-` CSS prefix

**Manual Testing 1.2:**
- [ ] Navigate to `/travel-log/` as new user (no collections) — see empty state
- [ ] Verify login required

---

### 1.3 Create Collection

- [ ] Implement `GET /travel-log/collections/new` — render create form
- [ ] Implement `POST /travel-log/collections/create`
  - [ ] Validate name not empty
  - [ ] Create Collection, set `last_modified = created_at`
  - [ ] Flash success, redirect to index (or to Log Place flow?)
- [ ] Create `templates/travel_log/collections/new.html`
  - [ ] Name input, Submit, Cancel
  - [ ] `tlog-` prefix

**Manual Testing 1.3:**
- [ ] Create a collection — verify it appears on index
- [ ] Create second collection — verify both listed, ordered by last_modified

---

### 1.4 Rename & Delete Collection

- [ ] Implement `GET /travel-log/collections/<id>/edit` — render rename form
- [ ] Implement `POST /travel-log/collections/<id>/update` — update name, set `last_modified`, redirect
- [ ] Implement `POST /travel-log/collections/<id>/delete`
  - [ ] Verify ownership
  - [ ] Count entries that will be deleted
  - [ ] Delete collection (cascade deletes entries and entry_photos)
  - [ ] Flash success, redirect to index
- [ ] Create `templates/travel_log/collections/edit.html` (rename form)
- [ ] Add delete button with **confirmation dialog**: "Are you sure? This will permanently delete N entries." (N = actual count)

**Manual Testing 1.4:**
- [ ] Rename a collection — verify change persists
- [ ] Delete empty collection — verify removed
- [ ] Create collection with entries (Phase 2), then delete — verify confirmation shows entry count, and entries are gone after confirm

---

## Phase 2: Journal View (Collections & Entries List)

### 2.1 Collection Detail Page

- [ ] Implement `GET /travel-log/collections/<id>` route
  - [ ] Verify ownership (404 if not)
  - [ ] Query entries for this collection, ordered by `updated_at DESC`
  - [ ] Pass collection and entries to template
- [ ] Create `templates/travel_log/collections/show.html`
  - [ ] Collection name in header
  - [ ] List of entries: place name, address, visited_date, notes preview (truncated), photo count/thumbnails
  - [ ] Empty state: "No entries yet. Log your first place."
  - [ ] "Log Place" button
  - [ ] "Back to Collections" link
  - [ ] `tlog-` prefix

**Manual Testing 2.1:**
- [ ] Click collection from index — collection detail loads
- [ ] Empty collection shows empty state
- [ ] Verify 404 for other user's collection

---

### 2.2 Entry Placeholder (Create Without Places API)

- [ ] For testing Phase 2, add a minimal "Create Test Entry" route or seed script
  - [ ] OR: skip until Phase 4; Phase 2 can be tested with empty list and manual DB insert
- [ ] Entry display: place name, address, visited_date, notes preview, "No photos" or photo thumbnails
- [ ] Tap entry → goes to edit page (Phase 5)

**Manual Testing 2.2:**
- [ ] Insert test entry via Flask shell or minimal form — verify it displays on collection detail
- [ ] Verify ordering by updated_at

---

## Phase 3: Google Places API Service

### 3.1 Config & Places Service

- [ ] Add `GOOGLE_PLACES_API_KEY` to `config.py` (from env)
- [ ] Create `app/projects/travel_log/services/` directory (with `__init__.py`)
- [ ] Create `app/projects/travel_log/services/places.py` (see INITIAL_SPEC 5.3, 5.4, 5.6)
  - [ ] Function `search_nearby(lat, lng, radius_m=200, included_types=None)`
    - [ ] POST to `https://places.googleapis.com/v1/places:searchNearby`
    - [ ] Field mask: `places.displayName,places.formattedAddress,places.location,places.id,places.types,places.businessStatus`
    - [ ] `locationRestriction.circle` with center and radius
    - [ ] If `included_types`: pass as `includedTypes` array; if "other" or None: no includedTypes, filter out types `route`, `locality`, `political`, `real_estate_agency`
    - [ ] Return list of places; filter out `businessStatus != OPERATIONAL`; sort by distance from (lat, lng)
    - [ ] If fewer than 3 results and radius < 500: retry with wider radius
  - [ ] Function `search_text(query, lat=None, lng=None, box_size_m=400)`
    - [ ] POST to `https://places.googleapis.com/v1/places:searchText`
    - [ ] Field mask: same as above
    - [ ] If lat/lng provided: build `locationRestriction.rectangle` from coordinates and box_size (use longitude offset formula for latitude)
    - [ ] If lat/lng absent: omit `locationRestriction` — user includes location in query (e.g. "coffee Tokyo")
    - [ ] Filter `businessStatus != OPERATIONAL`; when lat/lng present, sort by distance; otherwise return as-is
    - [ ] If fewer than 3 results: widen box and retry (optional)
  - [ ] Error handling: log failures, return empty list or raise
- [ ] Category type mappings (from PRD): Food & Drink, Shopping, Attractions, Other (no filter)

**Manual Testing 3.1:**
- [ ] In Flask shell, call `search_nearby(40.74, -74.38, 200)` — verify results
- [ ] Call `search_text("coffee", 40.74, -74.38)` — verify results
- [ ] Verify OPERATIONAL filter works (if any closed place in results)
- [ ] Verify API key from env

---

### 3.2 Places API Proxy Endpoints

- [ ] Implement `POST /travel-log/api/places/nearby` (JSON API)
  - [ ] Expect JSON: `{ "lat": float, "lng": float, "radius": int?, "category": str? }`
  - [ ] category: "food", "shopping", "attractions", "other" (or null)
  - [ ] Call `search_nearby`, return JSON list of places
  - [ ] `@login_required`
- [ ] Implement `POST /travel-log/api/places/search` (JSON API)
  - [ ] Expect JSON: `{ "query": str, "lat": float?, "lng": float? }` — lat/lng optional (for GPS-failure flow)
  - [ ] If lat/lng present: call `search_text` with `locationRestriction`
  - [ ] If lat/lng absent: call `search_text` with query only (no locationRestriction)
  - [ ] `@login_required`
- [ ] Ensure fetch requests include CSRF token in header (e.g. `X-CSRFToken` from meta tag)

**Manual Testing 3.2:**
- [ ] `curl` or Postman: POST search with valid lat/lng — verify JSON response
- [ ] POST search with query only (no lat/lng) — verify results (GPS-failure flow)

---

## Phase 4: Log Place UI (Browse, Search, Create)

### 4.1 Log Place Page Structure

- [ ] Implement `GET /travel-log/log` route
  - [ ] Require at least one collection (redirect to create-first if none)
  - [ ] Default collection = most recently used: query last Entry by current_user → its collection_id; if no entries yet, use most recently modified collection
  - [ ] Pass collections list and default_collection_id to template
- [ ] Create `templates/travel_log/log.html`
  - [ ] **Subtle collection selector** — dropdown or link to change collection (default visible but not prominent)
  - [ ] Two modes: Browse (no typing) and Search (typed)
  - [ ] Browse: "Log This Place" button → triggers GPS → calls `/api/places/nearby` → shows results
  - [ ] Search: search input → on input/debounce → calls `/api/places/search` with query + GPS
  - [ ] When many results: category filter buttons (Food & Drink, Shop, Attraction, Other)
  - [ ] Results list: place name, address, distance (server returns already filtered and sorted)
  - [ ] **Google logo/attribution** when displaying Places results
  - [ ] Selecting a place → show creation form (name, address editable only; visited_date set server-side at save)
  - [ ] `tlog-` prefix

**Manual Testing 4.1:**
- [ ] Navigate to `/travel-log/log` — page loads
- [ ] Grant GPS — Browse shows nearby places
- [ ] Type in search — Search shows results
- [ ] Select place — creation form appears with pre-filled name/address
- [ ] Change collection via subtle control — verify selection persists

---

### 4.2 Client-Side: GPS, API Calls, Place Selection

- [ ] Create `static/travel_log/log.js` (or similar)
  - [ ] `navigator.geolocation.getCurrentPosition()` — get lat/lng; handle errors (show message, enable search-without-GPS or manual fallback)
  - [ ] Fetch `/api/places/nearby` with lat, lng, radius (start 200), category
  - [ ] If results < 3: retry with radius 400
  - [ ] Fetch `/api/places/search` with query + lat/lng when GPS available; with query only when GPS failed (user includes location in search)
  - [ ] Render results (server returns filtered, sorted); on tap → show form with place data
  - [ ] Error handling: API failure → show "Add manually" fallback form (name, address only)

**Manual Testing 4.2:**
- [ ] Test Browse flow on real device or with location mock
- [ ] Test Search flow with "coffee", "restaurant"
- [ ] Test GPS denied — search with query only works (e.g. "coffee Tokyo"); manual form available
- [ ] Test API error — fallback form appears

---

### 4.3 Create Entry Backend

- [ ] Implement `POST /travel-log/entries/create`
  - [ ] Expect: `collection_id`, `user_name`, `user_address`, `place_id` (optional), `lat`, `lng` (optional), `visited_date` (optional)
  - [ ] Validate: collection belongs to user, user_name not empty
  - [ ] Default `visited_date`: if lat/lng present, derive from timezone (timezonefinder) → today in that TZ; else use creation date
  - [ ] Create Entry, update collection `last_modified`
  - [ ] Flash success, redirect to collection detail
- [ ] Add `timezonefinder` to requirements.txt
- [ ] Helper: `get_visited_date_default(lat, lng)` → use timezonefinder to get IANA zone, then `datetime.now(ZoneInfo(zone)).date()`

**Manual Testing 4.3:**
- [ ] Submit creation form — entry created, redirects to collection
- [ ] Verify visited_date default from lat/lng when available
- [ ] Verify visited_date default from today when no lat/lng
- [ ] Verify collection last_modified updated
- [ ] Test manual fallback (no place_id, no lat/lng)

---

## Phase 5: Entry View & Edit

### 5.1 Entry Detail / Edit Page

- [ ] Implement `GET /travel-log/entries/<id>` route
  - [ ] Fetch entry, verify ownership (404 if not)
  - [ ] Pass entry (with photos) to template
- [ ] Implement `POST /travel-log/entries/<id>/update`
  - [ ] Validate ownership
  - [ ] Update: user_name, user_address, notes, visited_date
  - [ ] Update collection `last_modified`
  - [ ] Flash success, redirect to collection or stay on edit
- [ ] Implement `POST /travel-log/entries/<id>/delete`
  - [ ] Verify ownership, delete entry (cascade photos), update collection last_modified
  - [ ] Flash success, redirect to collection
- [ ] Create `templates/travel_log/entries/edit.html`
  - [ ] Editable: name, address, notes, visited_date (date picker)
  - [ ] Photos section (Phase 6)
  - [ ] Delete button with confirmation
  - [ ] Save button
  - [ ] Back to collection link

**Manual Testing 5.1:**
- [ ] View entry — edit form loads with correct data
- [ ] Edit and save — changes persist
- [ ] Delete entry — removed from collection, redirects
- [ ] Try editing another user's entry — 404

---

## Phase 6: Photo Upload (R2)

### 6.1 R2 Service & Presigned URLs

- [ ] Add `boto3` to requirements.txt
- [ ] Add R2 env vars to config (from env)
- [ ] Create `app/projects/travel_log/services/r2.py`
  - [ ] Configure boto3 client for R2 (endpoint, credentials)
  - [ ] `generate_presigned_upload_url(key, expires_in=300)` — PUT URL for browser upload
  - [ ] `generate_presigned_download_url(key, expires_in=3600)` — GET URL for displaying photo
  - [ ] Key format: `travel_log/{user_id}/{entry_id}/{uuid}.jpg`
- [ ] Implement `POST /travel-log/api/photos/presign` (JSON)
  - [ ] Expect: `{ "entry_id": int }`
  - [ ] Verify entry belongs to user
  - [ ] Generate key, presigned upload URL
  - [ ] Return `{ "upload_url": str, "key": str }`
- [ ] Implement `POST /travel-log/api/photos/confirm`
  - [ ] Expect: `{ "entry_id": int, "key": str }`
  - [ ] Verify entry belongs to user
  - [ ] Create EntryPhoto, set sort_order (append)
  - [ ] Update entry `updated_at`, collection `last_modified`
  - [ ] Return success (photo saved immediately — no extra "Save" needed)

**Manual Testing 6.1:**
- [ ] In Flask shell, generate presigned URL — verify format
- [ ] Call presign endpoint — get URL
- [ ] Upload a file to the URL with curl — verify it lands in R2
- [ ] Call confirm — verify EntryPhoto created

---

### 6.2 Photo Display URLs

- [ ] When rendering entry (edit or collection list): for each photo, generate presigned **download** URL server-side
- [ ] Add helper or template logic: `get_photo_view_url(photo)` → presigned GET URL
- [ ] Include in entry JSON or template

**Manual Testing 6.2:**
- [ ] Upload photo, view entry — image loads from R2 via presigned URL

---

### 6.3 Client-Side Photo Upload

- [ ] Create `static/travel_log/photo_upload.js` (or in edit page)
  - [ ] File input (accept image)
  - [ ] On select: compress via Canvas (resize long edge to 1200–1600px, JPEG 70–80%)
  - [ ] Request presign from `/api/photos/presign`
  - [ ] PUT compressed blob to presigned URL
  - [ ] Call `/api/photos/confirm` with key
  - [ ] On success: append photo to UI, no page reload
  - [ ] Error handling: show message, allow retry
  - [ ] Support multiple photos (add more)
- [ ] Add "Remove" for each photo
  - [ ] Implement `POST /travel-log/entries/<id>/photos/<photo_id>/delete`
  - [ ] Delete EntryPhoto (R2 object can be orphaned for now, or add cleanup job later)
- [ ] Photos save **immediately** on upload — no "Save" button needed for photos

**Manual Testing 6.3:**
- [ ] Upload photo on edit page — appears immediately
- [ ] Upload multiple — all appear
- [ ] Remove photo — disappears, DB updated
- [ ] Test with large image (5MB) — verify compression reduces size
- [ ] Test on mobile — capture from camera works

---

## Phase 7: Error Recovery & Fallbacks

### 7.1 Places API Failure

- [ ] When `/api/places/nearby` or `/api/places/search` returns error or empty:
  - [ ] Show fallback form: user can type place name and optionally address
  - [ ] Submit creates entry with `place_id`=null, `lat`/`lng`=null
  - [ ] `visited_date` defaults to creation date (no lat/lng to derive timezone)

**Manual Testing 7.1:**
- [ ] Simulate API failure (wrong key, network error) — fallback form appears
- [ ] Submit fallback form — entry created, displays correctly

---

### 7.2 GPS Failure

- [ ] When `getCurrentPosition` fails or is denied:
  - [ ] Show message: "Location not available. You can search by name (include location in your search, e.g. 'coffee Tokyo' or 'ramen Myeongdong Seoul') or add manually."
  - [ ] **Search flow without GPS:** Call Text Search with query only (no `locationRestriction`). User includes location in the query string — e.g. "latte Shibuya", "pizza Hoboken NJ" — and gets results. Less precise than GPS-constrained search but still useful.
  - [ ] Implement `search_text(query)` variant in places service — no lat/lng, no rectangle; Text Search accepts query-only.
  - [ ] Manual form: name, address, visited_date (default today) — always available as fallback

**Manual Testing 7.2:**
- [ ] Deny GPS — search box allows query; try "coffee Tokyo" — verify results
- [ ] Verify manual form still available when no results or user prefers it

---

### 7.3 Photo Upload Failure

- [ ] If presign fails: show "Upload failed, please try again"
- [ ] If PUT to R2 fails: show retry option
- [ ] Don't block user from continuing to edit other fields

**Manual Testing 7.3:**
- [ ] Simulate R2 failure — error shown, user can still save other edits

---

## Phase 8: Polish & Integration

### 8.1 Collection Last Modified

- [ ] Ensure `last_modified` is updated on:
  - [ ] Entry created
  - [ ] Entry updated (incl. photo add/remove)
  - [ ] Collection renamed
  - [ ] Migration: backfill `last_modified` for existing collections (if any)

**Manual Testing 8.1:**
- [ ] Create entry → collection moves to top of list
- [ ] Edit entry → collection order updates
- [ ] Rename collection → order updates

---

### 8.2 Navigation & UX

- [ ] Ensure "Log Place" is accessible from: index, collection detail
- [ ] After creating entry: redirect to collection detail (not index)
- [ ] Breadcrumbs or back links: Collection detail → Index
- [ ] Mobile-friendly: touch targets, readable text, tlog-page container

**Manual Testing 8.2:**
- [ ] Full flow: Index → Collection → Log Place → Create → back to Collection
- [ ] Full flow: Log Place → Create → Collection shows new entry
- [ ] Test on 375px viewport

---

### 8.3 Google Attribution

- [ ] When displaying Places API results (place selection list): include Google logo per terms
- [ ] Reference: [Places API attribution](https://developers.google.com/maps/documentation/places/web-service/policies#attribution)

**Manual Testing 8.3:**
- [ ] Verify Google logo/attribution visible in place selection UI

---

### 8.4 Edge Cases

- [ ] User with no collections: clear empty state, CTA to create
- [ ] Entry with no photos: show placeholder or "Add photos"
- [ ] Long place names, long notes: truncate in list view, full in edit
- [ ] visited_date in past or future: allow (no validation)
- [ ] CSRF on all forms
- [ ] 404 for invalid entry/collection IDs
- [ ] 404 for other users' resources (not 403)

**Manual Testing 8.4:**
- [ ] Full user flow: Create collection → Log place (Browse) → Edit → Add photo → View in journal
- [ ] Full user flow: Log place (Search) → Create → Edit → Delete
- [ ] Delete collection with entries — confirm dialog, verify cascade
- [ ] Try accessing other user's collection/entry — 404

---

## Completion Checklist

- [ ] All database models created and migrated
- [ ] All routes return appropriate responses
- [ ] All templates render correctly with `tlog-` CSS prefix
- [ ] Login required on all routes
- [ ] Ownership checks (404 for other users)
- [ ] Places API proxy works (Browse + Search)
- [ ] businessStatus filter applied
- [ ] Results sorted by distance
- [ ] visited_date default from lat/lng when available
- [ ] R2 presigned upload works
- [ ] Photo compression client-side
- [ ] Photos save immediately on upload
- [ ] Collection delete with confirmation (entry count)
- [ ] Error recovery: API failure, GPS failure
- [ ] Google attribution on place selection
- [ ] Full flow testable end-to-end

---

## Future Enhancements (Post-V1)

- Map view (pins on a map)
- Sharing (read-only links)
- Dedicated "add place manually" flow
- R2 object cleanup job (delete orphaned objects)
- Full offline-first PWA
