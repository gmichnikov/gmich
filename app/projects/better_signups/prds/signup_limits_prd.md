# Per-List Signup Limits PRD

## Overview

Add per-list signup limits to Better Signups, allowing list creators to limit how many elements each family member can sign up for within a list. This helps ensure fair distribution of spots across participants, especially in high-demand lists.

## Core Requirements

### List-Level Settings

1. **Max Signups Per Family Member**: Lists have an optional `max_signups_per_member` field (integer, nullable)

   - Default: `NULL` (no limit)
   - Can be set during list creation OR added later via edit list view
   - Can be changed at any time (increased or decreased)
   - Minimum value: 1 (if set) - setting to 0 is not allowed (use `accepting_signups=False` to close signups instead)
   - If changed to a lower value after signups exist, existing signups are NOT automatically removed

2. **Scope**: The limit applies per family member, not per account
   - If limit is 3, each family member can sign up for 3 elements independently
   - Example: Parent (self) can sign up for 3 events, Child A for 3 events, Child B for 3 events

### What Counts Toward the Limit

**ONLY confirmed and pending_confirmation signups count:**

- ✅ Signups with status='confirmed'
- ✅ Signups with status='pending_confirmation' (offered from waitlist)
- ❌ Waitlist entries do NOT count
- ❌ Cancelled signups do NOT count

**Rationale:** Waitlists are a queue for potential future signups, not actual commitments. We want to prevent gaming the system where someone signs up for everything then joins waitlists, but we don't want waitlists themselves to block participation.

### Signup Flow with Limits

#### Regular Signup (Element Not Full)

1. **Check Limit**: Before showing "Sign Up" button, check if family member has reached limit
2. **Display Logic**:

   - If at limit: Show message "Cannot sign up - [Family Member Name] has reached the limit (X/X spots used)"
   - If below limit: Show normal "Sign Up" button with progress indicator "([Current]/[Max] spots used)"
   - If no limit set: Show normal "Sign Up" button with no indicator

3. **Validation on Signup**:

   - Count current signups for that family member in that list (status='confirmed' or 'pending_confirmation')
   - If count >= limit: Reject with error "This person has already signed up for the maximum number of elements in this list (X/X)"
   - If count < limit: Allow signup

4. **Multiple Signups in One Action**: If user tries to sign up multiple family members for same element:
   - Check limit for EACH family member independently
   - Only sign up those who are below the limit
   - Show appropriate error messages for those at limit

#### Joining Waitlist

1. **Check Limit**: Before allowing someone to join waitlist, check current signup count
2. **Validation**:

   - Count current signups (confirmed + pending_confirmation) for that family member in that list
   - If count >= limit: Reject with error "Cannot join waitlist - [Family Member Name] has already signed up for the maximum number of elements (X/X). You can join the waitlist once they have fewer signups."
   - If count < limit: Allow joining waitlist

3. **Rationale**: We don't want waitlists clogged with people who can't actually take a spot. If they're already at max signups, they shouldn't be able to join any waitlists until they cancel something.

#### Promotion from Waitlist to Signup

1. **Check Limit**: When offering spot from waitlist (via cascade helper), check if family member has reached limit
2. **Logic**:

   - Count current signups for that family member in that list
   - If count >= limit: Skip this person, move to next person in waitlist, log event
   - If count < limit: Create pending_confirmation signup normally, send email

