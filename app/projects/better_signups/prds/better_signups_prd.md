# Better Signups PRD

This is a PRD for a better version of signup genius. The goal is to describe the requirements, very succinctly. We want to get an MVP version working, and then we can consider additional features.

# Process Rules

- Never create migrations by hand. Prompt me to run the flask db commands.

# Basics

1. The unit that a user creates will be called a List.
2. A list contains either events or items (just one)
3. Lists have a name and an optional description
4. Events are either dates or datetimes/timestamps (just one, and the creator chooses if they want to offer specific time ranges, or just dates). Either way, they have an optional field called location and an optional descriptions. (The date or datetime is the "name" but we won't store this. We'll format the name for display.) For times, let's store the datetime and the time zone. The time zone should be the creator's time zone. Let's also store the duration in minutes, not the end time. For dates, store as a Date field (no time component). For date-only events, set duration_minutes = None and timezone = None.
5. Items are strings. They have names and optional description.
6. If we need an internal term that includes both events and items, we can call them elements, but that will never be exposed to users.
7. There can be 1 or more signup spots available for each item event/item
8. Auth will be handled by my web app's existing auth. Users must be signed in to use this.
9. Each list can be either open to anyone with an account, or it can require an additional list password. Let's hash the password like with user passwords.
10. It should be possible for the end user to cancel their signup for a spot
11. A list creator is considered to be an editor and can add additional users to be list editors. Only creators can do this, editors cannot.
12. A list can be in the state or accepting signups, or not accepting signups
13. Editors can both remove signups and edit the lists/elements at any time. For now, they cannot reduce the number of spots in an element below the number already signed up.
14. When signing up, users can see (before the sign up) how many spots are available and who has taken spots so far (though per below, we may eventually offer to hide that)
15. Each user account needs to have the option to add other family members. For now, these other members only have a single full name for display.
16. When a user signs up, if they have other family members in their account, they have the option to indicate who they are signing up. The default is themselves. We should have some sort of self Family Member record so we don't have to special case it. The name should not be editable here, we will take it from the user's account.
17. A user can sign up more than one person for the same element if there are multiple spots. The same person cannot be signed up more than once for a splot though.
18. There is no public list of lists. It must be reached via direct link. This will be a standard UUID based URL that cannot be changed.

# One level beyond basics

1. Ability to limit how many spots one account signs up for within a list of elements (max 1 signup per element). Limits are at the level of the person being signed up (e.g. child), not the user doing the signups.
2. Have an option to do a lottery after a certain of time goes by (same lottery time for all elements in a list), rather than first come first served (it can only use one approach). No special action needed, this will be the only option for these elements (Enter lottery). Before the lottery, it will show the user that they have entered (and if they have other family members, there will be an option to enter another person). It will be done automatically at the chosen time, and users will be notified of results in emails. Users must click to accept (the creator can choose how long they have to accept). If they don't, it goes to the next person in the waitlist, or to no one if empty. Users can be in a lottery for more than one element (and for more than the limit for the given list). Limits will be applied as needed when the lottery is conducted (loterries will be done in random order, users cannot rank preferences between elements, once they hit the max they won't be in lotteries for future elements).
3. Within lists that user lotteries, have an option to always give everyone 1 spot before giving anyone a second spot, etc.
4. A list level option to allow swaps. If this is on, a user can request to switch out of their current spot, and a link is sent by email to any other users who are signed up on that list but for a different element. Whoever clicks that link first, the swap is completed automatically. Until the swap is completed, the requestor remains in their chosen spot.
5. Allow (ordered) waitlists on elements. For signups with lotteries, there will be an option up front to be added to a waitlist if not picked. For signups that are first come first served, there will just be an option to join the waitlist. The names can be visible or hidden. If someone cancels, the first name on the waitlist fills in. They must accept within some time (set by creator), or the next person is added. If the spot is not filled, it's then re-opened. A user can remove themselves from a waitlist at any time after it is created.
6. [x] Added to Google Calendar button
7. A way to view a user's signups (including their family members)

# Ideas that are not part of MVP, tracking them here for later

1. Allow someone to indicate they are flexible across several items
2. Allow hiding who else signed up
3. List editors can add questions that must be answered as part of taking a spot
4. Confirmation emails and reminder emails

# Implementation Plan

## Phase 1: Core Setup and Models

- [x] Create `models.py` from improved proposed models (move from `proposed_models_improved.py`)
- [x] Create database migration for all models
- [x] Create `__init__.py` for the better_signups module
- [x] Create Flask blueprint in `routes.py` with basic structure
- [x] Register blueprint in `app/__init__.py`
- [x] Import models in `app/__init__.py` so they're known to Flask-SQLAlchemy
- [x] Add project to `registry.py` (auth_required=True, type='project')

**Testing:**

- Verify the app starts without errors
- Check that "Better Signups" appears on the homepage (when logged in)
- Verify you can navigate to the Better Signups URL (should show a basic page or placeholder)
- Check database migration ran successfully (verify tables exist in database)

## Phase 2: Family Members Management

