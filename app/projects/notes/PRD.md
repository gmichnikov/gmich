# Notes Project - Product Requirements Document

## Overview
A lightweight, personal notes application with markdown support, archiving, and search functionality. All notes are private to the logged-in user.

## Core Features (V1)

### 1. Note Management

#### Note Structure
- **Title**: Required field for each note
- **Content**: Markdown-formatted text
- **Archive Status**: Boolean field `is_archived`
- **Timestamps**:
  - `created_at`: When the note was first created
  - `modified_at`: Last time content was edited

#### Modes
- **View Mode**: Rendered markdown display
- **Edit Mode**: Plain text markdown editor with manual save button
- **No live preview**: User switches between view and edit modes

### 2. Main Page (Notes List)

#### Display
- Table/list showing:
  - Note title (clickable - goes to view page)
  - Date created
  - Date modified
- **Sorting**: By date modified (most recent first)
- **Default view**: Shows only active notes (excludes archived)
- **Search bar**: Single input field for searching note titles
- **New Note button**: Prominently displayed
- **Link to archived notes view**: Access archived notes separately

#### Empty State
- If no notes exist, display message: "No notes yet. Create your first note!"

### 3. Search

#### Main Page Search
- **Search bar**: Single input field on main page
- **Default behavior**: Search note titles only
- **Action**: Submitting search navigates to dedicated search results page
- **Empty input**: Search button is disabled when input is empty
- **Search scope**: Only searches active notes (archived notes are excluded from search)

#### Search Results Page
- **Display**: Similar to main page - table/list of matching notes
- **Sorting**: By date modified (most recent first)
- **Search scope dropdown**: Toggle between:
  - "Title" (default)
  - "Content" (searches full note body)
  - When changed, auto-submits and preserves current query
- **Matching**: Case-insensitive string matching
- **Results**: Only includes active notes (archived notes not included)
- **Empty results**: "No notes found matching '[query]'"
- **Navigation**: "Back to Notes" link returns to main page

### 4. Saving (Manual + Autosave)

#### Manual Save
- **Save button**: Always visible in edit mode
- **Action**: Saves note and remains on edit page
- **Feedback**: Flash message or indicator showing "Saved"

#### Autosave
- **Trigger**: Automatically saves when user stops typing in either title or content field
- **Debounce timing**: Saves after 3 seconds of inactivity (no keystrokes)
  - Timer resets with each keystroke in either field
  - Only fires after user pauses typing
