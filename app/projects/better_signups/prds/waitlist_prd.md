# Waitlist Feature PRD

## Overview

Add waitlist functionality to Better Signups, allowing users to queue for spots when elements (events/items) are full. When someone cancels, the first person on the waitlist is automatically offered the spot with 24 hours to accept.

## Core Requirements

### List-Level Settings

1. **Enable Waitlist Option**: Lists have a boolean `allow_waitlist` flag (default: False)
   - Set during list creation OR added later via edit list view
   - Can be enabled at any time
   - Can ONLY be disabled if ALL elements have empty waitlists (no one is waiting)
   - This is a list-level setting even though waitlists exist per-element

### Joining a Waitlist

1. **Eligibility**: Users can join a waitlist for an element when:

   - The list has `allow_waitlist = True`
   - The element is full (all spots taken by confirmed signups)
   - The user/family member is not already signed up for that element
   - The user/family member is not already on the waitlist for that element
   - The list is accepting signups (`accepting_signups = True`)

2. **Button Behavior**:

   - When element is full AND waitlist is enabled: Show "Join Waitlist" button
   - When element is full AND waitlist is disabled: Show "Full" (no button)
   - When element has spots: Show normal "Sign Up" button

3. **Family Members**:
   - Users can add family members to waitlists (same as regular signups)
   - Each family member joins independently (separate waitlist positions)
   - Users can add multiple family members to the same element's waitlist

### Waitlist Model

```
WaitlistEntry:
- id (PK)
- signup_list_id (FK to SignupList)
- element_type (enum: 'event', 'item')
- element_id (int, stores event_id or item_id)
- family_member_id (FK to FamilyMember)
- position (int, determines order)
- created_at (timestamp)
```

**Note:** WaitlistEntry records are **deleted** when processed (offered, accepted, or removed). The table only contains people actively waiting. History is tracked via Signup records with their status field.

### Waitlist Order

1. **FIFO (First In, First Out)**: Order determined by `position` field
2. When someone joins, they get `max(position) + 1` for that element
3. Position is unique per element (not globally unique)
4. Positions don't renumber when someone leaves (gaps are okay)

### Signup Status Extension

**Add new status to Signup model**: `status` field with values:

- `'confirmed'` (default, current behavior)
- `'pending_confirmation'` (offered from waitlist, awaiting acceptance)
- `'cancelled'` (existing, user cancelled)

### Cancellation → Waitlist Flow

When a user cancels a confirmed signup:

1. **Check for waitlist**: Query for `WaitlistEntry` for that element, ordered by position (ascending)
2. **If waitlist exists**:
   - Get first person (lowest position)
   - Create a Signup with status='pending_confirmation' for that family member
   - **Delete** the WaitlistEntry record (they're no longer on the waitlist)
   - Send notification email to the user
   - Start 24-hour timer
3. **If no waitlist**: Spot opens immediately for anyone to take

### Confirmation Flow

**Email Notification:**

- Email contains a link to the list view (using UUID)
- Subject: "A spot is available! [List Name] - [Element Name]"
- Body: "You've been offered a spot! Click here to view and confirm: [link to list]"
- Email also shows countdown (e.g., "You have until [date/time] to confirm")

**Web App Flow:**

1. **User clicks email link**: Navigates to the list view (must be logged in)
2. **List view displays**: Prominent alert/banner at top: "⏱ You have a spot waiting! [Element Name] - Confirm within 24 hours"
3. **In the element section**: Show the pending signup with visual indicator and "Confirm Your Spot" button
4. **User clicks "Confirm Your Spot"**:
   - Update Signup status from 'pending_confirmation' to 'confirmed'
   - Show success message: "Spot confirmed!"
   - Alert banner disappears
5. **User clicks "Decline Spot"** (optional button next to confirm):
   - Delete the Signup
   - Move to next person on waitlist (repeat entire flow with new email to next person)
   - If no one else on waitlist, spot opens to everyone

**Alternative confirmation page:**

- Could also create a dedicated `/list/<uuid>/confirm/<signup_id>` page instead of showing on main list view
- This page would just show the element details and big "Confirm" / "Decline" buttons
- Recommendation: Start with showing on main list view (simpler)

### 24-Hour Expiration

1. **Background job** (cron or similar) runs every 15-30 minutes:

   - Find all Signup records with status='pending_confirmation' where created_at > 24 hours ago
   - For each expired signup:
     - Delete the Signup (or mark as 'expired' if we want to track)
     - Move to next person on waitlist for that element (create new pending_confirmation for them)
     - If no one else on waitlist, spot opens to everyone

2. **Alternative**: Use a scheduled task library or trigger-based system

3. **Real-time check**: Also check expiration when list is viewed (in addition to background job) to avoid showing stale data

### Display Requirements

1. **Waitlist Visibility**: Show waitlist members in all views where signups are shown:

   - Public list view (under each element)
   - Editor list view
   - "My Signups" view (show both confirmed signups AND waitlist positions)

2. **Waitlist Display Format**:

   - Section header: "Waitlist" (separate from "Signups" or "Who's signed up")
   - Show: family member name, position number (optional), date joined
   - Style differently from confirmed signups (lighter background, italics, etc.)

3. **Pending Confirmation Display**:

   - Show in signup list with visual indicator: "(Pending confirmation)" or "⏱" icon
   - Lighter/grayed styling to indicate not fully confirmed
   - Countdown timer showing hours remaining? (optional, nice-to-have)

4. **My Signups View**:
   - Show confirmed signups
   - Show pending confirmations (with "Confirm" button)
   - Show waitlist positions (with position number, "Remove from waitlist" button)
   - Group or sort appropriately

### User Actions

1. **Join Waitlist**: Button visible when element is full and waitlist enabled
2. **Remove from Waitlist**: User can remove themselves (or family member) from waitlist at any time
   - Deletes the WaitlistEntry record
   - Button available in list view and "My Signups" view
3. **Confirm Spot**: Accept pending_confirmation signup within 24 hours
   - Accessed via email link → web app
   - Click "Confirm Your Spot" button on list view (or dedicated confirmation page)
4. **Decline Spot**: Optionally decline instead of just letting it expire
   - Deletes the pending_confirmation Signup
   - Automatically offers to next person on waitlist

### Editor Actions

1. **View Waitlists**: See all waitlist entries for all elements in editor view
2. **Remove from Waitlist**: Editors can manually remove someone from waitlist
3. **Manual Promotion** (Future/Optional): Editors could manually promote someone from waitlist to confirmed signup
4. **Cannot Disable Waitlist**: If any element has non-empty waitlist, cannot toggle `allow_waitlist` to False

### Notifications

**Email notifications** (requires email service):

1. **Spot Offered**: When moved from waitlist to pending_confirmation
   - Subject: "A spot is available! [List Name] - [Element Name]"
   - Body:
     - "Great news! You've been offered a spot from the waitlist."
     - Element details (event date/time or item name)
     - Deadline: "You have until [date/time] to confirm"
     - Link to list view: "Click here to confirm your spot: [link]"
     - Note: User must log in and click "Confirm Your Spot" button on the site
2. **Spot Confirmed**: Confirmation email (optional)
   - "Your spot has been confirmed!"
3. **Spot Expired**: Let them know they didn't confirm in time (optional)
   - "Your offered spot expired because you didn't confirm within 24 hours"

**In-app notifications** (stretch goal):

- Banner on home page: "You have a spot waiting for confirmation!"
- Badge count on Better Signups nav item

## Edge Cases & Validation

1. **Cannot join waitlist if already signed up** (confirmed or pending) for that element
2. **Cannot join waitlist if already on waitlist** for that element with same family member
3. **Waitlist only available if list has `allow_waitlist = True`**
4. **Cannot disable waitlist** if any elements have WaitlistEntry records (COUNT > 0)
5. **Pending signup counts as "taken spot"**: Other users see "0 spots available"
6. **Multiple family members**: User can have multiple family members on same waitlist
7. **If list.accepting_signups = False**: Cannot join waitlist (follows same rule as regular signups)

## Decisions Made

### 1. Can users join waitlist when accepting_signups = False?

- **DECISION**: No, waitlist follows accepting_signups flag
- Simpler and more consistent - if signups are closed, waitlist is also closed

### 2. Show waitlist position numbers?

- **DECISION**: Yes, show "You are #3 in line"
- More transparent, sets clear expectations for users

### 3. Keep WaitlistEntry after acceptance/expiration?

- **DECISION**: No, delete records when processed
- Keeps table simple and only contains active waiters
- History tracked via Signup status field

### 4. Multiple waitlists per list?

- **DECISION**: Yes, users can be on multiple element waitlists in same list
- Simpler and more flexible (no additional limit logic needed)

### 5. Decline button?

- **DECISION**: Yes, provide explicit decline option
- Better user experience than just waiting for expiration

### 6. Cascade timing?

- **DECISION**: When spot expires or is declined, immediately offer to next person
- Each person gets a fresh 24-hour window
- Honors the waitlist queue

### 7. 24-hour confirmation window?

- **DECISION**: Hardcoded to 24 hours (system-wide constant)
- Can be made configurable per-list in future if needed

## Future Decisions (Deferred)

### 1. Editors manually promote from waitlist?

- **Deferred**: Start without manual promotion, add later if needed
- Automatic promotion is simpler and fair

### 2. Notification timing?

- **Deferred**: Start with email immediately when spot offered
- Can add reminder email after 12 hours in future if users miss emails

### 3. Hide signups setting?

- **Deferred**: Will handle when "hide signups" feature is implemented
- Plan: treat waitlist same as signups for visibility

## Technical Clarifications

### Element Deletion with Waitlist

- If an editor deletes an element (event/item) that has waitlist entries, cascade delete all WaitlistEntry records
- No validation error, just clean up
- Matches existing behavior for signups (they also get deleted)

### Timezone for Deadline Display

- Display "You have until [date/time] to confirm" in the **user's timezone**
- Store deadline calculation as UTC internally (created_at + 24 hours)
- Convert to user's timezone for display in UI and emails
- If user timezone unknown, fall back to list creator's timezone or UTC

### Cancelling Pending Confirmations

- Users **cannot** use the regular "Cancel Signup" action on pending_confirmation signups
- Only actions available: "Confirm Your Spot" or "Decline Spot" buttons
- This makes the intent clearer and prevents confusion
- Declining triggers cascade (next person offered), cancelling wouldn't

### Race Condition Handling

- Use database transactions with proper isolation level for critical operations:
  - Creating/cancelling signups
  - Joining/leaving waitlist
  - Cascade helper function (offer to next person)
- Check spot availability and waitlist position within same transaction
- Handle concurrent cancellations: each spot offers to exactly one person from waitlist
- If two users cancel simultaneously, two separate people get offered (one per cancelled spot)

### Background Job Implementation

- Use **Flask CLI command** + **system cron**
- Create command: `flask better-signups check-expirations`
- Set up cron job to run every 15-30 minutes
- Command logs: how many expirations processed, any errors
- Simple approach, no additional dependencies (no Celery/Redis needed for MVP)

### Pending Confirmation Display Location

- Show pending_confirmation signups **in the regular signups list** (not separate section)
- Add visual indicator: "(Pending confirmation)" badge or ⏱ icon
- Use lighter/grayed styling to differentiate from confirmed signups
- Include "Confirm Your Spot" and "Decline Spot" buttons inline with the signup
- At element level, they count as a taken spot for availability calculations

## Implementation Phases

### Phase 1: Data Model & List Settings

- [ ] Add `allow_waitlist` field to SignupList model (boolean, default False)
- [ ] Create WaitlistEntry model (signup_list_id, element_type, element_id, family_member_id, position, created_at)
- [ ] Add `status` field to Signup model (enum: 'confirmed', 'pending_confirmation', 'cancelled')
- [ ] Create migration
- [ ] Write data migration to update all existing Signup records to status='confirmed'
- [ ] Update list creation form to include `allow_waitlist` checkbox
- [ ] Update list edit form to include `allow_waitlist` toggle
- [ ] Add validation on list edit: cannot disable waitlist if any elements have non-empty waitlists

**Testing:**

- Create new list with waitlist enabled
- Create new list with waitlist disabled
- Toggle waitlist on/off on existing list
- Verify cannot disable if waitlist entries exist

### Phase 2: Joining & Displaying Waitlists

- [ ] Add "Join Waitlist" button logic to public list view (show only when element full AND allow_waitlist=True)
- [ ] Create route for joining waitlist (POST `/list/<uuid>/element/<type>/<id>/waitlist/join`)
- [ ] Add validation:
  - List must have allow_waitlist=True
  - Element must be full (no available spots)
  - User/family member not already signed up for that element (any status)
  - User/family member not already on waitlist for that element
  - List must be accepting_signups=True
- [ ] Calculate position = max(position for that element) + 1 (or 1 if first)
- [ ] Create WaitlistEntry record
- [ ] Display waitlist section under each element in public list view
  - Show "Waitlist" header
  - List family member names with position numbers
  - Show "You are #X in line" if current user/family on waitlist
- [ ] Update editor view to show waitlist entries for each element
- [ ] Update "My Signups" view to show waitlist positions
  - Section: "Waitlists You're On"
  - Show: list name, element name/date, position, date joined

**Testing:**

- Join waitlist when element is full
- Verify position numbers are correct
- Try to join again (should fail validation)
- Add multiple family members to same waitlist
- View waitlist in public, editor, and My Signups views

### Phase 3: Remove from Waitlist

- [ ] Add "Remove from Waitlist" button in public list view (next to each waitlist entry)
- [ ] Add "Remove from Waitlist" button in My Signups view
- [ ] Create route for removing from waitlist (POST `/list/<uuid>/waitlist/<id>/remove`)
- [ ] Validation: must be your own family member or you're an editor
- [ ] Delete the WaitlistEntry record
- [ ] Show success message

**Testing:**

- Remove yourself from waitlist
- Remove family member from waitlist
- Verify positions of others don't change (gaps are okay)
- Verify editor can remove anyone from waitlist

### Phase 4: Cascade Helper Function

- [ ] Create helper function `offer_spot_to_next_in_waitlist(element_type, element_id)`
  - Query for WaitlistEntry records for that element, ordered by position ASC
  - If found:
    - Get first entry
    - Create Signup with status='pending_confirmation', created_at=now
    - Delete the WaitlistEntry record
    - Return the created Signup (or user info for email)
  - If not found:
    - Return None (spot opens to everyone)
- [ ] Add logging for all cascade events
- [ ] Handle edge cases (concurrent deletions, etc.)

**Testing:**

- Unit test the helper function with various scenarios
- Test with empty waitlist (returns None)
- Test with one person on waitlist
- Test with multiple people on waitlist

### Phase 5: Cancellation → Offer Flow

- [ ] Update cancel signup route to call cascade helper after deletion
- [ ] If cascade returns a Signup, trigger email notification (queue for Phase 8)
- [ ] Update public list view to display pending_confirmation signups with visual indicator
  - Show "(Pending confirmation)" badge or ⏱ icon
  - Use lighter/grayed styling
- [ ] Update spots calculation logic:
  - pending_confirmation counts as a taken spot
  - Don't show "Join Waitlist" button if a pending_confirmation exists

**Testing:**

- Sign up for element, then cancel
- Verify first person on waitlist gets pending_confirmation signup
- Verify their WaitlistEntry is deleted
- Verify pending signup appears with visual indicator
- Verify "Join Waitlist" button doesn't show (spot is taken)

### Phase 6: Confirmation & Decline Flow

- [ ] Add helper function to check if user has any pending_confirmation signups for a list
- [ ] Update public list view: if user has pending_confirmation, show alert banner at top
  - "⏱ You have a spot waiting! [Element Name] - Confirm within 24 hours"
- [ ] Add "Confirm Your Spot" button next to pending_confirmation signups
- [ ] Create route for confirming spot (POST `/list/<uuid>/signup/<id>/confirm`)
  - Update Signup status from 'pending_confirmation' to 'confirmed'
  - Show success message
- [ ] Add "Decline Spot" button next to "Confirm Your Spot"
- [ ] Create route for declining spot (POST `/list/<uuid>/signup/<id>/decline`)
  - Delete the Signup record
  - Call cascade helper to offer to next person
  - Show message: "Spot declined and offered to next person"
- [ ] Update "My Signups" view to prominently show pending confirmations
  - Separate section at top: "Spots Waiting for Confirmation"
  - Show countdown/deadline
  - Include "Confirm" and "Decline" buttons

**Testing:**

- Get offered a spot from waitlist
- View list and see alert banner
- Click "Confirm Your Spot" and verify status changes
- Get offered another spot and click "Decline"
- Verify next person gets offered
- View My Signups and see pending confirmation

### Phase 7: Expiration & Background Job

- [ ] Create helper function to check and expire pending confirmations
  - Find all Signup with status='pending_confirmation' AND created_at < (now - 24 hours)
  - For each expired signup:
    - Get element info
    - Delete the Signup
    - Call cascade helper
    - Log the expiration event
- [ ] Add real-time expiration check to list view (run helper on page load)
  - Prevents showing stale data
  - Process any expirations before rendering
- [ ] Create background job/cron that runs every 15-30 minutes
  - Calls the expiration helper function
  - Logs how many expirations processed
- [ ] Add command line script for manual expiration check (for testing)
  - `flask better-signups check-expirations`

**Testing:**

- Manually set created_at to > 24 hours ago in database
- Run expiration checker
- Verify signup is deleted and next person gets offered
- Test with no one left on waitlist (spot opens up)
- Test background job runs correctly

### Phase 8: Email Notifications

- [ ] Create email template for "Spot Offered" notification
  - Subject: "A spot is available! [List Name] - [Element Name]"
  - Body:
    - "Great news! You've been offered a spot from the waitlist."
    - Element details (event date/time or item name)
    - Deadline: "You have until [date/time] to confirm"
    - Clear instructions: "Click the link below, log in, and click 'Confirm Your Spot'"
    - Link to list view: `/list/<uuid>`
- [ ] Integrate email sending into cascade helper (or trigger after cascade)
- [ ] Send email when:
  - Spot offered from waitlist (cancellation flow)
  - Spot offered after decline
  - Spot offered after expiration
- [ ] Optional: Create "Spot Confirmed" confirmation email
- [ ] Optional: Create "Spot Expired" notification email

**Testing:**

- Join waitlist, have someone cancel, verify email received
- Check email content and formatting
- Click link in email and verify it goes to list view
- Test with multiple cascade events (multiple emails sent)

### Phase 9: Testing & Polish

- [ ] **End-to-end flow testing:**
  - Create list with waitlist enabled
  - Fill all spots
  - Have multiple people join waitlist
  - Cancel a signup
  - Verify first person gets email and pending_confirmation
  - Confirm the spot
  - Cancel another signup
  - Verify next person gets offered
  - Let this one expire (24h)
  - Verify third person gets offered
- [ ] **Multiple family members:**
  - Add multiple family members to same waitlist
  - Verify each gets offered independently
- [ ] **Editor functionality:**
  - Verify editors can see all waitlists
  - Verify editors can remove people from waitlist
  - Verify editors cannot disable waitlist when non-empty
- [ ] **Edge cases:**
  - Try to join waitlist when already signed up (should fail)
  - Try to join waitlist when already on waitlist (should fail)
  - Try to confirm a spot that has expired (should show error)
  - Cancel signup when waitlist is empty (spot opens normally)
  - Disable waitlist when all waitlists are empty (should work)
  - Try to disable waitlist when someone is waiting (should fail)
- [ ] **Race conditions:**
  - Two people try to sign up for last spot simultaneously
  - Someone cancels while someone else joins waitlist
  - Spot expires while user is clicking confirm
- [ ] **UI/UX:**
  - Verify waitlist sections are clearly labeled
  - Verify pending signups are visually distinct
  - Verify position numbers are accurate
  - Verify alert banner is prominent
  - Check responsive design on mobile
- [ ] **Performance:**
  - Test with large waitlist (50+ people)
  - Verify cascade doesn't cause issues
  - Verify expiration check is fast
- [ ] **Logging & monitoring:**
  - Verify all important events are logged
  - Check logs for cascade events
  - Check logs for expirations

## Future Enhancements (Post-MVP)

- [ ] Editor manual promotion from waitlist
- [ ] Reminder emails
- [ ] In-app notifications
- [ ] Waitlist analytics (track how many spots filled from waitlist)
- [ ] Integration with lottery system (waitlist after lottery completes)
- [ ] Allow users to set per-element waitlist limits

## Notes

- Waitlist is separate from lottery system (that's a future feature)
- This is simpler than lottery: just FIFO queue with auto-promotion
- The 24-hour confirmation window is hardcoded
