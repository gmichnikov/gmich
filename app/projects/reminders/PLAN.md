# Reminders Project - Implementation Plan

This plan follows the PRD and breaks implementation into small, testable phases. Each phase ends with manual testing steps before moving on.

---

## Relevant Files

- `app/projects/reminders/__init__.py` — package marker
- `app/projects/reminders/models.py` — Reminder model
- `app/projects/reminders/routes.py` — blueprint and all routes
- `app/projects/reminders/templates/reminders/index.html` — reminder list (upcoming + past)
- `app/projects/reminders/templates/reminders/new.html` — create reminder form
- `app/projects/reminders/templates/reminders/edit.html` — edit reminder form
- `app/projects/reminders/static/reminders.css` — all styles, `reminders-` prefix
- `app/projects/reminders/commands.py` — Flask CLI command for cron job
- `app/__init__.py` — blueprint registration, model import, CLI command registration
- `app/projects/registry.py` — project registry entry

---

## Phase 1: Model & Migration

### 1.1 Database Model

- [x] Create `models.py` with `Reminder` model
  - [x] `id` — Integer primary key
  - [x] `user_id` — ForeignKey to `user.id`, not nullable
  - [x] `title` — String(255), not nullable
  - [x] `body` — Text, nullable
  - [x] `remind_at` — DateTime (UTC), not nullable
  - [x] `sent_at` — DateTime (UTC), nullable; set when email is successfully sent
  - [x] `created_at` — DateTime, not nullable, default utcnow
  - [x] Add relationship: `user = db.relationship('User', backref=...)`
  - [x] Add index on `(user_id, remind_at)`
  - [x] Add `__repr__` method
- [x] Import `Reminder` model in `app/__init__.py`

**Manual Testing 1.1:**
- [ ] Ask to run `flask db migrate -m "Add reminder table"`
- [ ] Review migration file — check columns, nullability, index
- [ ] Ask to run `flask db upgrade`
- [ ] Verify `reminder` table exists in database with correct schema

---

## Phase 2: Core Routes & Templates

### 2.1 Index Page (List View)

- [x] Implement `GET /reminders/` route
  - [x] Query upcoming reminders: `sent_at IS NULL`, `remind_at > now`, ordered by `remind_at ASC`
  - [x] Query past reminders: `sent_at IS NOT NULL`, ordered by `sent_at DESC`
  - [x] Pass both lists and `current_user.credits` to template
  - [x] Log project visit
