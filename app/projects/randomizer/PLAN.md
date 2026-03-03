# Randomizer — Implementation Plan

This plan follows the PRD and breaks the work into small, testable phases. All work is front-end only (HTML, CSS, vanilla JS) — no database, no login.

---

## Phase 1: Item List Input

### 1.1 Page Layout & Base Structure

- [ ] Replace the existing placeholder `index.html` with the full Randomizer layout
- [ ] Two-column layout on desktop: left panel (inputs) + right panel (results); single column on mobile
- [ ] Left panel sections: Item Input, Item List, Grouping Config
- [ ] Right panel: Results area (empty state until first randomization)
- [ ] Link project CSS (`rz-` prefix) in `{% block styles %}`
- [ ] Add all JS in `{% block scripts %}` or a dedicated `static/randomizer/randomizer.js`

**Manual Testing 1.1:**
- [ ] Page loads at `/randomizer`
- [ ] Two-panel layout visible on desktop
- [ ] Single-column stacking on mobile (375px viewport)
- [ ] No console errors

---

### 1.2 Single-Item Text Input

- [ ] Text input field with placeholder "Add an item…"
- [ ] "Add" button next to input
- [ ] Pressing Enter in the input also adds the item
- [ ] Item is trimmed of whitespace before being added
- [ ] Empty string after trimming is ignored (no add)
- [ ] Input clears after a successful add

**Manual Testing 1.2:**
- [ ] Type an item, press Enter → item added, input cleared
- [ ] Type an item, click Add → same result
- [ ] Type only spaces, press Enter → nothing added
- [ ] Input clears after adding

---

### 1.3 Paste Comma-Separated Items

- [ ] "Paste a list" textarea (or second input mode accessible via tab/toggle)
- [ ] "Add from paste" button splits input on commas
- [ ] Each resulting token is trimmed; empty tokens discarded
- [ ] All valid tokens added to the item list in one action
- [ ] Textarea clears after successful add

**Manual Testing 1.3:**
- [ ] Paste `Alice, Bob, Carol` → 3 items added
- [ ] Paste `Alice,,Bob , Carol` → 3 items (empty token discarded, "Bob " trimmed)
- [ ] Works on mobile (paste from clipboard)

---

### 1.4 Paste Newline-Separated Items

- [ ] Same textarea as 1.3 also handles newline-separated input
- [ ] Logic: if input contains newlines, split on newlines; otherwise split on commas
- [ ] Each token trimmed; empties discarded

**Manual Testing 1.4:**
- [ ] Paste a multi-line block → each line becomes one item
- [ ] Paste a single line with commas → comma-split still works
- [ ] Mix of both (commas and newlines) → newline takes precedence

---

### 1.5 Item List Display & Item Count

- [ ] Items displayed as a styled list below the inputs
- [ ] Live item count shown above or beside the list (e.g. "5 items")
- [ ] Count updates immediately on every add or remove
- [ ] Empty state: "No items yet. Add some above."

**Manual Testing 1.5:**
- [ ] Add 3 items → count reads "3 items"
- [ ] Remove one → count reads "2 items"
- [ ] Add 1 item → count reads "1 item" (singular)
- [ ] Empty list shows empty state message

---

### 1.6 Edit & Delete Individual Items

- [ ] Each item in the list has an Edit (pencil) icon and a Delete (×) icon
- [ ] Clicking Delete removes the item immediately
- [ ] Clicking Edit replaces the item's display with an inline text input pre-filled with the current value
  - [ ] Confirm edit with Enter or a checkmark button
  - [ ] Cancel edit with Escape or a cancel button (restores original value)
- [ ] Edited value is trimmed; if empty after trim, cancel the edit (do not save empty)

**Manual Testing 1.6:**
- [ ] Click × on an item → item removed, count decrements
- [ ] Click pencil → item becomes editable
- [ ] Edit text, press Enter → updated value saved
- [ ] Press Escape → edit cancelled, original value restored
- [ ] Edit to blank, press Enter → edit cancelled (no empty items saved)

---

### 1.7 Duplicate Detection

- [ ] On every add (any method), compare the new item(s) against existing items (case-insensitive)
- [ ] If a duplicate is found, show a visible inline warning near the list: "⚠ 'Alice' is already in the list."
- [ ] The item is still added despite the warning
- [ ] Warning dismisses automatically after 4 seconds or when another item is added

**Manual Testing 1.7:**
- [ ] Add "Alice", then add "Alice" again → warning appears, item is in the list twice
- [ ] Add "alice" when "Alice" exists → warning appears (case-insensitive)
- [ ] Warning disappears after ~4 seconds
- [ ] Pasting a list that includes an existing item triggers the warning for each duplicate

---

## Phase 2: Grouping Configuration

### 2.1 Mode Toggle (# of Groups vs. Items per Group)

- [ ] Radio toggle with two options: `○ Number of groups` and `○ Items per group`
- [ ] Default: "Number of groups" selected
- [ ] A single number input is shown for the active mode
- [ ] The derived value is shown as read-only text below (e.g. "→ 3 items per group" or "→ 4 groups")
- [ ] Derived value updates live as the user changes the number input or the item count changes
- [ ] If the division is uneven, the derived display notes it (e.g. "→ ~3 items per group (uneven)")