3. **Skipped Person Handling**:

   - The person stays on the waitlist (don't delete their WaitlistEntry)
   - Log: "Skipped offering spot to [Family Member] - at signup limit (X/X)"
   - Continue to next person in waitlist queue
   - If they later cancel a signup (freeing up space), they can still be offered future spots

4. **Cascade Logic Update**:
   - When spot opens, iterate through waitlist (ordered by position) until finding someone below limit
   - If everyone on waitlist is at their limit: Spot opens to general signup
   - May need to check multiple people in the queue

### Display Requirements

#### Public List View

1. **Per-Element Display**:

   - For each element, show signup button/status for each family member
   - If family member is at limit:
     - Replace "Sign Up" button with message: "At limit (X/X spots used)"
     - Use muted/grayed styling (e.g., gray text, strikethrough, or badge)
   - If family member is below limit:
     - Show "Sign Up" button
     - Show progress indicator next to button: "(2/3 spots used)"

2. **List-Level Banner**:

   - At top of list: "Note: Each person can sign up for up to X elements in this list"
   - Only show if limit is set
   - Clear, prominent placement so users understand the constraint upfront

3. **Family Member Selector**:
   - When user clicks "Sign Up" and has multiple family members
   - Show normal family member dropdown/selector
   - Validation happens on submit (server-side)
   - If family member is at limit, show clear error message after submit

#### Editor View

1. **List Settings Section**:

   - Show current limit setting: "Max signups per family member: 3" or "No limit"
   - Show edit button to change limit

2. **Per-Element Display**:
   - Same as current view, no special changes needed
   - Editors can still see all signups and can determine who's at limits by viewing the signup lists

#### My Signups View

1. **Per-Signup Display**:
   - Show normal signup details
   - No special changes needed (users can see their count by looking at their signups)

### Editor Capabilities

1. **Bypass Limits**: Editors can manually remove signups at any time

   - This may bring someone below their limit
   - No automatic re-offering from waitlist when this happens
   - User can then sign up for more elements or be offered from waitlist

2. **Change Limits**:
   - Can set limit for the first time
   - Can increase limit (users immediately able to sign up for more)
   - Can decrease limit (existing signups NOT removed, but no new signups allowed for those at/over limit)
   - Can remove limit (set to NULL) - all restrictions lifted

### Cancellation & Limit Updates

1. **User Cancels Signup**:

   - Signup status changes to 'cancelled'
   - Count decreases by 1 for that family member
   - User can now sign up for another element (if below limit)
   - User can now join waitlists (if previously blocked by limit)

2. **User Declines Pending Confirmation**:

   - Signup is deleted
   - Count decreases by 1
   - Same effects as cancellation

3. **Pending Confirmation Expires**:

   - Signup is deleted
   - Count decreases by 1
   - Same effects as cancellation

4. **Editor Removes Signup**:
   - Signup status changes to 'cancelled'
   - Count decreases by 1
   - Same effects as user cancellation

### Error Messages & User Feedback

1. **At Limit - Cannot Sign Up**:

   - "You cannot sign up [Family Member Name] for this because they have already signed up for the maximum number of elements in this list (X/X). Please cancel one of their existing signups first."

2. **At Limit - Cannot Join Waitlist**:

   - "[Family Member Name] cannot join the waitlist because they have already signed up for the maximum number of elements (X/X). Please cancel one of their existing signups first, or wait until a signup is confirmed from a current waitlist entry."

3. **Skipped in Waitlist Queue** (logged, not shown to user immediately):

   - Log: "Skipped offering spot to [Family Member Name] (user_id: X, family_member_id: Y) for [Element] - at signup limit (X/X)"
   - User doesn't receive email notification
   - Stays on waitlist for future opportunities

4. **Limit Increased**:

   - Flash message: "Signup limit increased to X per person. Users can now sign up for more elements."

5. **Limit Decreased**:
   - Flash message: "Signup limit decreased to X per person. This does not affect existing signups, but users at or above the limit cannot sign up for additional elements."
   - Note: No email notifications sent to affected users

## Edge Cases & Validation

### 1. Limit Set After Signups Exist

**Scenario**: List has 10 signups per person, limit is set to 3

**Behavior**:

- Existing signups are NOT removed or cancelled
- Users with 4+ signups are "grandfathered in"
- These users cannot sign up for additional elements until they cancel enough to get below the limit
- They CAN still be on waitlists from before the limit was set
- They CANNOT join new waitlists until below the limit
- They will be skipped when offered spots from waitlists (until they cancel to get below limit)

**Display**: Show "At limit (4/3 spots used)" to indicate over-limit state

### 2. User Has Pending Confirmations

**Scenario**: User has 2 confirmed signups and 1 pending_confirmation, limit is 3

**Behavior**:

- Total count = 3 (confirmed + pending_confirmation)
- User is at limit
- Cannot sign up for more elements
- Cannot join waitlists
- If pending_confirmation expires or is declined: count drops to 2, user can sign up/join waitlists again

### 3. Multiple Family Members, Some at Limit

**Scenario**: Limit is 3, Parent has 3 signups, Child has 1 signup

**Behavior**:

- Parent cannot sign up for more elements
- Child can sign up for 2 more elements
- Family member selector shows both with their counts
- Parent option is disabled with tooltip explaining they're at limit

### 4. Waitlist Queue All at Limit

**Scenario**: 5 people on waitlist, all are at their signup limit

**Behavior**:

- When spot opens, cascade helper checks each in order
- All 5 are skipped (logged)
- Spot opens to general signup (anyone below limit can take it)
- Waitlist entries remain (they might cancel other signups later)

### 5. Limit Removed (Set to NULL)

**Scenario**: Limit was 3, now removed

**Behavior**:

- All restrictions immediately lifted
- Users can sign up for unlimited elements
- Users can join unlimited waitlists
- Display no longer shows count indicators

### 6. Concurrent Signups at Limit

**Scenario**: User is at 2/3, tries to sign up for 2 different elements simultaneously

**Behavior**:

- Use database transactions
- First request succeeds (3/3)
- Second request fails with "at limit" error
- Race condition handled by checking within transaction

### 7. Lottery System Integration (Future)

**Scenario**: List uses lottery system, limit is 3

**Behavior** (planned for when lottery is implemented):

- Users can enter lottery for more than 3 elements
- When lottery runs (random order), limits are enforced as lotteries are processed
- Once someone wins 3 spots, they're removed from remaining lotteries
- This matches the description in the original PRD point #2 under "One level beyond basics"

## Technical Implementation

### Database Changes

1. **SignupList Model**:
   - Add field: `max_signups_per_member` (Integer, nullable=True, default=None)
   - Validation: If not NULL, must be >= 1

### Helper Functions

1. **`get_signup_count(family_member_id, signup_list_id)`**:

   - Count Signup records where:
     - family_member_id matches
     - signup_list_id matches (via element relationship)
     - status in ('confirmed', 'pending_confirmation')
   - Return integer count

2. **`is_at_limit(family_member_id, signup_list_id)`**:

   - Get list's max_signups_per_member
   - If NULL: return False (no limit)
   - Get signup count via helper above
   - Return True if count >= limit, else False

3. **`can_signup(family_member_id, signup_list_id)`**:

   - Return NOT is_at_limit(...)
   - Use in validation and display logic

4. **Update cascade helper** (`offer_spot_to_next_in_waitlist`):
   - When iterating waitlist queue:
     - For each person, check `is_at_limit()`
     - If at limit: Log, continue to next person (don't delete waitlist entry)
     - If below limit: Offer spot as normal (create pending_confirmation, delete waitlist entry)
   - If all waitlist entries checked and all at limit: return None (spot opens)

### Route Updates

1. **Signup Route** (`POST /list/<uuid>/signup`):

   - Add validation: `if is_at_limit(family_member_id, list_id): flash error + return`
   - Check before creating Signup record

2. **Join Waitlist Route** (`POST /list/<uuid>/element/<type>/<id>/waitlist/join`):

   - Add validation: `if is_at_limit(family_member_id, list_id): flash error + return`
   - Check before creating WaitlistEntry record

3. **Edit List Route** (`POST /list/<uuid>/edit`):
   - Add form field for max_signups_per_member
   - Validation: if provided, must be integer >= 1
   - Save to database
   - Flash appropriate message based on whether limit increased/decreased/set/removed

### Template Updates

1. **List Edit Form**:

   - Add input field: "Max signups per family member (leave blank for no limit)"
   - Type: number, min=1
   - Show current value if set

2. **Public List View**:

   - For each family member option, calculate and display count
   - Disable "Sign Up" button if at limit
   - Show progress indicator "(X/Y spots used)" if limit exists

3. **Family Member Selector** (modal/dropdown):

   - For each family member, show name + count
   - Disable those at limit
   - Add tooltip/help text

4. **Editor View**:
   - Add "Signup Summary" section showing counts per family member
   - Show limit in list settings section

## Migration Strategy

1. **Database Migration**:

   - Add `max_signups_per_member` column to `signup_list` table
   - Default: NULL (no limit)
   - No data migration needed (all existing lists will have no limit)

2. **Gradual Rollout**:
   - Feature is opt-in (list creators must explicitly set a limit)
   - Existing lists unaffected
   - New lists can optionally set limit at creation

## Testing Plan

### Unit Tests

1. **Helper Functions**:

   - Test `get_signup_count()` with various signup statuses
   - Test `is_at_limit()` with no limit, below limit, at limit, over limit
   - Test `can_signup()` logic

2. **Cascade Helper**:
   - Test skipping people at limit
   - Test offering to next person below limit
   - Test all people on waitlist at limit

### Integration Tests

1. **Signup Flow**:

   - Sign up when below limit (should succeed)
   - Sign up when at limit (should fail)
   - Sign up when no limit (should succeed)
   - Multiple family members with different counts

2. **Waitlist Flow**:

   - Join waitlist when below limit (should succeed)
   - Join waitlist when at limit (should fail)
   - Get offered from waitlist when at limit (should skip to next person)

3. **Limit Changes**:

   - Set limit on new list
   - Add limit to existing list with signups
   - Increase limit (users can sign up for more)
   - Decrease limit (users at/over limit cannot sign up)
   - Remove limit (all restrictions lifted)

4. **Cancellation**:
   - Cancel signup when at limit (count decreases, can sign up again)
   - Decline pending confirmation (count decreases)

### Manual Testing Scenarios

1. **End-to-End: Limit Enforcement**:

   - Create list with limit = 2
   - Add 5 elements
   - Sign up for 2 elements
   - Try to sign up for 3rd (should fail with clear message)
   - Cancel one signup
   - Sign up for another element (should succeed)

2. **End-to-End: Waitlist with Limits**:

   - Create list with limit = 2, allow_waitlist = True
   - Add 1 element with 2 spots
   - User A signs up (1/2)
   - User A signs up for another element (2/2, at limit)
   - User B signs up for first element (full)
   - User A tries to join waitlist for first element (should fail - at limit)
   - User A cancels second element signup (1/2)
   - User A joins waitlist for first element (should succeed)
   - User B cancels, spot offered to User A (should succeed)

3. **End-to-End: Multiple Family Members**:

   - Create list with limit = 2
   - User has 3 family members (self + 2 kids)
   - Sign up self for 2 elements (at limit)
   - Sign up Kid1 for 1 element (below limit)
   - Try to sign up self for another element (should fail)
   - Sign up Kid1 for another element (should succeed)
   - Verify each family member's count is independent

4. **Edge Case: Over Limit After Decrease**:

   - Create list with no limit
   - Sign up for 5 elements
   - Set limit to 3
   - Verify you cannot sign up for more
   - Verify display shows "5/3 spots used"
   - Cancel 2 signups (3/3)
   - Verify you still cannot sign up (at limit)
   - Cancel 1 more (2/3)
   - Verify you can now sign up

5. **Editor Functions**:
   - As editor, remove a signup for user at limit
   - Verify user can now sign up again
   - Change limit as editor
   - Verify changes take effect immediately

## Implementation Phases

### Phase 1: Database & Models

- [x] Add `max_signups_per_member` field to SignupList model
- [x] Create migration
- [x] Run migration

**Testing:**

- Verify new field exists in database
- Verify existing lists have NULL (no limit)

### Phase 2: Helper Functions

- [x] Create `get_signup_count(family_member_id, signup_list_id)` helper
- [x] Create `is_at_limit(family_member_id, signup_list_id)` helper
- [x] Create `can_signup(family_member_id, signup_list_id)` helper
- [ ] Write unit tests for helpers

**Testing:**

- Test helpers with various scenarios
- Test with no limit, below limit, at limit, over limit
- Test counting only confirmed + pending_confirmation

### Phase 3: Display Limit Settings

- [x] Add form field to list creation form
- [x] Add form field to list edit form
- [x] Add validation on form (must be >= 1 if provided)
- [x] Display limit in editor view (list settings section)

**Testing:**

- Create new list with limit
- Create new list without limit
- Edit existing list to add limit
- Edit existing list to change limit
- Edit existing list to remove limit (blank field)

### Phase 4: Enforce Limits on Signup

- [x] Update signup route to check `is_at_limit()` before creating signup
- [x] Add appropriate error message when validation fails
- [x] Update public list view to show count indicator "(X/Y spots used)" for family members
- [x] Show "At limit" message in place of "Sign Up" button when family member is at limit
- [x] Ensure error messages are clear and actionable

**Testing:**

- Sign up when below limit (should work)
- Try to sign up when at limit (should fail with error)
- Try to sign up when no limit (should work)
- Verify count indicator displays correctly
- Test with multiple family members

### Phase 5: Enforce Limits on Waitlist Join

- [x] Update join waitlist route to check `is_at_limit()` before creating waitlist entry
- [x] Add appropriate error message
- [x] Update "Join Waitlist" button logic to check limit

**Testing:**

- Join waitlist when below limit (should work)
- Try to join waitlist when at limit (should fail)
- Verify error message is clear

### Phase 6: Enforce Limits in Cascade Helper

- [x] Update `offer_spot_to_next_in_waitlist()` to check limits
- [x] Skip people at limit (log but don't delete waitlist entry)
- [x] Continue to next person in queue
- [x] If all at limit, return None (spot opens)

**Testing:**

- Create scenario where first person on waitlist is at limit
- Verify they're skipped and next person gets offered
- Verify skipped person stays on waitlist
- Test with entire waitlist at limit (spot should open)

### Phase 7: UI Polish & User Feedback

- [x] Add progress indicators throughout UI "(X/Y spots used)" (simplified to just banner)
- [x] Add list-level banner explaining limit
- [x] Improve error messages with helpful suggestions
- [x] Add tooltips where helpful
- [x] Style limit-related elements consistently

**Testing:**

- Review all user-facing messages
- Test on mobile/responsive
- Verify all indicators are clear and helpful

### Phase 8: Comprehensive Testing

- [ ] Run all unit tests
- [ ] Run all integration tests
- [x] Complete manual testing scenarios (listed above)
- [x] Test edge cases
- [ ] Test with large numbers (100+ signups)
- [ ] Test performance of helper functions

**Testing:**

- Follow testing plan above
- Document any issues found
- Fix and re-test

## Future Enhancements (Post-MVP)

- [ ] Lottery system integration (apply limits during lottery processing)
- [ ] Per-element limits (different limits for different element types)
- [ ] Configurable time-based limits (e.g., "max 2 per week")
- [ ] Analytics: Track how often limits are hit, how many users are affected
- [ ] Notifications when someone at limit has a spot free up (cancelled)
- [ ] Allow editors to temporarily bypass limits for specific users (exception list)

## Notes

- Limits are a fairness mechanism, not a hard security boundary
- Editors have flexibility to work around limits if needed (by removing the limit temporarily)
- Focus on clear communication to users about why they can't sign up
- The grandfathering approach for existing signups is intentional (avoid disruption)
- Validation is primarily server-side for simplicity; UI hints (like progress indicators) help users understand the constraint but validation happens on form submit