- [x] Create `templates/reminders/index.html`
  - [x] **Credits display**: show current credit balance prominently
  - [x] **Credits warning**: if `upcoming_count > credits`, show a warning banner
  - [x] **Upcoming section**: list of pending reminders
    - [x] Show title, scheduled time (in user's timezone), body preview if present
    - [x] Actions: Edit, Delete, Duplicate
    - [x] Empty state: "No upcoming reminders"
  - [x] **Past section**: visually separated, collapsed or muted
    - [x] Show title, sent time (in user's timezone)
    - [x] Action: Duplicate
    - [x] Empty state: "No past reminders yet"
  - [x] "New Reminder" button linking to create form
  - [x] All CSS classes use `reminders-` prefix

**Manual Testing 2.1:**
- [ ] Navigate to `/reminders/` — page loads, empty states show
- [ ] Verify login is required (logged-out user redirected)
- [ ] Verify credit balance displays correctly
- [ ] Verify upcoming/past sections render without errors

---

### 2.2 Create Reminder

- [x] Implement `GET /reminders/new` route — render create form
- [x] Implement `POST /reminders/create` route
  - [x] Validate title is not empty
  - [x] Validate `remind_at` is in the future (server-side, UTC)
  - [x] Parse submitted datetime from user's timezone, convert to UTC before saving
  - [x] Create `Reminder` record and commit
  - [x] Flash success message
  - [x] Redirect to index
- [x] Create `templates/reminders/new.html`
  - [x] Title input (required)
  - [x] Body textarea (optional)
  - [x] Datetime picker: date + time, 15-minute increments, labeled with user's timezone
  - [x] Submit button, Cancel link back to index
  - [x] Show validation errors inline

**Manual Testing 2.2:**
- [ ] Create a reminder with title only — verify it saves and appears in Upcoming
- [ ] Create a reminder with title + body — verify body stored correctly
- [ ] Try submitting with empty title — verify error shown
- [ ] Try submitting a time in the past — verify error shown
- [ ] Verify scheduled time displays in user's timezone on the index page

---

### 2.3 Edit & Delete

- [x] Implement `GET /reminders/<int:id>/edit` route
  - [x] Fetch reminder, verify it belongs to current user (404 otherwise)
  - [x] Render edit form pre-filled with existing values
- [x] Implement `POST /reminders/<int:id>/update` route
  - [x] Same validations as create
  - [x] Only allow editing if `sent_at IS NULL` (can't edit a sent reminder)
  - [x] Update fields and commit
  - [x] Flash success, redirect to index
- [x] Implement `POST /reminders/<int:id>/delete` route
  - [x] Verify ownership (404 otherwise)
  - [x] Hard delete the record
  - [x] Flash success, redirect to index
- [x] Create `templates/reminders/edit.html`
  - [x] Same form as new, pre-filled
  - [x] Delete button (with confirmation prompt)

**Manual Testing 2.3:**
- [ ] Edit a reminder — verify changes saved and displayed correctly
- [ ] Delete a reminder — verify it disappears from the list
- [ ] Try editing another user's reminder (by URL) — verify 404
- [ ] Try editing a sent reminder — verify it is blocked

---

### 2.4 Duplicate

- [x] Implement `POST /reminders/<int:id>/duplicate` route
  - [x] Fetch reminder, verify ownership
  - [x] Redirect to `GET /reminders/new` with title and body pre-filled (via query params or session)
  - [x] Do NOT copy `remind_at` — user must pick a new time
- [x] Update new reminder form to accept optional pre-fill from query params

**Manual Testing 2.4:**
- [ ] Click Duplicate on an upcoming reminder — form opens pre-filled with title/body, no time set
- [ ] Click Duplicate on a past reminder — same behavior
- [ ] Submit the duplicated form — new reminder created, original unchanged

---

## Phase 3: Email Sending

### 3.1 Send Reminder Email Function

- [ ] Create `app/projects/reminders/email.py`
  - [ ] Function `send_reminder_email(reminder)`:
    - [ ] Build subject from `reminder.title`
    - [ ] Build body from `reminder.body` (if present) + link to `/reminders/`
    - [ ] Call `send_email()` from `app/utils/email_service.py`
    - [ ] Return True on success, raise on failure

**Manual Testing 3.1:**
- [ ] Call `send_reminder_email` directly in a Flask shell with a test reminder
- [ ] Verify email arrives with correct subject and body
- [ ] Verify the link to `/reminders/` is present

---

### 3.2 Test Now Button

- [ ] Add "Test Now" button to each upcoming reminder on the index page
- [ ] Implement `POST /reminders/<int:id>/test` route
  - [ ] Verify ownership
  - [ ] Check `current_user.credits >= 1` — if not, flash error and redirect
  - [ ] Call `send_reminder_email(reminder)`
  - [ ] Deduct 1 credit (`current_user.credits -= 1`, commit)
  - [ ] Flash success with "Test email sent (1 credit used, X remaining)"
  - [ ] Redirect to index
  - [ ] Do NOT set `sent_at` — this is a test, not the real send

**Manual Testing 3.2:**
- [ ] Click "Test Now" on a reminder — verify email arrives
- [ ] Verify credit count decreases by 1 in the UI
- [ ] Verify `sent_at` is still NULL after test send (reminder stays in Upcoming)
- [ ] Reduce credits to 0, try Test Now — verify error message shown, no email sent

---

## Phase 4: Cron Job

### 4.1 Cron Command

- [ ] Create `app/projects/reminders/commands.py`
  - [ ] Flask CLI command `flask reminders send`
  - [ ] Define window: `now - 10 minutes` to `now + 5 minutes`
  - [ ] Query: `remind_at` within window, `sent_at IS NULL`, `user.credits >= 1`
    - [ ] Join `Reminder` with `User` to filter on credits
  - [ ] For each matching reminder:
    - [ ] Call `send_reminder_email(reminder)`
    - [ ] On success: set `sent_at = utcnow()`, deduct 1 credit, commit
    - [ ] On failure: log error, leave `sent_at` NULL, continue to next
  - [ ] Print summary: N sent, N failed, N skipped (no credits)
- [ ] Register CLI command in `app/__init__.py`
  - [ ] Import and call `init_app` from `commands.py`

**Manual Testing 4.1:**
- [ ] Create a reminder with `remind_at` set to ~1 minute from now
- [ ] Wait for the time to pass, then run `flask reminders send` manually
- [ ] Verify email arrives
- [ ] Verify `sent_at` is set on the reminder in the DB
- [ ] Verify reminder moves from Upcoming to Past in the UI
- [ ] Verify 1 credit was deducted
- [ ] Create a reminder in the window, set user credits to 0, run command — verify it is skipped
- [ ] Create a reminder outside the window (2 hours ago) — verify it is NOT sent

---

### 4.2 Render Cron Job Setup

- [ ] Document the Render Cron Job configuration needed:
  - [ ] Command: `flask reminders send` (or the equivalent `python -m flask reminders send`)
  - [ ] Schedule: `*/5 * * * *` (every 5 minutes)
  - [ ] Environment: same env vars as the web service
- [ ] Add a note in this PLAN about how to set it up in the Render dashboard

**Render Setup Note:**
In the Render dashboard, add a new **Cron Job** service pointing to the same repo. Set the command to `flask reminders send` and the schedule to `*/5 * * * *`. It needs the same environment variables as the web service (DATABASE_URL, MAILGUN_API_KEY, etc.).

**Manual Testing 4.2:**
- [ ] After deploying, create a reminder ~10 minutes out on production
- [ ] Wait for the cron to fire
- [ ] Verify email arrives within ~5 minutes of the scheduled time
- [ ] Verify `sent_at` is set and reminder appears in Past section

---

## Phase 5: Polish & Edge Cases

### 5.1 Timezone Display

- [ ] Verify all datetime displays use the user's `time_zone` field
- [ ] Verify the datetime picker is clearly labeled with the user's timezone name
- [ ] Verify UTC storage is correct (no off-by-one on timezone conversion)

### 5.2 Credits Warning

- [ ] Verify warning banner appears when `upcoming_count > credits`
- [ ] Verify warning disappears when credits are sufficient
- [ ] Verify credit count updates immediately after Test Now

### 5.3 Edge Cases

- [ ] User with no timezone set — default to UTC gracefully
- [ ] Reminder edited to a time that has already passed — server-side validation blocks it
- [ ] Two reminders at the exact same time — both send correctly
- [ ] User account deleted — reminders are orphaned (acceptable for now, no cascade needed)

**Manual Testing 5.3:**
- [ ] Full flow: create → view in Upcoming → Test Now → edit → delete
- [ ] Full flow: create → wait for cron → view in Past → duplicate → create new
- [ ] Verify credit warning appears and disappears correctly
- [ ] Verify all times display in user's timezone throughout

---

## Completion Checklist

- [ ] All database models created and migrated
- [ ] All routes return appropriate responses
- [ ] All templates render correctly with `reminders-` CSS prefix
- [ ] Login required on all routes
- [ ] Ownership checks (404 for other users' reminders)
- [ ] Credits checked before every email send
- [ ] Cron command tested locally and on Render
- [ ] Timezone conversion correct (input in user tz, stored in UTC, displayed in user tz)
- [ ] Duplicate works from both Upcoming and Past sections
- [ ] Test Now does not set `sent_at`
- [ ] Sent reminders appear in Past section, not Upcoming

---

## Future Enhancements (Post-V1)

- [ ] Natural language input ("remind me in 3 days")
- [ ] Recurring reminders
- [ ] In-app snooze on past reminders
- [ ] SMS delivery via Twilio
- [ ] Snooze via email reply
- [ ] Calendar integration