- **Empty title handling**: If title is empty when autosave triggers, skip the save silently (don't show error)
- **Mechanism**: Background AJAX request without page reload
- **Indicator**: Visual feedback showing save status
  - "Saving..." while request in progress
  - "Saved" when complete
  - "Unsaved changes" if there are pending changes
- **Behavior**: Works silently alongside manual save button
- **Navigation**: No browser warnings - trust that autosave is fast enough
  - Accept that in rare edge cases (close tab 1 second after typing), content might be lost
  - Trade-off for seamless, no-friction experience

### 5. Deletion & Archiving

#### Archive
- **Implementation**: Boolean field `is_archived` on Note model
- **Behavior**: Archived notes are hidden from main list by default
- **Archived Notes View**: Separate page at `/notes/archived` showing only archived notes
- **Archive action**: Available on view page (button/link)
- **Unarchive action**: Available when viewing an archived note or from archived notes list

#### Delete
- **Permanence**: Complete deletion from database (no trash/recovery)
- **Confirmation**: JavaScript confirmation prompt before deleting
- **Location**: Delete button available on view page

### 6. Privacy & Security

- **User isolation**: All notes are private to the user who created them
- **Authentication**: Login required for all note operations
- **Authorization**: Users can only access their own notes

### 7. Markdown Support

- **Library**: Use any simple, reliable Python markdown library (e.g., `python-markdown` or `mistune`)
- **Features needed**:
  - Basic markdown (headers, lists, bold, italic, links)
  - Code blocks (with syntax highlighting optional)
  - Tables
- **Sanitization**: Sanitize rendered HTML to prevent XSS attacks

### 8. Mobile Responsiveness

- **Priority**: Must be easy to use on mobile phones
- **Requirements**:
  - Touch-friendly UI elements (buttons, links)
  - Responsive table/list layout (consider card view on small screens)
  - Large textarea for editing
  - Easy switching between view/edit modes
  - Readable text sizes (minimum 16px to prevent auto-zoom on iOS)
  - Navigation that works on small screens

## Data Model (V1)

### Note Table
```python
class Note(db.Model):
    __tablename__ = 'note'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default='')
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    modified_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationship to User
    user = db.relationship('User', backref='notes')
```

**Constraints:**
- `title` is required (cannot be empty)
- `user_id` is required (foreign key to User table)
- All notes belong to exactly one user

**Indexes:**
- Create composite index on `(user_id, is_archived, modified_at)` for efficient list queries
- Create index on `(user_id, modified_at)` for general queries

**Timestamp Behavior:**
- `modified_at` updates only when title or content changes
- `modified_at` does NOT update when archiving/unarchiving
- Manually set `modified_at = datetime.utcnow()` in save/autosave handlers (do not rely on SQLAlchemy's `onupdate`)

## Pages & Routes (V1)

### Main Routes
- `GET /notes/` - Main page: list of active notes (excluding archived)
- `GET /notes/archived` - List of archived notes only
- `GET /notes/new` - Show form to enter new note title
- `POST /notes/create` - Create new note in DB, redirect to edit page
- `GET /notes/<id>` - View note (rendered markdown)
- `GET /notes/<id>/edit` - Edit note (markdown editor)
- `POST /notes/<id>/save` - Save note (manual save button)
- `POST /notes/<id>/delete` - Permanently delete note
- `POST /notes/<id>/archive` - Archive note (sets is_archived=True)
- `POST /notes/<id>/unarchive` - Unarchive note (sets is_archived=False)
- `GET /notes/search` - Search results page (accepts `?q=query&scope=title|content`)

### API Routes (for autosave)
- `POST /notes/api/<id>/autosave` - Autosave endpoint (AJAX only)
  - Accepts JSON: `{"title": "...", "content": "..."}`
  - Returns JSON: `{"status": "success", "modified_at": "..."}`

## UI/UX Considerations (V1)

### Main Page (`/notes/`)
- **Header**: "My Notes"
- **Search bar**: Single input at top with "Search" button
  - Button is disabled when input is empty
- **New Note button**: Prominently displayed (top right or near search)
- **Table/List view**: Shows for each note:
  - Title (clickable - goes to view page)
  - Content preview (first 100 characters, truncated with "...")
  - Date created
  - Date modified
  - No quick action buttons - user must click through to view page first (simpler for v1)
- **Link to archived notes**: "View Archived Notes" link
- **Empty state**: If no notes, show friendly message "No notes yet. Create your first note!"

### New Note Page (`/notes/new`)
- **Form**: Single input field for note title
- **Validation**: Title is required (cannot be empty)
  - Show error message if user tries to submit empty title
- **Actions**:
  - "Create Note" button (submits form, creates note, goes to edit page)
  - "Cancel" button (returns to main list)

### View Page (`/notes/<id>`)
- **Display**:
  - Title prominently displayed
  - Rendered markdown content
  - Timestamps: "Created: [date]" and "Last modified: [date]"
- **Actions** (buttons/links):
  - "Edit" button (goes to edit page) - available even for archived notes
  - "Archive" button (archives note, redirects to archived notes view)
    - Only shown if note is not archived
  - "Unarchive" button (unarchives note, redirects to main notes list)
    - Only shown if note is archived
  - "Delete" button (shows confirmation, then deletes and redirects to main list)
    - Confirmation message: "Are you sure you want to permanently delete this note? This action cannot be undone."
    - Always returns to main notes list after deletion
  - "Back to Notes" link (always returns to main notes list)

### Edit Page (`/notes/<id>/edit`)
- **Title input field**: Editable text input
  - **Validation**: Cannot be empty
  - If user tries to save with empty title, show error message
- **Markdown textarea**: Large textarea for content editing
  - Can be empty (notes with just a title are valid)
- **Autosave indicator**: Shows "Saved", "Saving...", or "Unsaved changes"
- **Actions**:
  - "Save" button (manual save, validates title, stays on edit page)
  - "View Note" button (goes to view page)
  - "Back to Notes" link
- **Keyboard shortcut**: Ctrl+S (Windows/Linux) or Cmd+S (Mac) triggers manual save
  - Prevents browser's default "Save Page" dialog
  - Same behavior as clicking Save button
- **Autosave**: Runs automatically in background
- **Archived notes**: Can be edited while archived (is_archived remains true)

### Archived Notes Page (`/notes/archived`)
- **Header**: "Archived Notes"
- **Display**: Similar to main page but shows only archived notes
  - Same table format with title, preview, dates
  - No quick action buttons (consistent with main page)
- **Unarchive action**: Available on view page only (click through to view archived note first)
- **Link back**: "Back to Active Notes" (returns to main list)
- **Empty state**: If no archived notes, show "No archived notes. Archive a note to see it here."

### Search Results Page (`/notes/search`)
- **Search input**: Pre-filled with current query, can modify and re-search
- **Scope dropdown**: Toggle between "Title" and "Content"
  - Auto-submits search when changed (no need to click Search again)
  - Preserves current query when switching scope
- **Results**: Table/list similar to main page
  - Shows title, content preview, dates
  - Only includes active notes (archived excluded)
  - Sorted by date modified (most recent first)
- **Empty results**: "No notes found matching '[query]'"
- **Back link**: "Back to Notes" (returns to main notes list)

### Mobile Optimizations
- **Responsive layout**: Stack elements vertically on small screens
- **Card view on mobile**: Instead of table, use cards for better mobile UX
- **Large touch targets**: Minimum 44x44px for buttons
- **Large textarea**: Full width, tall enough for comfortable editing
- **Readable text**: 16px minimum font size

## Design Decisions & Clarifications

### Title Validation
- **New note creation**: Title is required, show error if empty
- **During edit**: Cannot save with empty title, show validation error
- **Empty content**: OK - notes can have title with no content
- **Markdown in titles**: Titles are treated as plain text only (no markdown rendering)
- **HTML escaping**: Escape HTML characters in titles for security

### Autosave Strategy
- **Approach**: Trust the autosave (no browser warnings)
- **Trade-off**: Accept rare data loss (close tab 1 second after typing) for seamless UX
- **Manual save**: Always available as backup

### Navigation After Actions
- **After Archive**: Redirect to archived notes view (so user sees it worked)
- **After Unarchive**: Redirect to main notes list
- **After Delete**: Always redirect to main notes list (simplified - no context tracking)
- **After Create**: Redirect to edit page for new note
- **"Back to Notes" links**: Always go to main notes list (no context awareness needed)

### Archived Notes Behavior
- **Editing**: Can edit archived notes (is_archived stays true)
- **Visibility**: Hidden from main list, visible in separate archived view
- **Actions**: Can view, edit, unarchive, or delete archived notes

### Date Display
- **Format**: Always use absolute datetime format: "Jan 23, 2026 3:45 PM"
- **Timezone handling**:
  - Store all timestamps in UTC in the database
  - Convert to user's timezone for display (from user profile `timezone` field)
  - Use Python's `pytz` or `zoneinfo` for timezone conversion
- **Display format**: `%b %-d, %Y %-I:%M %p` (e.g., "Jan 23, 2026 3:45 PM")

### Search Behavior
- **Scope**: Only searches active notes (archived notes are excluded)
- **Empty input**: Search button is disabled when input is empty
- **Scope dropdown**: Auto-submit when changed, preserving current query
- **Results sorting**: Always by modified date descending
- **Empty results**: Clear message with the search query displayed
- **Query preservation**: When changing scope, preserve and re-search with same query

### Empty Notes
- **After creation**: Note exists in DB with title and empty content
- **If never edited**: Keep the note (it has a title, just no content)
- **No orphan cleanup**: Don't delete empty notes automatically

### Content Preview
- **Location**: Show on main page, archived page, and search results
- **Length**: First 100 characters of note content (raw markdown, not rendered)
- **Truncation**: Add "..." if content exceeds 100 characters
- **Empty content**: Show "(empty)" if note has no content

### Timestamp Updates
- **modified_at updates when**:
  - Title is changed
  - Content is changed
- **modified_at does NOT update when**:
  - Note is archived
  - Note is unarchived
  - Note is only viewed (no edits)

### Quick Actions
- **V1 decision**: No quick action buttons on main list
- **Rationale**: Simpler UI, prevents accidental actions
- **User flow**: Click title → view page → choose action

## Technical Considerations (V1)

### Autosave Implementation
- **JavaScript**: Debounced function triggers on keyup/input events
  - Monitors both title input and content textarea
  - Timer resets on each keystroke in either field
  - Only fires after user stops typing
  - If title is empty, skip the autosave request entirely
- **Debounce timing**: Exactly 3 seconds of no typing activity
- **AJAX**: POST to `/notes/api/<id>/autosave` with JSON payload
- **CSRF for AJAX**: Include CSRF token in request header
  - Add meta tag to base template: `<meta name="csrf-token" content="{{ csrf_token() }}">`
  - JavaScript reads token and sends as `X-CSRFToken` header with fetch request
- **Visual indicator**: Update DOM element to show "Saving..." then "Saved"
- **Error handling**:
  - If autosave fails, show error indicator (no auto-retry)
  - Keep "Unsaved changes" indicator visible
  - Next keystroke resets debounce timer, triggering new autosave attempt
  - Error clears automatically on next successful save
  - Manual save button always available as fallback
- **No beforeunload warnings**: Keep it simple, trust that 3 second debounce is fast enough
- **Manual save**: Always available for users who want explicit control

### Markdown Rendering
- **Server-side rendering**: Use Python markdown library
- **Recommended library**: `python-markdown` (already used in the app for Ask Many LLMs)
- **Extensions**: Enable fenced code blocks, tables
- **Sanitization**: Render markdown to HTML safely (avoid XSS)

### Search Implementation
- **Query type**: SQL `ILIKE` for case-insensitive pattern matching
- **Title search**: `WHERE title ILIKE '%query%'`
- **Content search**: `WHERE content ILIKE '%query%'`
- **Filter by user**: Always include `AND user_id = current_user.id`
- **Sorting**: Results sorted by `modified_at DESC`

### Form Handling
- **CSRF protection**: Use Flask-WTF CSRF tokens on all forms
- **Validation**:
  - Title is required (cannot be empty)
  - Content can be empty
- **Flash message categories**:
  - Success (green): "Note saved", "Note deleted", "Note archived", "Note unarchived"
  - Error (red): "Title cannot be empty", "Note not found", "You do not have permission"
  - Info (blue): General informational messages
- **Date formatting**:
  - Always use absolute datetime: "Jan 23, 2026 3:45 PM" (format: `%b %-d, %Y %-I:%M %p`)
  - Convert from UTC to user's timezone (from user profile)
  - Use a template filter or helper function for consistent formatting

### Error Handling
- **Non-existent note**: Return 404, flash "Note not found", redirect to main list
- **Unauthorized access**: If note belongs to another user, return 404 (don't reveal existence)
- **Empty title submission**: Show validation error, stay on current page
- **Manual save failure**: Flash error message "Failed to save note. Please try again."
- **Autosave failure**: Show persistent error indicator, keep unsaved changes state
- **Network errors**: Graceful degradation - manual save always available

### Authorization
- **Every route**: Use `@login_required` decorator
- **Data access**: Filter all queries by `current_user.id`
- **Direct access prevention**: When accessing note by ID, verify `note.user_id == current_user.id`

## Known Limitations (V1)

### Edge Cases Accepted for V1

1. **Session Timeout During Editing**
   - If user session expires while editing, autosave will fail
   - User will need to log in again
   - Unsaved work may be lost
   - Mitigation: Manual save button available before timeout

2. **Concurrent Editing**
   - If same note is edited in multiple browser tabs/devices simultaneously
   - Last write wins (no conflict resolution)
   - Earlier changes may be overwritten
   - Mitigation: Not a common use case for personal notes app

3. **Rare Autosave Data Loss**
   - If user closes tab within 3 seconds of typing
   - Content typed in that window may be lost
   - Trade-off accepted for seamless UX
   - Mitigation: Manual save button always available

4. **Content Preview Limitations**
   - Preview shows raw markdown (not rendered)
   - First 100 chars may cut mid-word or mid-markdown syntax
   - Acceptable for V1 - just a preview

5. **Search Does Not Include Archived Notes**
   - Archived notes are excluded from all searches
   - If user wants to find archived note, must browse archived list
   - Could add to V2+ if needed

## Out of Scope - Future Enhancements

### Possible V2+ Features
- **Tags**: Add, remove, and filter notes by tags
  - Many-to-many relationship between notes and tags
  - Tag management UI (add/remove from edit page)
  - Filter notes by tag on main page
  - Tag autocomplete
- **Dark Mode**: Toggle between light/dark themes with persistence
- **Last Accessed Timestamp**: Track when note was last viewed
- **Pagination**: If note list grows large (>100 notes)
- **Note size limits**: Enforce max title length or content size
- **Version history**: Track changes over time
- **Note sharing/collaboration**: Share notes with other users
- **Rich text editor (WYSIWYG)**: Alternative to markdown editing
- **File attachments**: Upload and embed files in notes
- **Nested tags or tag hierarchies**: Organize tags in groups
- **Multiple tag filtering**: AND/OR logic for complex filters
- **Note templates**: Pre-filled note structures
- **Export/import**: Download notes as markdown/JSON files
- **Folder/notebook organization**: Group notes into folders
- **Full-text search**: Better performance for large content searches

## Success Criteria (V1)

1. ✅ User can create, edit, view, and delete notes
2. ✅ Manual save works correctly
3. ✅ Autosave works reliably without data loss
4. ✅ Search returns relevant results (both title and content search)
5. ✅ Archive/unarchive functionality works as expected
6. ✅ Mobile experience is smooth and usable
7. ✅ Notes are properly isolated between users (security)
8. ✅ Markdown rendering works correctly
9. ✅ All timestamps (created, modified) are accurate

## Implementation Plan

### Phase 1: Core CRUD (MVP)
1. Create database models (Note table)
2. Set up routes and basic views
3. Main page: list notes (title, dates, sorted by modified)
4. New note flow: form to enter title → create → redirect to edit
5. View page: display note with rendered markdown
6. Edit page: edit title and content with manual save button
7. Delete functionality with confirmation

**Deliverable**: Basic working notes app with manual save

### Phase 2: Search & Archive
1. Search bar on main page
2. Search results page with title/content toggle
3. Archive/unarchive functionality
4. Archived notes view
5. Update main page to hide archived notes by default

**Deliverable**: Full CRUD with search and archive

### Phase 3: Autosave & Polish
1. Implement autosave with debouncing
2. Visual indicators for save status
3. Mobile responsiveness (card view, large touch targets)
4. UI/UX improvements
5. Error handling and edge cases

**Deliverable**: Production-ready V1

## Notes for Implementation

- Follow existing project conventions in the gmich app
- Use existing base template and CSS styles
- Leverage Flask-Login for authentication
- Use Flask-SQLAlchemy for database models
- Follow the pattern from basketball_tracker or better_signups projects
- Add routes to `/notes` with `@login_required` decorator
- Filter all queries by `current_user.id`