**Manual Testing 2.1:**
- [ ] Default shows "Number of groups" mode with input
- [ ] Change to "Items per group" → input label and derived text swap
- [ ] With 10 items and 3 groups → derived shows "~3 items per group (uneven)"
- [ ] With 12 items and 3 groups → derived shows "4 items per group"
- [ ] Derived updates live as items are added/removed

---

### 2.2 Uneven Split Handling

- [ ] When items don't divide evenly, distribute the remainder starting from Group 1
- [ ] Show an info note in the results: e.g. "Groups 1–2 have 4 items; Groups 3–4 have 3 items"
- [ ] Edge case: 0 items → show error "Add some items first"
- [ ] Edge case: more groups than items → show error "Fewer items than groups"
- [ ] Edge case: 0 or negative group count → show error "Enter a valid number of groups"

**Manual Testing 2.2:**
- [ ] 7 items, 3 groups → Group 1 has 3, Groups 2–3 have 2; info note shown
- [ ] 0 items, click Randomize → error message shown
- [ ] 2 items, 5 groups → error shown
- [ ] 0 groups → error shown

---

### 2.3 Group Naming

- [ ] Below the grouping config, a toggle: "Custom group names (optional)"
- [ ] When enabled, a name input appears for each group (count determined by current group setting)
- [ ] Inputs are labeled "Group 1 name", "Group 2 name", etc. with placeholder "Group 1"
- [ ] If a name input is left blank, it falls back to the default "Group N" label
- [ ] Name inputs update when the number of groups changes (add/remove inputs as needed)

**Manual Testing 2.3:**
- [ ] Enable custom names → name inputs appear, one per group
- [ ] Change number of groups from 3 to 4 → 4th name input appears
- [ ] Leave one name blank → result uses "Group N" default for that group
- [ ] Disable custom names toggle → name inputs disappear, defaults used

---

## Phase 3: Randomize & Results

### 3.1 Randomize Button

- [ ] "Randomize" button below the config panel
- [ ] On click: validate inputs (items exist, group count valid), then shuffle items and assign to groups
- [ ] Fisher-Yates shuffle algorithm for true randomness
- [ ] Results displayed in the right panel immediately
- [ ] Randomize button remains active for re-shuffling

**Manual Testing 3.1:**
- [ ] Add 6 items, set 2 groups, click Randomize → results appear with 3 items each
- [ ] Click Randomize again → results change (re-shuffle with same inputs)
- [ ] Validate error cases from Phase 2.2 are caught here too

---

### 3.2 Results Display — Card Layout

- [ ] Default view: groups displayed as cards in a responsive grid (2–3 per row on desktop)
- [ ] Each card shows: group name (custom or default), item count, and list of items
- [ ] Cards collapse to single column on mobile
- [ ] Empty right panel before first randomization shows: "Configure your list and click Randomize"

**Manual Testing 3.2:**
- [ ] Results show correct items in each group
- [ ] Group names display correctly (custom and default)
- [ ] Cards are side by side on desktop, stacked on mobile
- [ ] Item counts on each card are accurate

---

### 3.3 Results Display — List Layout

- [ ] A toggle (e.g. two icon buttons: grid icon / list icon) above the results panel switches between card and list views
- [ ] List layout: groups stacked vertically, each group as a labeled section with a bulleted item list
- [ ] Toggle state is remembered for the session (not persisted to localStorage)

**Manual Testing 3.3:**
- [ ] Switch to list layout → groups stack vertically
- [ ] Switch back to card layout → grid returns
- [ ] List layout is readable on mobile

---

### 3.4 Re-Shuffle Button

- [ ] After the first randomization, a "Re-shuffle" button appears alongside the results
- [ ] Clicking it re-runs the randomization with the current items and settings (no need to click the main Randomize button)
- [ ] Button is distinct from (but near) the main Randomize button

**Manual Testing 3.4:**
- [ ] Click Randomize → results appear, Re-shuffle button appears
- [ ] Click Re-shuffle → results update with same item list and group config
- [ ] Re-shuffle multiple times → results vary (randomness working)

---

### 3.5 Clear / Reset Button

- [ ] A "Clear / Reset" button (separate from Re-shuffle, styled as a secondary/destructive action)
- [ ] Clears: item list, group config inputs, group names, results panel
- [ ] Clears localStorage
- [ ] Page returns to the initial empty state

**Manual Testing 3.5:**
- [ ] After entering items and randomizing, click Clear → everything resets
- [ ] localStorage is cleared (verify in DevTools → Application → Local Storage)
- [ ] Page looks identical to a fresh load after clearing

---

## Phase 4: Copy, Download & Persistence

### 4.1 Copy Results to Clipboard

- [ ] "Copy to Clipboard" button appears in the results panel after randomization
- [ ] Copies results as plain text in this format:
  ```
  Group 1 (or custom name):
  - Alice
  - Bob

  Group 2:
  - Carol
  - Dave
  ```
