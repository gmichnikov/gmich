# List Views PRD

## Overview
Track and display lists that users have recently viewed, helping them quickly return to lists they're interested in. This creates a personalized navigation experience showing the user's list viewing history.

## Requirements

### Core Functionality
1. **View Tracking**
   - Record when a user views a list detail page (not previews/modals)
   - Store: list_id, user_id, last_viewed_at timestamp
   - Update existing record if user re-views a list (overwrite timestamp)
   - Keep only the 50 most recently viewed lists per user

2. **Display Page**
   - Dedicated "Recently Viewed Lists" page accessible from Better Signups navigation
   - Show most recently viewed first (sorted by last_viewed_at DESC)
   - Display for each list:
     - List name
     - Creator name
     - Last viewed date (formatted as "2 days ago", "Just now", etc.)
     - Summary counts for user's family members on that list:
       - Active signups
       - Waitlist entries
       - Lottery entries
   - Link to the list (using UUID)

3. **Data Scope**
   - Track views for ANY list the user can access (whether they're the owner/editor or not)
   - Summary counts show only the current user's family member activity on each list
   - No tracking of who else viewed a list (privacy)

### Database Schema
New table: `ListView`
- `id` (Integer, primary key)
- `user_id` (Integer, foreign key to User)
- `list_id` (Integer, foreign key to SignupList)
- `last_viewed_at` (DateTime, indexed for sorting)
- Unique constraint on (user_id, list_id)

### User Experience
- Access via navigation link: "Recently Viewed" or "My Lists"
- Empty state message when no lists viewed yet
- Clicking a list navigates to the list detail page (handles passwords if needed)
- Show up to 50 lists, automatically pruning older entries

### Technical Notes
- Track view on list detail page load (both public and editor views)
- Use upsert pattern: update timestamp if record exists, create if not
- Cleanup: when user has >50 viewed lists, delete oldest entries
- Summary counts calculated on-the-fly via joins to Signup, WaitlistEntry, LotteryEntry tables
- Handle deleted lists gracefully (show "List deleted" or filter out)

## Out of Scope (Future Considerations)
- Filtering/search within viewed lists
- Categorizing lists (favorites, archived, etc.)
- Viewing history beyond 50 lists
- Tracking view counts (# of times viewed)
- List previews/thumbnails

## Implementation Plan

### Phase 1: Database and Model
- Create `ListView` model in models.py
- Generate migration for new table
- Add relationship to User and SignupList models
- Add method to record/update view

### Phase 2: View Tracking
- Add view tracking to list detail route (public view)
- Add view tracking to list editor route
- Implement automatic cleanup (keep only 50 most recent per user)
- Test that views are recorded and timestamps updated correctly

### Phase 3: Display Page
- Create route for "Recently Viewed Lists" page
- Create template showing viewed lists with all required info
- Calculate summary counts (signups, waitlist, lottery) per list
- Add navigation link from Better Signups home page
- Handle edge cases (deleted lists, password-protected lists)

### Phase 4: Testing and Polish
- Test view recording across different list types
- Test with multiple users viewing same/different lists
- Verify 50-list limit and cleanup
- Test summary counts with various signup states
- Verify performance with many viewed lists
- Add proper error handling and user feedback

## Success Metrics
- Users can quickly return to lists they've previously accessed
- No performance degradation when tracking views
- Accurate summary counts for user's family activity
