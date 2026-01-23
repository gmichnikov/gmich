# Notes Project - Implementation Plan

This plan follows the PRD phases but breaks them into smaller, testable chunks.

---

## Phase 1: Core CRUD (MVP)

### 1.1 Database Model Setup

- [ ] Create `Note` model in `app/projects/notes/models.py`
  - [ ] Define all fields: `id`, `user_id`, `title`, `content`, `is_archived`, `created_at`, `modified_at`
  - [ ] Add foreign key relationship to User model
  - [ ] Set appropriate defaults (`content=''`, `is_archived=False`)
  - [ ] Add `__repr__` method for debugging
- [ ] Create database migration
  - [ ] Generate migration file with `flask db migrate`
  - [ ] Review migration file for correctness
  - [ ] Run migration with `flask db upgrade`
- [ ] Add indexes for query optimization
  - [ ] Composite index on `(user_id, is_archived, modified_at)`
  - [ ] Index on `(user_id, modified_at)`

**Manual Testing 1.1:**
- [ ] Verify table exists in database
- [ ] Verify all columns have correct types and constraints
- [ ] Verify indexes are created

---

### 1.2 Blueprint and Route Structure

- [ ] Create notes blueprint in `app/projects/notes/__init__.py`
  - [ ] Initialize blueprint with url_prefix `/notes`
  - [ ] Register blueprint in main app
- [ ] Create `routes.py` with placeholder routes
  - [ ] `GET /notes/` - list notes (placeholder)
  - [ ] `GET /notes/new` - new note form (placeholder)
  - [ ] `POST /notes/create` - create note (placeholder)
  - [ ] `GET /notes/<id>` - view note (placeholder)
  - [ ] `GET /notes/<id>/edit` - edit note (placeholder)
  - [ ] `POST /notes/<id>/save` - save note (placeholder)
  - [ ] `POST /notes/<id>/delete` - delete note (placeholder)
- [ ] Add `@login_required` decorator to all routes
- [ ] Create empty templates directory structure

**Manual Testing 1.2:**
- [ ] Verify `/notes/` route loads (even if empty)
- [ ] Verify unauthenticated users are redirected to login
- [ ] Verify 404 for non-existent routes

---

### 1.3 Helper Functions

