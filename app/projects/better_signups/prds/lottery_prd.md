# Lottery System PRD

## Overview

This PRD describes the lottery system for Better Signups. Instead of first-come-first-served signups, list creators can enable a lottery mode where users enter a lottery for each element, and winners are randomly selected at a specified datetime. This ensures fair distribution of spots regardless of when users access the list.

## Core Concepts

### Lottery-Enabled Lists

- A list can be marked as a lottery list at **creation time only**
- Once a list is created as a lottery list, this **cannot be turned off**
- All elements in a lottery list use the lottery system
- Regular lists cannot be converted to lottery lists (and vice versa)

### Lottery Datetime

- The creator sets a lottery datetime when creating the list
- The lottery datetime must be **at least 1 hour in the future** (from current time in creator's timezone)
- The creator can change the lottery datetime later, but it must remain at least 1 hour in the future
- The lottery will execute automatically **within 60 minutes after** the scheduled time (not before)
- UI must clearly display: "Lottery will run on [date/time] in [creator's timezone]. It may take up to 1 hour after this time to complete."

**Validation:**

- Form validation and backend validation must check: `lottery_datetime >= current_time + 1 hour`
- Validation must compare times in the same timezone (convert to UTC for comparison)
- Error message: "Lottery time must be at least 1 hour from now"

### Timezone Handling

- The lottery datetime is entered in the **creator's timezone**
- Store both the UTC datetime and the creator's timezone in the database
- Display the lottery datetime to all users in the **creator's timezone** with clear timezone indication (e.g., "March 15, 2025 at 3:00 PM EST")
- Make it very clear in the UI what timezone is being used

## User Experience

### Before Lottery

**Entering the Lottery:**

- Instead of "Sign Up" buttons, users see "Enter Lottery" buttons
- Users can enter multiple family members for the same element (if there are enough spots)
- Users can enter lotteries for more elements than the list limit allows winning (if limits are enabled)
- Users can remove any of their lottery entries (for any family member) at any time before the lottery runs
- The list displays:
  - Who has entered each lottery (family member names and their account)
  - How many entries each element has
  - The lottery datetime prominently displayed
  - Clear indication that this is a lottery list, not first-come-first-served

**What Users Can See:**

- All lottery entries are visible (similar to how signups are visible)
- For each element, show: "X entries" and list of family members who entered
- Clearly show the lottery datetime and timezone

**Creator/Editor Actions:**

- Creators can still edit elements:
  - Change number of spots
  - Add new elements
  - Delete elements (even with entries)
  - Change element details (dates, descriptions, etc.)
- Creators can change the lottery datetime (must remain in future)
- All normal list editing capabilities remain available

### During Lottery Execution

- When the lottery is actively running, the list shows: "Lottery in progress... Please check back shortly."
- All actions are blocked (no entering, no removing entries, no editing by creators)
- This should be a brief state (just while the lottery algorithm runs)

### After Lottery

**Winner Acceptance:**

- Winners receive an email with links to accept each spot they won
- Each spot must be individually accepted (if someone won multiple spots or for multiple family members)
- Winners have **24 hours** to accept each spot
- If not accepted within 24 hours:
  - If waitlist is enabled: offer to next person on waitlist (they also get 24 hours)
  - If no waitlist: spot becomes available for regular signup
- Acceptance workflow is similar to existing waitlist acceptance

**Post-Lottery Operations:**

- After lottery completes, normal list operations resume:
  - Unfilled spots can be signed up for (first-come-first-served)
  - Waitlist operates normally (if enabled)
  - Users can cancel their won spots
  - All existing list features work as normal
- The system tracks that the lottery has completed (never runs again)

## Lottery Algorithm

### Execution Timing

- Automated job runs every hour (via Heroku Scheduler)
- Job looks for lotteries scheduled in the past 65 minutes that haven't run yet
- Each lottery is processed and marked as completed

### Processing Order

- Process elements in order:
  - **Events (date/datetime lists)**: Chronological order by date/datetime
  - **Items lists**: Order they appear in the list (display order)

### Selection Algorithm (Per Element)

For each element:

1. **Collect all entries** for this element
2. **Apply list limits** (if enabled):
   - Track how many spots each user has already won in this lottery run
   - Filter out entries for users who have already reached their limit
3. **Randomly select winners**:
   - Select the number of winners equal to available spots
   - Use random selection from eligible entries
4. **Create pending signups** for winners (requiring acceptance within 24 hours)
5. **Handle waitlist** (if enabled on this list):
   - Take remaining non-winning entries
   - Randomly order them
   - Add to waitlist in that random order
   - Note: Users at their limit can still be on waitlists, but existing waitlist logic prevents them from moving up

### Under-subscribed Lotteries

- If fewer entries than available spots: all entrants automatically win
- Still require acceptance within 24 hours

### List Limits Integration

- If a list has a `max_signups_per_member` set, apply it during lottery:
  - Track wins per user (across all their family members) during lottery processing
  - Once a user reaches their limit, remove their remaining entries from consideration
  - Users CAN be on waitlists even after reaching their limit
  - Existing waitlist logic prevents them from receiving spots beyond the limit

## Email Notifications

### Lottery Completion Email (to Participants)

**Sent to:** Each user who had ANY lottery entries (one email per user account, not per family member)

**Content includes:**

- List name
- Clear statement: "The lottery has completed"
- **For each family member:**
  - **Won spots:** Element details, link to accept (24-hour deadline clearly stated)
  - **Waitlist positions:** Element details, waitlist position number
  - **Did not win:** Elements they entered but didn't win and aren't on waitlist
- Call to action: Accept your spots within 24 hours via the links provided

### Lottery Completion Email (to Creator)

**Sent to:** List creator

**Content includes:**

- List name
- Summary: "Your lottery has completed"
- For each element:
  - How many entries received
  - How many spots filled (pending acceptance)
  - How many on waitlist (if enabled)
- Link to view list editor page

## Database Schema Changes

### SignupList Model

Add fields:

```python
is_lottery = db.Column(db.Boolean, default=False, nullable=False)
lottery_datetime = db.Column(db.DateTime(timezone=True), nullable=True)  # UTC
lottery_timezone = db.Column(db.String(50), nullable=True)  # e.g., "America/New_York"
lottery_completed = db.Column(db.Boolean, default=False, nullable=False)
```

### LotteryEntry Model (New)

```python
class LotteryEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    element_id = db.Column(db.Integer, db.ForeignKey('element.id'), nullable=False)
    element_type = db.Column(db.String(10), nullable=False)  # 'event' or 'item'
    family_member_id = db.Column(db.Integer, db.ForeignKey('family_member.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # For easy lookup
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    family_member = db.relationship('FamilyMember', backref='lottery_entries')
    user = db.relationship('User', backref='lottery_entries')
```

Note: We use polymorphic element references (element_id + element_type) since elements can be Events or Items.

## UI Components

### List Creation Form

- Add checkbox: "Enable lottery for this list"
- If checked, show datetime picker: "Lottery will run on:"
- Display timezone clearly: "Times are in your timezone: [timezone]"
- Show info text: "Note: Lottery cannot be disabled once list is created. The lottery will run within 1 hour after the selected time."
- Validate datetime is at least 1 hour in the future
- Show validation error if datetime is too soon: "Lottery time must be at least 1 hour from now"

### List Editor View (Lottery Lists)

- Prominently display: "LOTTERY LIST"
- Show lottery datetime with edit option (must stay in future)
- Show lottery status:
  - "Lottery scheduled for [datetime] in [timezone]"
  - "Lottery in progress..." (if running)
  - "Lottery completed on [datetime]" (if done)
- Show lottery entries for each element (similar to signup display)
- If lottery not yet run: show count of entries per element
- If lottery completed: show normal signup management

### Public List View (Before Lottery)

- Clear banner at top: "🎲 This is a LOTTERY LIST"
- Display lottery datetime prominently: "Lottery runs on [date/time] [timezone]"
- Info text: "The lottery will run within 1 hour after this time. Winners will be notified by email."
- For each element:
  - "Enter Lottery" button (instead of "Sign Up")
  - Show entries: "X entries" with list of who entered
  - If user entered: show "You entered: [family member names]" with option to remove
- No "spots remaining" display (since lottery is random)

### Public List View (During Lottery)

- Banner: "⏳ Lottery in Progress"
- Message: "The lottery is currently running. Please check back in a few minutes."
- Disable all actions

### Public List View (After Lottery)

- Normal list view
- Show signups (with pending acceptance status)
- Available spots show "Sign Up" button (first-come-first-served)
- Waitlist operates normally (if enabled)

### Entry Management

- Simple way to remove lottery entries before lottery runs
- Similar UI to canceling signups
- Can remove entries for any family member

## Implementation Phases

### Phase 1: Database Models & Basic Setup

- [ ] Add `is_lottery`, `lottery_datetime`, `lottery_timezone`, `lottery_completed` to `SignupList`
- [ ] Create `LotteryEntry` model
- [ ] Create database migration
- [ ] Add validation helpers (lottery datetime must be at least 1 hour in future, accounting for timezone)

### Phase 2: List Creation with Lottery Option

- [ ] Update list creation form to include lottery option
- [ ] Add datetime picker for lottery datetime
- [ ] Display and store creator's timezone
- [ ] Validate lottery datetime is at least 1 hour in future (both client-side and server-side)
- [ ] Convert times to UTC properly accounting for creator's timezone
- [ ] Prevent editing `is_lottery` after creation

### Phase 3: Lottery Entry UI (Public View)

- [ ] Update public list view to detect lottery lists
- [ ] Show lottery banner and datetime
- [ ] Replace "Sign Up" with "Enter Lottery" buttons
- [ ] Create lottery entry form (select family members)
- [ ] Display lottery entries (who has entered)
- [ ] Add remove entry functionality

### Phase 4: Lottery Entry Backend

- [ ] Create route for entering lottery
- [ ] Validation: list must be lottery list, lottery not yet run
- [ ] Create `LotteryEntry` records
- [ ] Create route for removing lottery entries
- [ ] Handle multiple family members per element

### Phase 5: List Editor View for Lotteries

- [ ] Update editor view to show lottery status
- [ ] Display lottery entries per element
- [ ] Add ability to edit lottery datetime (validate at least 1 hour in future)
- [ ] Show entry counts and participant lists

### Phase 6: Lottery Execution Algorithm

- [ ] Create command/task for running lotteries
- [ ] Implement lottery selection algorithm:
  - Process elements in correct order
  - Random selection per element
  - Apply list limits
  - Create pending signups for winners
  - Randomly order waitlist (if enabled)
- [ ] Mark lottery as completed
- [ ] Add logging for lottery execution

### Phase 7: Automated Lottery Scheduling

- [ ] Create Heroku Scheduler command
- [ ] Add to scheduled jobs (hourly)
- [ ] Look for lotteries in past 65 minutes
- [ ] Execute and mark complete
- [ ] Handle errors gracefully

### Phase 8: Winner Acceptance Flow

- [ ] Extend existing pending signup acceptance to handle lottery winners
- [ ] Generate acceptance links (already exists for waitlist)
- [ ] 24-hour timeout (already exists for waitlist)
- [ ] Handle acceptance and rejection
- [ ] Move to next person on waitlist if rejected/timeout

### Phase 9: Email Notifications

- [ ] Create lottery completion email template (participants)
- [ ] Include won spots, waitlist positions, losses
- [ ] Include acceptance links with 24-hour deadline
- [ ] Create lottery completion email template (creator)
- [ ] Send emails after lottery completes

### Phase 10: During-Lottery State Handling

- [ ] Add flag or state tracking for "lottery in progress"
- [ ] Update UI to show "in progress" message
- [ ] Block all actions during execution
- [ ] Clear state when lottery completes

### Phase 11: Post-Lottery Behavior

- [ ] After lottery completes, allow regular signups for unfilled spots
- [ ] Ensure waitlist operates normally
- [ ] Ensure all existing features work (cancellation, etc.)
- [ ] Display lottery completion status clearly

### Phase 12: Testing & Edge Cases

- [ ] Test under-subscribed lotteries
- [ ] Test with list limits enabled
- [ ] Test with waitlists enabled
- [ ] Test editing elements/spots after entries
- [ ] Test changing lottery datetime
- [ ] Test timezone display for different users
- [ ] Test email notifications
- [ ] Test acceptance flow
- [ ] Test concurrent lottery execution (multiple lists)

## Key Design Decisions

1. **Lottery is permanent**: Once enabled, cannot be disabled. This prevents gaming the system.

2. **Timezone clarity**: Always display creator's timezone to avoid confusion.

3. **Transparency**: Users can see all entries, fostering trust in the random selection.

4. **Acceptance required**: Winners must actively accept spots, preventing no-shows.

5. **List limits respected**: Ensures fair distribution across all elements.

6. **Waitlist randomization**: If using waitlists, order is also randomized (not first-to-enter).

7. **Post-lottery flexibility**: After lottery, normal operations resume, allowing organic signup for remaining spots.

8. **Creator control maintained**: Creators can still edit elements even after entries are made.

## Open Questions / Future Considerations

1. Should creators get a notification when someone enters the lottery?

2. Should there be an upper limit on how far in the future a lottery can be scheduled?

3. Should lottery entries be allowed to have comments/notes (like regular signups sometimes do)?

4. Analytics: Track lottery statistics (number of entries vs spots, acceptance rates, etc.)?

## Dependencies

- Existing waitlist system (for post-lottery waitlist handling)
- Existing list limits system (for applying limits during lottery)
- Existing pending signup acceptance flow (for winner acceptance)
- Email notification system
- Heroku Scheduler (for automated lottery execution)