- [ ] Button shows a brief "Copied!" confirmation (e.g. 2 seconds), then reverts to "Copy to Clipboard"
- [ ] Uses the Clipboard API with a fallback for older browsers

**Manual Testing 4.1:**
- [ ] Click Copy → paste into a text editor, verify format is correct
- [ ] Custom group names appear in the copied output
- [ ] "Copied!" confirmation appears and reverts
- [ ] Test on mobile (clipboard access works)

---

### 4.2 Download as Text File

- [ ] "Download .txt" button appears in the results panel alongside Copy
- [ ] Generates the same plain-text format as clipboard copy
- [ ] Triggers a download of `randomizer-results.txt`
- [ ] No server request needed — generated entirely client-side using a Blob URL

**Manual Testing 4.2:**
- [ ] Click Download → `randomizer-results.txt` downloaded
- [ ] Open file → format matches expected output
- [ ] Custom group names appear in the file
- [ ] Works on mobile (file download or share sheet)

---

### 4.3 localStorage Persistence

- [ ] Save to localStorage on every change:
  - [ ] Item list (array of strings)
  - [ ] Grouping mode (# groups or items per group)
  - [ ] Grouping value (the number)
  - [ ] Custom group names (array of strings)
- [ ] On page load: check localStorage for saved state; if found, restore all of the above
- [ ] Restored state is reflected in the UI immediately (item list renders, inputs populated)
- [ ] Results are NOT persisted (user must re-randomize after reload)
- [ ] Clear/Reset also calls `localStorage.clear()` (or removes only Randomizer keys)

**Manual Testing 4.3:**
- [ ] Add items and configure groups → refresh page → items and config restored
- [ ] Custom group names survive a page refresh
- [ ] After Clear/Reset → refresh → page is empty (nothing restored)
- [ ] Open in a second tab → same state loads

---

## Phase 5: Polish & Mobile

### 5.1 Mobile Responsiveness Audit

- [ ] Test all interactions at 375px width
- [ ] Left/right panels stack to single column
- [ ] All buttons meet 44px minimum touch target
- [ ] Text inputs are full width on mobile
- [ ] Results cards are single column on mobile
- [ ] No horizontal scrolling at any point
- [ ] Paste inputs are comfortable to use on mobile keyboard

**Manual Testing 5.1:**
- [ ] Full flow on 375px viewport (Chrome DevTools)
- [ ] Full flow on an actual mobile device
- [ ] No horizontal scroll at any step
- [ ] All tap targets are easy to hit

---

### 5.2 Error States & Edge Cases

- [ ] Validate all error conditions show clear, friendly messages (not browser alerts)
- [ ] Errors appear inline near the relevant control (not just at the top of the page)
- [ ] Errors clear automatically when the condition is resolved
- [ ] Review all edge cases:
  - [ ] 1 item, 1 group → works (trivial case)
  - [ ] 1 item, 2 groups → error "Fewer items than groups"
  - [ ] 100 items → list scrollable, performance acceptable
  - [ ] Very long item name → wraps correctly in cards and list view
  - [ ] Special characters in item names (ampersand, quotes, emoji) → render safely

**Manual Testing 5.2:**
- [ ] Trigger each error condition, verify message is clear
- [ ] Add 100 items → no lag, list scrolls fine
- [ ] Add item with `<script>` tag → renders safely (not executed)
- [ ] Add item with emoji → displays correctly in results and copied output

---

### 5.3 Visual Polish

- [ ] Consistent spacing and typography matching the site's `base.html` style
- [ ] Randomize button is visually prominent (primary color, larger)
- [ ] Destructive actions (Clear/Reset) are styled as secondary/muted
- [ ] Smooth transition or highlight when results first appear
- [ ] Duplicate warning is visually distinct (yellow/orange, icon)
- [ ] Error messages are visually distinct (red, icon)
- [ ] Info notes (uneven split) are styled as info (blue, icon)

**Manual Testing 5.3:**
- [ ] Overall page looks polished and consistent with the rest of the site
- [ ] Warning, error, and info states are visually distinguishable
- [ ] Results panel feels responsive and snappy

---

## Completion Checklist

Before considering the project done:

- [ ] All phases' manual tests pass
- [ ] No console errors in browser
- [ ] No horizontal scroll on mobile
- [ ] localStorage persists and restores correctly
- [ ] Copy and Download produce correctly formatted output
- [ ] All error edge cases handled gracefully
- [ ] CSS uses `rz-` prefix throughout, no class name collisions
- [ ] Works on Chrome, Firefox, and Safari
- [ ] Works on iOS Safari and Android Chrome

---

## Future Enhancements (Out of Scope for V1)

- [ ] Shareable URL (encode list + config in query params)
- [ ] Shuffle animation (brief visual mixing before reveal)
- [ ] Drag-to-reorder items in input list
- [ ] Mutual exclusivity constraints ("keep these apart")
- [ ] History of previous shuffles
- [ ] Dark mode