- [ ] Create helper function to get note by ID with authorization check
  - [ ] Return 404 if note doesn't exist
  - [ ] Return 404 if note belongs to different user (don't reveal existence)
- [ ] Create date formatting helper/template filter
  - [ ] Convert UTC to user's timezone
  - [ ] Format as "Jan 23, 2026 3:45 PM"
  - [ ] Register as Jinja filter
- [ ] Create content preview helper
  - [ ] Truncate to 100 characters
  - [ ] Add "..." if truncated
  - [ ] Return "(empty)" if no content

**Manual Testing 1.3:**
- [ ] Test date formatting with various timezones
- [ ] Test content preview with short, long, and empty content

---

### 1.4 Main Page - Notes List

- [ ] Implement `GET /notes/` route
  - [ ] Query active notes (is_archived=False) for current user
  - [ ] Order by modified_at DESC
- [ ] Create `notes/index.html` template
  - [ ] Page header "My Notes"
  - [ ] "New Note" button (link to /notes/new)
  - [ ] Search bar with input and disabled-when-empty button (functionality in Phase 2)
  - [ ] "View Archived Notes" link
  - [ ] Table/list displaying notes:
    - [ ] Title (clickable link to view page)
    - [ ] Content preview (100 chars)
    - [ ] Date created
    - [ ] Date modified
  - [ ] Empty state message when no notes exist

**Manual Testing 1.4:**
- [ ] Page loads without errors when logged in
- [ ] Empty state shows when user has no notes
- [ ] New Note button links to correct URL
- [ ] Archived notes link present

---

### 1.5 New Note Page

- [ ] Implement `GET /notes/new` route
  - [ ] Render form template
- [ ] Implement `POST /notes/create` route
  - [ ] Validate title is not empty
  - [ ] Create new Note in database
  - [ ] Set created_at and modified_at to current UTC time
  - [ ] Redirect to edit page for new note
- [ ] Create `notes/new.html` template
  - [ ] Title input field (required)
  - [ ] "Create Note" submit button
  - [ ] "Cancel" button (returns to main list)
  - [ ] Validation error display for empty title

**Manual Testing 1.5:**
- [ ] Form displays correctly
- [ ] Submitting empty title shows error, stays on page
- [ ] Submitting valid title creates note and redirects to edit page
- [ ] Cancel button returns to main list
- [ ] New note appears in main list

---

### 1.6 View Page

- [ ] Implement `GET /notes/<id>` route
  - [ ] Use authorization helper to get note
  - [ ] Render markdown content to HTML
  - [ ] Sanitize HTML output for XSS prevention
- [ ] Create `notes/view.html` template
  - [ ] Display title prominently
  - [ ] Display rendered markdown content
  - [ ] Display "Created: [date]" and "Last modified: [date]"
  - [ ] "Edit" button (links to edit page) - available for both active and archived notes
  - [ ] "Archive" button (only if not archived) - placeholder for Phase 2
  - [ ] "Unarchive" button (only if archived) - placeholder for Phase 2
  - [ ] "Delete" button with JS confirmation
  - [ ] "Back to Notes" link

**Manual Testing 1.6:**
- [ ] Note displays with correct title and content
- [ ] Markdown renders correctly (headers, bold, lists, code blocks)
- [ ] Dates display in correct format and timezone
- [ ] Edit button links to edit page
- [ ] Back to Notes returns to main list
- [ ] Accessing another user's note returns 404
- [ ] Accessing non-existent note ID returns 404

---

### 1.7 Edit Page with Manual Save

- [ ] Implement `GET /notes/<id>/edit` route
  - [ ] Use authorization helper to get note
  - [ ] Render edit form with current values
- [ ] Implement `POST /notes/<id>/save` route
  - [ ] Validate title is not empty
  - [ ] Update title and content
  - [ ] Update modified_at timestamp (only if title or content actually changed)
  - [ ] Flash success message
  - [ ] Redirect back to edit page
- [ ] Create `notes/edit.html` template
  - [ ] Title input field (required, pre-filled)
  - [ ] Large textarea for content (pre-filled)
  - [ ] "Save" button
  - [ ] "View Note" button (links to view page)
  - [ ] "Back to Notes" link
  - [ ] Validation error display for empty title
  - [ ] Placeholder for autosave indicator (Phase 3)
- [ ] Implement Ctrl+S / Cmd+S keyboard shortcut
  - [ ] Prevent browser default save dialog
  - [ ] Submit form on keypress

**Manual Testing 1.7:**
- [ ] Edit page loads with current note data
- [ ] Saving with empty title shows error, stays on page
- [ ] Saving valid changes updates note and shows success message
- [ ] modified_at timestamp updates after save
- [ ] Ctrl+S triggers save (Windows/Linux)
- [ ] Cmd+S triggers save (Mac)
- [ ] View Note button goes to view page
- [ ] Back to Notes returns to main list

---

### 1.8 Delete Functionality

- [ ] Implement `POST /notes/<id>/delete` route
  - [ ] Use authorization helper to get note
  - [ ] Delete note from database
  - [ ] Flash success message
  - [ ] Redirect to main notes list
- [ ] Add JavaScript confirmation to delete button on view page
  - [ ] Confirmation message: "Are you sure you want to permanently delete this note? This action cannot be undone."
  - [ ] Only proceed if user confirms

**Manual Testing 1.8:**
- [ ] Delete button shows confirmation dialog
- [ ] Canceling confirmation does not delete note
- [ ] Confirming deletion removes note from database
- [ ] After deletion, redirected to main list with success message
- [ ] Deleted note no longer appears in list

---

## Phase 2: Search & Archive

### 2.1 Archive/Unarchive Functionality

- [ ] Implement `POST /notes/<id>/archive` route
  - [ ] Set is_archived=True (do NOT update modified_at)
  - [ ] Flash success message
  - [ ] Redirect to archived notes view
- [ ] Implement `POST /notes/<id>/unarchive` route
  - [ ] Set is_archived=False (do NOT update modified_at)
  - [ ] Flash success message
  - [ ] Redirect to main notes list
- [ ] Update view page template
  - [ ] Show "Archive" button only for active notes
  - [ ] Show "Unarchive" button only for archived notes

**Manual Testing 2.1:**
- [ ] Archive button sets is_archived=True
- [ ] After archiving, redirected to archived view
- [ ] Archived note no longer appears in main list
- [ ] Unarchive button sets is_archived=False
- [ ] After unarchiving, redirected to main list
- [ ] modified_at is NOT changed by archive/unarchive

---

### 2.2 Archived Notes Page

- [ ] Implement `GET /notes/archived` route
  - [ ] Query only archived notes (is_archived=True) for current user
  - [ ] Order by modified_at DESC
- [ ] Create `notes/archived.html` template
  - [ ] Page header "Archived Notes"
  - [ ] Same table format as main page
  - [ ] "Back to Active Notes" link
  - [ ] Empty state: "No archived notes. Archive a note to see it here."

**Manual Testing 2.2:**
- [ ] Archived notes page shows only archived notes
- [ ] Empty state displays when no archived notes
- [ ] Notes are sorted by modified_at DESC
- [ ] Clicking note title goes to view page
- [ ] Can view, edit, and delete archived notes
- [ ] Back to Active Notes link works

---

### 2.3 Search - Main Page Integration

- [ ] Update main page search bar
  - [ ] Form submits to `/notes/search` with GET
  - [ ] Search button disabled when input is empty (JavaScript)
  - [ ] Pass query as `?q=` parameter

**Manual Testing 2.3:**
- [ ] Search button is disabled when input is empty
- [ ] Search button enables when text is entered
- [ ] Submitting search navigates to search results page with query in URL

---

### 2.4 Search Results Page

- [ ] Implement `GET /notes/search` route
  - [ ] Accept `q` (query) and `scope` (title/content) parameters
  - [ ] Default scope to "title"
  - [ ] Perform case-insensitive search (ILIKE)
  - [ ] Filter to active notes only (is_archived=False)
  - [ ] Filter by current user
  - [ ] Order by modified_at DESC
- [ ] Create `notes/search.html` template
  - [ ] Search input pre-filled with current query
  - [ ] Scope dropdown (Title / Content)
  - [ ] Auto-submit on scope change (JavaScript)
  - [ ] Results table (same format as main page)
  - [ ] Empty results message: "No notes found matching '[query]'"
  - [ ] "Back to Notes" link

**Manual Testing 2.4:**
- [ ] Title search finds notes with matching titles
- [ ] Content search finds notes with matching content
- [ ] Search is case-insensitive
- [ ] Archived notes are NOT included in results
- [ ] Changing scope dropdown re-submits with same query
- [ ] Empty results show appropriate message
- [ ] Results sorted by modified_at DESC
- [ ] Other users' notes are not included

---

## Phase 3: Autosave & Polish

### 3.1 Autosave API Endpoint

- [ ] Implement `POST /notes/api/<id>/autosave` route
  - [ ] Accept JSON body: `{"title": "...", "content": "..."}`
  - [ ] Validate title is not empty (return error JSON if empty)
  - [ ] Use authorization helper to get note
  - [ ] Update title and content
  - [ ] Update modified_at timestamp (only if title or content actually changed)
  - [ ] Return JSON: `{"status": "success", "modified_at": "..."}`
  - [ ] Return appropriate error JSON on failure
- [ ] Add CSRF token meta tag to base template
  - [ ] `<meta name="csrf-token" content="{{ csrf_token() }}">`

**Manual Testing 3.1:**
- [ ] API returns success for valid request (test with curl/Postman)
- [ ] API returns error for empty title
- [ ] API returns 404 for unauthorized note access
- [ ] CSRF token validation works

---

### 3.2 Autosave JavaScript Implementation

- [ ] Create autosave JavaScript (in edit template or separate file)
  - [ ] Debounce timer: 3 seconds of no typing
  - [ ] Monitor both title input and content textarea
  - [ ] Reset timer on each keystroke in either field
  - [ ] Skip autosave if title is empty
  - [ ] Send AJAX POST to `/notes/api/<id>/autosave`
  - [ ] Include CSRF token in X-CSRFToken header
- [ ] Implement visual indicator
  - [ ] "Unsaved changes" when content differs from last save
  - [ ] "Saving..." while request in progress
  - [ ] "Saved" when autosave completes
  - [ ] Error indicator on failure (clears on next successful save)
- [ ] Update edit page template with indicator element

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

- [ ] Add responsive CSS for notes list
  - [ ] Card view on small screens (instead of table)
  - [ ] Stack elements vertically
- [ ] Add responsive CSS for edit page
  - [ ] Full-width textarea
  - [ ] Large touch targets for buttons (min 44x44px)
- [ ] Add responsive CSS for view page
  - [ ] Readable content width
  - [ ] Touch-friendly action buttons
- [ ] Ensure minimum 16px font size throughout
- [ ] Test navigation on small screens

**Manual Testing 3.3:**
- [ ] Main list displays as cards on mobile viewport
- [ ] All buttons are easily tappable (44x44px minimum)
- [ ] Text is readable without zooming
- [ ] Edit textarea is usable on mobile
- [ ] No horizontal scrolling required
- [ ] Navigation works on small screens

---

### 3.4 Error Handling & Edge Cases

- [ ] Verify all routes return 404 for non-existent notes
- [ ] Verify all routes return 404 for other users' notes
- [ ] Add flash messages for all success/error scenarios
  - [ ] "Note saved"
  - [ ] "Note deleted"
  - [ ] "Note archived"
  - [ ] "Note unarchived"
  - [ ] "Title cannot be empty"
  - [ ] "Note not found"
  - [ ] "Failed to save note. Please try again."
- [ ] Handle network errors gracefully in autosave
- [ ] Verify CSRF protection on all POST routes

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
