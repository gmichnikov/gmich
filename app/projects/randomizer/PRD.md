# Randomizer — Product Requirements Document

## Overview

A front-end-only web tool for randomly distributing a list of items into groups. No login required, no database. All state lives in the browser (localStorage + in-memory).

---

## Features

### 1. List of Items to Randomize

- Users build a list of items before running the randomizer.
- Items are displayed as an editable list — each item can be edited inline or deleted individually.
- **Item count** is displayed live (e.g. "8 items") and updates immediately as items are added or removed.
- **Duplicate detection**: if a user adds an item that already exists in the list (case-insensitive), show a visible warning but do not block the addition. The user can choose to keep or remove the duplicate.

### 2. Ways to Add Items

Three input methods, all feeding into the same item list:

- **Text input**: type a single item and press Enter or click Add.
- **Paste comma-separated**: paste a string like `Alice, Bob, Carol` and have it split into individual items.
- **Paste newline-separated**: paste a multi-line block (one item per line) and have it split into individual items.

Pasted input should be trimmed of leading/trailing whitespace per item, and empty entries should be discarded.

### 3. Grouping Configuration

- A radio toggle lets the user choose their mode: `○ Number of groups  ○ Items per group`.
- Selecting a mode shows a single number input for that value. The other value is derived and displayed as read-only text below the input (e.g. "→ 4 groups" or "→ 3 items per group").
- **Uneven splits**: if items don't divide evenly, distribute the remainder one-per-group starting from Group 1. Clearly indicate which groups have an extra item (e.g. "Groups 1–2 have 4 items; Groups 3–4 have 3 items").

### 4. Group Naming

- By default, groups are labeled "Group 1", "Group 2", etc.
- Users can optionally provide custom names for each group (e.g. "Team A", "Round 1", "Table 3").
- Custom names appear in the results display and in copied/downloaded output.

### 5. Randomize & Re-shuffle

- **Randomize button**: runs the randomization and displays results.
- **Re-shuffle button**: re-runs the randomization with the same items and settings, without requiring the user to re-enter anything. Available after the first randomization.

### 6. Clear / Reset

- A **Clear / Reset button** wipes the item list, group settings, group names, and results back to a blank state.
- Also clears localStorage.

### 7. Results Display

Two display modes, togglable after results are shown:

- **Card layout**: each group shown as a card side by side (grid), good for comparing groups at a glance.
- **List layout**: groups stacked vertically, good for longer item names or mobile.

Results remain visible until the user re-shuffles, clears, or navigates away.

### 8. Copy Results to Clipboard

- A **Copy to Clipboard** button copies the randomized results as plain text.
- Format:
  ```
  Group 1 (or custom name):
  - Alice
  - Bob

  Group 2:
  - Carol
  - Dave
  ```

### 9. Download as Text File

- A **Download .txt** button saves the same formatted output as a `.txt` file.
- Filename: `randomizer-results.txt`

### 10. Persist to localStorage

- The current item list and group settings (number of groups/items, custom group names) are saved to `localStorage` automatically as the user makes changes.
- On page load, if saved data exists, it is restored so the user can continue where they left off.
- Clearing/resetting also clears localStorage.

### 11. Mobile-Friendly Layout

- All input controls, item list, and results are usable on small screens.
- Card layout switches to single-column on narrow viewports.
- Buttons and inputs meet minimum touch target sizes.
- No horizontal scrolling.

---

## Out of Scope (for now)

- User accounts / login
- Database persistence
- Shareable URLs
- Shuffle animation
- Drag-to-reorder items
- Mutual exclusivity constraints ("keep these apart")
- History of previous shuffles
