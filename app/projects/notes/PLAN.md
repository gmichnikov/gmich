# Notes Project - Implementation Plan

This plan follows the PRD phases but breaks them into smaller, testable chunks.

---

## Phase 1: Core CRUD (MVP)

### 1.1 Database Model Setup

- [x] Create `Note` model in `app/projects/notes/models.py`
  - [x] Define all fields: `id`, `user_id`, `title`, `content`, `is_archived`, `created_at`, `modified_at`
  - [x] Add foreign key relationship to User model
  - [x] Set appropriate defaults (`content=''`, `is_archived=False`)
  - [x] Add `__repr__` method for debugging
- [x] Create database migration
  - [x] Generate migration file with `flask db migrate`
  - [x] Review migration file for correctness
  - [x] Run migration with `flask db upgrade`
- [x] Add indexes for query optimization
  - [x] Composite index on `(user_id, is_archived, modified_at)`
  - [x] Index on `(user_id, modified_at)`

**Manual Testing 1.1:**
- [x] Verify table exists in database
- [x] Verify all columns have correct types and constraints
- [x] Verify indexes are created

---

### 1.2 Blueprint and Route Structure

- [x] Create notes blueprint in `app/projects/notes/__init__.py`
  - [x] Initialize blueprint with url_prefix `/notes`
  - [x] Register blueprint in main app
- [x] Create `routes.py` with placeholder routes
  - [x] `GET /notes/` - list notes (placeholder)
  - [x] `GET /notes/new` - new note form (placeholder)
  - [x] `POST /notes/create` - create note (placeholder)
  - [x] `GET /notes/<id>` - view note (placeholder)
  - [x] `GET /notes/<id>/edit` - edit note (placeholder)
  - [x] `POST /notes/<id>/save` - save note (placeholder)
  - [x] `POST /notes/<id>/delete` - delete note (placeholder)
- [x] Add `@login_required` decorator to all routes
- [x] Create empty templates directory structure

**Manual Testing 1.2:**
- [x] Verify `/notes/` route loads (even if empty)
- [x] Verify unauthenticated users are redirected to login
- [x] Verify 404 for non-existent routes

---

### 1.3 Helper Functions