- [x] Create form for adding/editing family members
- [x] Create route for viewing family members list
- [x] Create route for adding family member
- [x] Create route for deleting family member
- [x] Create template for family members management
- [x] Ensure "self" family member is auto-created for existing users (migration or signal)
- [x] Ensure "self" family member is auto-created for new users (hook or signal)

**Testing:**

- Navigate to family members page (should be accessible when logged in)
- Verify your "self" family member appears automatically (name should match your account's full_name)
- Add a new family member (e.g., "John Doe")
- Verify the new family member appears in the list
- Try to add another family member with the same name (should work - no uniqueness constraint)
- Delete a family member and verify it's removed
- Verify you cannot delete your "self" family member (or it's protected somehow)
- Create a new user account and verify their "self" family member is auto-created

## Phase 3: List Creation and Management (Editor View)

- [x] Create form for creating a new list (name, description, type, password option)
- [x] Create route for creating a new list (generate UUID, set creator)
- [x] Create route for viewing list details (editor view)
- [x] Create route for editing list (name, description, password, accepting_signups toggle)
- [x] Create route for deleting a list
- [x] Create template for list creation form
- [x] Create template for list editor view
- [x] Add helper method to check if user is editor (including creator)

**Testing:**

- Navigate to "Create New List" page
- Create a list with name "Test Event List", type "events", no password
- Verify you're redirected to the list editor view
- Check that the list shows the correct name, description, and type
- Verify a UUID is generated and shown in the URL
- Edit the list: change name, add description, toggle "accepting signups" off and on
- Create another list with type "items" and a password
- Verify the password is set (you won't be able to test it until Phase 7)
- Delete one of the lists and verify it's removed
- Try to access a list you didn't create (should show error or redirect)

## Phase 4: List Editors Management

- [x] Create form for adding list editors (by email)
- [x] Create route for adding an editor
- [x] Create route for removing an editor
- [x] Add UI in list editor view for managing editors

**Testing:**

- As list creator, view the list editor page
- Add an editor by entering another user's email address
- Verify the editor appears in the editors list
- Try to add the same editor again (should show error or prevent duplicate)
- Try to add an invalid email (should show validation error)
- Remove an editor and verify they're removed from the list
- Log in as the added editor and verify you can access the list editor view
- Verify the editor can see the list but cannot delete it (or can, depending on requirements)

## Phase 5: Events Management

- [x] Create form for creating/editing events (date vs datetime, location, description, spots)
- [x] Create route for adding an event to a list
- [x] Create route for editing an event
- [x] Create route for deleting an event
- [x] Create template for event form
- [x] Add validation: cannot reduce spots below current signups
- [x] Handle timezone storage (use creator's timezone)
- [x] Add optional location linking to Google Maps (with toggle)
- [x] Enforce consistent event types within a list (all date or all datetime)
- [x] Display end time calculation for datetime events with duration
- [x] Improved event display with better formatting and timezone info

**Testing:**

- In an "events" type list, click "Add Event"
- Create a date-only event: select "date" type, pick a date, add location "Park", spots=5
- Verify the event appears in the list with correct date, location, and spots
- Create a datetime event: select "datetime" type, pick date/time, duration 60 minutes, location "Community Center", spots=3
- Verify the event shows datetime, timezone (should match your account timezone), duration, location
- Edit an event: change location, description, spots
- Try to reduce spots below number of signups (if any exist) - should show validation error
- Delete an event and verify it's removed
- Verify events are only shown in "events" type lists (not in "items" lists)

## Phase 6: Items Management

- [x] Create form for creating/editing items (name, description, spots)
- [x] Create route for adding an item to a list
- [x] Create route for editing an item
- [x] Create route for deleting an item
- [x] Create template for item form
- [x] Add validation: cannot reduce spots below current signups
- [x] Integrate items display in list view (similar to events)
- [x] Add proper error handling and user feedback

**Testing:**

- In an "items" type list, click "Add Item"
- Create an item: name "Bring Cookies", description "Chocolate chip preferred", spots=10
- Verify the item appears in the list with correct name, description, and spots
- Create multiple items and verify they all appear
- Edit an item: change name, description, spots
- Try to reduce spots below number of signups (if any exist) - should show validation error
- Delete an item and verify it's removed
- Verify items are only shown in "items" type lists (not in "events" lists)

## Phase 7: Public List View

- [x] Create route for viewing list by UUID (public view)
- [x] Create route for password-protected list access
- [x] Create template for public list view (shows events/items, spots available, current signups)
- [x] Display spots taken vs spots available for each element
- [x] Show who has signed up (family member names)
- [x] Handle list password authentication
- [x] Implement account-based password access (enter once, stay unlocked)
- [x] Editors bypass password requirements for both view and edit
- [x] Fix login redirect to return users to intended list after authentication

**Testing:**

- Copy the UUID from a list's editor view
- Open the UUID URL in an incognito/private window (or different browser) while logged out
- Verify you're prompted to log in (auth required)
- Log in and access the UUID URL again
- For a list without password: verify you can see the list immediately
- For a list with password: verify you're prompted for password
- Enter wrong password: should show error
- Enter correct password: should show the list
- Verify the list shows: name, description, all events/items
- For each element, verify it shows: spots available, spots taken (should be 0 initially), spots remaining
- Verify "Who has signed up" section shows empty or "No signups yet"
- Try accessing a non-existent UUID: should show 404 or error

## Phase 8: Signup Functionality

- [x] Create form for signing up (select family member if multiple available)
- [x] Create route for creating a signup
- [x] Create route for cancelling a signup
- [x] Add validation: same person cannot sign up twice for same element
- [x] Add validation: cannot sign up if no spots available
- [x] Update spots remaining display after signup/cancellation
- [x] Handle signup for multiple family members on same element

**Testing:**

- View a public list with available spots
- Click "Sign Up" on an element
- If you have multiple family members: verify dropdown shows all family members (including "self")
- If you only have "self": verify it's pre-selected or no dropdown shown
- Sign up yourself for an element
- Verify spots taken increases, spots remaining decreases
- Verify your name appears in "Who has signed up" section
- Try to sign up the same person again for the same element: should show error
- Sign up a different family member for the same element (if multiple spots available)
- Verify both names appear in signups
- Fill all available spots, then try to sign up again: should show "No spots available" error
- Cancel one of your signups
- Verify spots taken decreases, spots remaining increases
- Verify the cancelled signup no longer appears in "Who has signed up"
- Try to sign up again after cancelling: should work
- Test with a list that has "accepting_signups" set to False: signup button should be disabled or show message

## Phase 9: My Signups View

- [x] Create route for viewing user's own signups (all lists, all family members)
- [x] Create template for "My Signups" page
- [x] Display signups chronologically by signup date (most recent first)
- [x] Show for each signup: list name, element details (event date/time or item name), family member name, signup date
- [x] Add ability to cancel signups from this view
- [x] Add links to view the list (using UUID)
- [x] Show up to 3 most recent signups on the home page (index) with link to full page
- [x] Only show active signups (not cancelled)

**Testing:**

- Navigate to "My Signups" page (should be accessible from main Better Signups page)
- Verify page shows all active signups across all lists where you've signed up, ordered by signup date (most recent first)
- For each signup, verify it shows: list name, element (event date/time or item name), which family member (with "via [user name]" if not self), signup date
- Sign up for multiple elements across different lists
- Verify all signups appear on "My Signups" page in chronological order
- Verify cancelled signups do NOT appear
- Cancel a signup from the "My Signups" page
- Verify the signup is removed from the page (redirects back to My Signups)
- Click link to view a list from "My Signups" page - should navigate to public list view
- Test with multiple family members signed up - verify all appear correctly
- Verify home page shows up to 3 most recent signups with link to full page

## Phase 10: Editor Signup Management

- [x] Create route for editor to remove a signup
- [x] Add UI in editor view for managing signups
- [x] Show all signups (active and cancelled) in editor view

**Testing:**

- As list creator/editor, view the list editor page
- Verify you can see all signups for each element
- For each signup, verify it shows: family member name, user email (or name), signup date
- Distinguish between active and cancelled signups (different styling or section)
- Remove a signup as editor
- Verify the signup is removed (marked as cancelled or deleted)
- Verify spots remaining increases in both editor view and public view
- Log in as a different user, create some signups
- As editor, verify you can see and remove those signups
- Verify non-editors cannot access the editor view (should redirect or show error)

## Phase 11: Testing and Polish

- [x] Test all CRUD operations
- [x] Test authentication and authorization (editors, creators)
- [x] Test password-protected lists
- [x] Test family member signups
- [x] Test edge cases (cancelling, editing spots, etc.)
- [x] Add error handling and user-friendly messages
- [x] Add logging for important actions
- [x] Style templates to match existing app design
- [x] Test on different browsers/devices

**Testing:**

- **End-to-end workflow:** Create a list → Add events/items → Share UUID → Sign up → Cancel → Edit as creator
- **Multi-user scenario:** Create list → Add editor → Editor adds events → Both users sign up → Editor removes signup
- **Edge cases:**
  - Try to edit spots to 0 when there are signups (should fail)
  - Try to edit spots to 1 when there are 2 signups (should fail)
  - Try to edit spots to 3 when there are 2 signups (should succeed)
  - Sign up, cancel, sign up again (should work)
  - Access list with wrong password multiple times
  - Try to delete a list with signups (decide behavior)
- **UI/UX:**
  - Verify all pages match existing app styling
  - Check responsive design on mobile
  - Verify error messages are clear and helpful
  - Verify success messages appear after actions
  - Check all links and navigation work correctly
- **Security:**
  - Verify non-editors cannot edit lists
  - Verify users cannot access other users' family members
  - Verify password-protected lists work correctly
  - Test SQL injection attempts (should be handled by ORM)

## Future Phases (Post-MVP)

- [ ] Implement lottery system
- [ ] Implement waitlists
- [x] Implement swap functionality (see `swap_requests_prd.md`)
- [x] Add Google Calendar integration (button added for date and datetime events)
- [ ] Add per-list signup limits
- [ ] Add email notifications