- [x] Create helper function to get note by ID with authorization check
  - [x] Return 404 if note doesn't exist
  - [x] Return 404 if note belongs to different user (don't reveal existence)
- [x] Create date formatting helper/template filter
  - [x] Convert UTC to user's timezone
  - [x] Format as "Jan 23, 2026 3:45 PM"
  - [x] Register as Jinja filter
- [x] Create content preview helper
  - [x] Truncate to 100 characters
  - [x] Add "..." if truncated
  - [x] Return "(empty)" if no content

**Manual Testing 1.3:**
- [x] Test date formatting with various timezones
- [x] Test content preview with short, long, and empty content

---

### 1.4 Main Page - Notes List

- [x] Implement `GET /notes/` route
  - [x] Query active notes (is_archived=False) for current user
  - [x] Order by modified_at DESC
- [x] Create `notes/index.html` template
  - [x] Page header "My Notes"
  - [x] "New Note" button (link to /notes/new)
  - [x] Search bar with input and disabled-when-empty button (functionality in Phase 2)
  - [x] "View Archived Notes" link
  - [x] Table/list displaying notes:
    - [x] Title (clickable link to view page)
    - [x] Content preview (100 chars)
    - [x] Date created
    - [x] Date modified
  - [x] Empty state message when no notes exist

**Manual Testing 1.4:**
- [x] Page loads without errors when logged in
- [x] Empty state shows when user has no notes
- [x] New Note button links to correct URL
- [x] Archived notes link present

---

### 1.5 New Note Page

- [x] Implement `GET /notes/new` route
  - [x] Render form template
- [x] Implement `POST /notes/create` route
  - [x] Validate title is not empty
  - [x] Create new Note in database
  - [x] Set created_at and modified_at to current UTC time
  - [x] Redirect to edit page for new note
- [x] Create `notes/new.html` template
  - [x] Title input field (required)
  - [x] "Create Note" submit button
  - [x] "Cancel" button (returns to main list)
  - [x] Validation error display for empty title

**Manual Testing 1.5:**
- [x] Form displays correctly
- [x] Submitting empty title shows error, stays on page
- [x] Submitting valid title creates note and redirects to edit page
- [x] Cancel button returns to main list
- [x] New note appears in main list

---

### 1.6 View Page

- [x] Implement `GET /notes/<id>` route
  - [x] Use authorization helper to get note
  - [x] Render markdown content to HTML
  - [x] Sanitize HTML output for XSS prevention
- [x] Create `notes/view.html` template
  - [x] Display title prominently
  - [x] Display rendered markdown content
  - [x] Display "Created: [date]" and "Last modified: [date]"
  - [x] "Edit" button (links to edit page) - available for both active and archived notes
  - [x] "Archive" button (only if not archived) - placeholder for Phase 2
  - [x] "Unarchive" button (only if archived) - placeholder for Phase 2
  - [x] "Delete" button with JS confirmation
  - [x] "Back to Notes" link

**Manual Testing 1.6:**
- [x] Note displays with correct title and content
- [x] Markdown renders correctly (headers, bold, lists, code blocks)
- [x] Dates display in correct format and timezone
- [x] Edit button links to edit page
- [x] Back to Notes returns to main list
- [x] Accessing another user's note returns 404
- [x] Accessing non-existent note ID returns 404

---

### 1.7 Edit Page with Manual Save

- [x] Implement `GET /notes/<id>/edit` route
  - [x] Use authorization helper to get note
  - [x] Render edit form with current values
- [x] Implement `POST /notes/<id>/save` route
  - [x] Validate title is not empty
  - [x] Update title and content
  - [x] Update modified_at timestamp (only if title or content actually changed)
  - [x] Flash success message
  - [x] Redirect back to edit page
- [x] Create `notes/edit.html` template
  - [x] Title input field (required, pre-filled)
  - [x] Large textarea for content (pre-filled)
  - [x] "Save" button
  - [x] "Save & View" button (saves then views)
  - [x] "Back to Notes" link
  - [x] Validation error display for empty title
  - [x] Placeholder for autosave indicator (Phase 3)
- [x] Implement Ctrl+S / Cmd+S keyboard shortcut
  - [x] Prevent browser default save dialog
  - [x] Submit form on keypress

**Manual Testing 1.7:**
- [x] Edit page loads with current note data
- [x] Saving with empty title shows error, stays on page
- [x] Saving valid changes updates note and shows success message
- [x] modified_at timestamp updates after save
- [x] Ctrl+S triggers save (Windows/Linux)
- [x] Cmd+S triggers save (Mac)
- [x] Save & View button saves then shows view page
- [x] Back to Notes returns to main list

---

### 1.8 Delete Functionality

- [x] Implement `POST /notes/<id>/delete` route
  - [x] Use authorization helper to get note
  - [x] Delete note from database
  - [x] Flash success message
  - [x] Redirect to main notes list
- [x] Add JavaScript confirmation to delete button on view page
  - [x] Confirmation message: "Are you sure you want to permanently delete this note? This action cannot be undone."
  - [x] Only proceed if user confirms

**Manual Testing 1.8:**
- [x] Delete button shows confirmation dialog
- [x] Canceling confirmation does not delete note
- [x] Confirming deletion removes note from database
- [x] After deletion, redirected to main list with success message
- [x] Deleted note no longer appears in list

---

## Phase 2: Search & Archive

### 2.1 Archive/Unarchive Functionality

- [x] Implement `POST /notes/<id>/archive` route
  - [x] Set is_archived=True (do NOT update modified_at)
  - [x] Flash success message
  - [x] Redirect to archived notes view
- [x] Implement `POST /notes/<id>/unarchive` route
  - [x] Set is_archived=False (do NOT update modified_at)
  - [x] Flash success message
  - [x] Redirect to main notes list
- [x] Update view page template
  - [x] Show "Archive" button only for active notes
  - [x] Show "Unarchive" button only for archived notes

**Manual Testing 2.1:**
- [x] Archive button sets is_archived=True
- [x] After archiving, redirected to archived view
- [x] Archived note no longer appears in main list
- [x] Unarchive button sets is_archived=False
- [x] After unarchiving, redirected to main list
- [x] modified_at is NOT changed by archive/unarchive

---

### 2.2 Archived Notes Page

- [x] Implement `GET /notes/archived` route
  - [x] Query only archived notes (is_archived=True) for current user
  - [x] Order by modified_at DESC
- [x] Create `notes/archived.html` template
  - [x] Page header "Archived Notes"
  - [x] Same table format as main page
  - [x] "Back to Active Notes" link
  - [x] Empty state: "No archived notes. Archive a note to see it here."

**Manual Testing 2.2:**
- [x] Archived notes page shows only archived notes
- [x] Empty state displays when no archived notes
- [x] Notes are sorted by modified_at DESC
- [x] Clicking note title goes to view page
- [x] Can view, edit, and delete archived notes
- [x] Back to Active Notes link works

---

### 2.3 Search - Main Page Integration

- [x] Update main page search bar
  - [x] Form submits to `/notes/search` with GET
  - [x] Search button disabled when input is empty (JavaScript)
  - [x] Pass query as `?q=` parameter

**Manual Testing 2.3:**
- [x] Search button is disabled when input is empty
- [x] Search button enables when text is entered
- [x] Submitting search navigates to search results page with query in URL

---

### 2.4 Search Results Page

- [x] Implement `GET /notes/search` route
  - [x] Accept `q` (query) and `scope` (title/content) parameters
  - [x] Default scope to "title"
  - [x] Perform case-insensitive search (ILIKE)
  - [x] Filter to active notes only (is_archived=False)
  - [x] Filter by current user
  - [x] Order by modified_at DESC
- [x] Create `notes/search.html` template
  - [x] Search input pre-filled with current query
  - [x] Scope dropdown (Title / Content)
  - [x] Auto-submit on scope change (JavaScript)
  - [x] Results table (same format as main page)
  - [x] Empty results message: "No notes found matching '[query]'"
  - [x] "Back to Notes" link

**Manual Testing 2.4:**
- [x] Title search finds notes with matching titles
- [x] Content search finds notes with matching content
- [x] Search is case-insensitive
- [x] Archived notes are NOT included in results
- [x] Changing scope dropdown re-submits with same query
- [x] Empty results show appropriate message
- [x] Results sorted by modified_at DESC
- [x] Other users' notes are not included

---

## Phase 3: Autosave & Polish

### 3.1 Autosave API Endpoint

- [x] Implement `POST /notes/api/<id>/autosave` route
  - [x] Accept JSON body: `{"title": "...", "content": "..."}`
  - [x] Validate title is not empty (return error JSON if empty)
  - [x] Use authorization helper to get note
  - [x] Update title and content
  - [x] Update modified_at timestamp (only if title or content actually changed)
  - [x] Return JSON: `{"status": "success", "modified_at": "..."}`
  - [x] Return appropriate error JSON on failure
- [x] Add CSRF token meta tag to base template
  - [x] `<meta name="csrf-token" content="{{ csrf_token() }}">`

**Manual Testing 3.1:**
- [ ] API returns success for valid request (test with curl/Postman)
- [ ] API returns error for empty title
- [ ] API returns 404 for unauthorized note access
- [ ] CSRF token validation works

---

### 3.2 Autosave JavaScript Implementation

- [x] Create autosave JavaScript (in edit template or separate file)
  - [x] Debounce timer: 3 seconds of no typing
  - [x] Monitor both title input and content textarea
  - [x] Reset timer on each keystroke in either field
  - [x] Skip autosave if title is empty
  - [x] Send AJAX POST to `/notes/api/<id>/autosave`
  - [x] Include CSRF token in X-CSRFToken header
- [x] Implement visual indicator
  - [x] "Unsaved changes" when content differs from last save
  - [x] "Saving..." while request in progress
  - [x] "Saved" when autosave completes
  - [x] Error indicator on failure (clears on next successful save)
- [x] Update edit page template with indicator element

**Manual Testing 3.2:**
- [ ] Typing triggers "Unsaved changes" indicator
- [ ] After 3 seconds of no typing, autosave fires
- [ ] Indicator shows "Saving..." then "Saved"
- [ ] Typing resets the 3-second timer
- [ ] Empty title does NOT trigger autosave
- [ ] Manual save still works alongside autosave
- [ ] Autosave error shows indicator (disable network to test)
- [ ] Next successful save clears error indicator

---

### 3.3 Mobile Responsiveness

- [x] Add responsive CSS for notes list
  - [x] Card view on small screens (instead of table)
  - [x] Stack elements vertically
- [x] Add responsive CSS for edit page
  - [x] Full-width textarea
  - [x] Large touch targets for buttons (min 44x44px)
- [x] Add responsive CSS for view page
  - [x] Readable content width
  - [x] Touch-friendly action buttons
- [x] Ensure minimum 16px font size throughout
- [x] Test navigation on small screens

**Manual Testing 3.3:**
- [ ] Main list displays as cards on mobile viewport
- [ ] All buttons are easily tappable (44x44px minimum)
- [ ] Text is readable without zooming
- [ ] Edit textarea is usable on mobile
- [ ] No horizontal scrolling required
- [ ] Navigation works on small screens

---

### 3.4 Error Handling & Edge Cases

- [x] Verify all routes return 404 for non-existent notes
- [x] Verify all routes return 404 for other users' notes
- [x] Add flash messages for all success/error scenarios
  - [x] "Note saved"
  - [x] "Note deleted"
  - [x] "Note archived"
  - [x] "Note unarchived"
  - [x] "Title cannot be empty"
  - [x] "Note not found" (handled via 404)
  - [x] "Failed to save note. Please try again." (handled in autosave JS)
- [x] Handle network errors gracefully in autosave
- [x] Verify CSRF protection on all POST routes

**Manual Testing 3.4:**
- [ ] All error scenarios show appropriate messages
- [ ] All success scenarios show appropriate messages
- [ ] No server errors (500) occur during normal use
- [ ] CSRF tokens are validated on all forms

---

### 3.5 Final Integration Testing

- [ ] Complete user flow: create note
  - [ ] Create new note with title
  - [ ] Add content in edit page
  - [ ] Verify autosave works
  - [ ] View rendered markdown
  - [ ] Return to main list and see note
- [ ] Complete user flow: edit existing note
  - [ ] Open existing note
  - [ ] Edit title and content
  - [ ] Save manually with Ctrl+S
  - [ ] Verify changes persisted
- [ ] Complete user flow: archive and unarchive
  - [ ] Archive a note
  - [ ] Verify it's in archived list
  - [ ] Verify it's NOT in main list or search
  - [ ] Unarchive the note
  - [ ] Verify it's back in main list
- [ ] Complete user flow: search
  - [ ] Create notes with searchable content
  - [ ] Search by title - verify results
  - [ ] Search by content - verify results
  - [ ] Verify archived notes not in search results
- [ ] Complete user flow: delete
  - [ ] Delete a note
  - [ ] Verify confirmation appears
  - [ ] Verify note is gone after confirmation
- [ ] Security testing
  - [ ] Try to access another user's note by ID
  - [ ] Try to edit another user's note
  - [ ] Try to delete another user's note
  - [ ] Verify all return 404 (not 403)
