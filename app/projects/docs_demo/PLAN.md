# Docs Demo — Implementation Plan

This plan follows the PRD and breaks implementation into small, testable phases. Each phase ends with manual testing steps before moving on.

---

## Relevant Files

- `app/projects/docs_demo/__init__.py` — package marker
- `app/projects/docs_demo/routes.py` — blueprint, index route, API route
- `app/projects/docs_demo/gemini_service.py` — thin wrapper to call Gemini
- `app/projects/docs_demo/templates/docs_demo/index.html` — full-page docs UI (from `docs-ui.html`, with `docs-demo-` prefix)
- `app/projects/docs_demo/static/docs_demo/style.css` — all styles, `docs-demo-` prefix
- `app/projects/docs_demo/static/docs_demo/app.js` — editor logic, slash commands, comments, command pill
- `app/__init__.py` — blueprint already registered
- `app/projects/registry.py` — project already registered

---

## Phase 1: Backend — Gemini Service & API Route

### 1.1 Gemini Service

- [ ] Create `app/projects/docs_demo/gemini_service.py`
  - [ ] Function `generate_text(prompt: str, text: str) -> str` — calls Gemini with prompt + text, returns plain text result
  - [ ] Function `generate_comments(prompt: str, document_text: str) -> list[dict]` — calls Gemini, parses JSON response `[{target, comment}, ...]`, returns list; prompt must instruct Gemini to quote target text exactly
  - [ ] Use `google.genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))`
  - [ ] Model: `gemini-3-flash-preview` (as in `sports_schedules`)
  - [ ] Handle API errors gracefully; re-raise or return structured error for route to handle

**Manual Testing 1.1:**
- [ ] In Flask shell, call `generate_text("Rewrite briefly: ", "hello world")` — verify non-empty string returned
- [ ] In Flask shell, call `generate_comments` with sample doc — verify list of `{target, comment}` dicts returned

---

### 1.2 API Route

- [ ] Add `POST /docs-demo/api/generate` to `routes.py`
  - [ ] Accept JSON body: `{ "type": "text" | "comments", "prompt": "...", "text": "..." }`
  - [ ] Validate `type`, `prompt`, `text` present
  - [ ] If `type: "text"`: call `generate_text`, return `{"result": "..."}`
  - [ ] If `type: "comments"`: call `generate_comments`, return `{"comments": [...]}`
  - [ ] On error: return 500 with `{"error": "Something went wrong. Please try again."}` or similar
  - [ ] No auth; no CSRF exemption needed if using fetch with existing patterns (verify)

**Manual Testing 1.2:**
- [ ] POST to `/docs-demo/api/generate` with `type: "text"`, sample prompt and text — verify JSON result
- [ ] POST with `type: "comments"`, sample doc — verify comments array
- [ ] POST with invalid/missing fields — verify appropriate error response

---

## Phase 2: Docs UI Layout (Prefixed, Cosmetic)

### 2.1 Convert docs-ui.html to index.html

- [ ] Create `templates/docs_demo/index.html` from `templates/docs_demo/docs-ui.html`
  - [ ] **Do not extend base.html** — standalone full page
  - [ ] Add `docs-demo-` prefix to all CSS class names (e.g. `top-bar` → `docs-demo-top-bar`)
  - [ ] Move inline styles to `static/docs_demo/style.css`
  - [ ] Keep structure: top bar, toolbar, document area, comments gutter, status bar
  - [ ] Top bar: doc icon, editable title, menus (File, Edit, View, etc.), icons (History, Comment, Meet), Share button, Gemini sparkle, avatar — all cosmetic (no handlers yet)
  - [ ] Toolbar: bold, italic, font selector, etc. — all cosmetic (no handlers)
  - [ ] Menu items and toolbar buttons do nothing on click

**Manual Testing 2.1:**
- [ ] Navigate to `/docs-demo/` — full-page loads, no app navbar/footer
- [ ] Verify layout matches docs-ui.html (top bar, toolbar, page, comments gutter, status bar)
- [ ] Verify all classes prefixed; no style collisions with other projects

---

### 2.2 Document Area & Comments Gutter

- [ ] Document area: `contenteditable` div (or prepare for it) with `docs-demo-page-content` class
  - [ ] White page styling, clean typography
  - [ ] Initial placeholder text: "Start typing here..." (clear on first focus)
- [ ] Comments gutter: 280px width, right of page, `docs-demo-comments-gutter`
  - [ ] Empty when no comments (optionally subtle "Run /review or /comment for feedback")
- [ ] Wire up `app.js` (can be minimal stub for now)

**Manual Testing 2.2:**
- [ ] Document area is editable; can type text
- [ ] Comments gutter visible, empty
- [ ] Page scrolls if content is long

---

## Phase 3: Editable Document & Selection

### 3.1 Contenteditable & Selection Capture

- [ ] Ensure document area is `contenteditable="true"`
- [ ] On focus of command pill (Phase 4): save document selection via `window.getSelection()` and `Range` before focus moves
- [ ] When applying text-transform result: restore selection and replace selected text; if no selection, replace full document content
- [ ] When applying brainstorm result: insert bullets after the saved selection's end position
- [ ] Helper: `getDocumentText()` — return plain text of document (for API calls)
- [ ] Helper: `getSelectionOrFullDocument()` — return selected text or full doc text

**Manual Testing 3.1:**
- [ ] Select some text, focus elsewhere, verify selection can be retrieved (or re-capture before focus change)
- [ ] Verify `getDocumentText()` returns correct content
- [ ] Verify selection vs. full-doc logic for replacement

---

## Phase 4: Command Pill & Gemini Sparkle Toggle

### 4.1 Floating Command Pill

- [ ] Add floating pill below document area (or overlaying bottom of viewport)
  - [ ] Horizontally centered, ~2/3 of document width
  - [ ] Tall enough for 2–3 lines (textarea or contenteditable)
  - [ ] Placeholder: "Type / for commands or ask Gemini anything..."
  - [ ] Styled like Google Docs AI bar (rounded, subtle shadow)
  - [ ] Class: `docs-demo-command-pill`
- [ ] Pill is always visible by default (or per PRD: toggled by Gemini sparkle)

**Manual Testing 4.1:**
- [ ] Command pill visible, centered, correct proportions
- [ ] Can focus and type in pill

---

### 4.2 Gemini Sparkle Toggle

- [ ] Gemini sparkle icon in top bar: on click, toggle visibility of command pill
  - [ ] When pill hidden: click sparkle → show pill
  - [ ] When pill visible: click sparkle → hide pill
- [ ] Persist toggle state in session if desired (optional; can be in-memory only)

**Manual Testing 4.2:**
- [ ] Click Gemini sparkle — pill hides
- [ ] Click again — pill shows
- [ ] Toggle works repeatedly

---

## Phase 5: Slash Commands — Text Transformation

### 5.1 Slash Command Config

- [ ] Define `SLASH_COMMANDS` in `app.js`:
  ```javascript
  const SLASH_COMMANDS = {
    "/improve":    { label: "Improve writing", prompt: "Rewrite the following text...\n\n{text}", requiresSelection: false },
    "/expand":     { label: "Expand", prompt: "Elaborate...\n\n{text}", requiresSelection: false },
    "/summarize":  { label: "Summarize", prompt: "Condense...\n\n{text}", requiresSelection: false },
    "/brainstorm": { label: "Brainstorm", prompt: "Generate bullet-point ideas about:\n\n{text}", requiresSelection: true },
    "/review":     { label: "Review document", prompt: "...", requiresSelection: false, type: "comments" },
    "/comment":    { label: "Comment (with instructions)", prompt: "User instructions: {instructions}\n\nDocument:\n{text}", requiresSelection: false, type: "comments", requiresExtraText: true }
  };
  ```
- [ ] Substitute `{text}` and `{instructions}` at runtime

---

### 5.2 Command Execution — /improve, /expand, /summarize

- [ ] On Submit (Enter or button): parse input
  - [ ] If starts with `/`, match against `SLASH_COMMANDS`
  - [ ] For `/improve`, `/expand`, `/summarize`: require document text (selection or full); block with "Document is empty" if empty
- [ ] Build prompt: replace `{text}` with selection or full doc
- [ ] POST to `/docs-demo/api/generate` with `type: "text"`
- [ ] On success: replace selection (or full doc) with `result`
- [ ] On error: show error message in UI
- [ ] Show loading spinner, disable input during request

**Manual Testing 5.2:**
- [ ] Type "hello world" in doc, run `/improve` — text replaced with improved version
- [ ] Select a paragraph, run `/expand` — only selection replaced
- [ ] Run `/summarize` on full doc — full doc replaced with summary
- [ ] Empty doc + `/improve` — error shown, no API call
- [ ] Spinner shows during request; errors display on failure

---

### 5.3 /brainstorm

- [ ] `/brainstorm` requires selection — block with "Please select text to brainstorm about" if no selection
- [ ] Send selection as `{text}` in prompt
- [ ] Parse response as bullet list (or let Gemini return markdown bullets)
- [ ] Insert bullets immediately after the selection (do not replace selection)
- [ ] Use saved Range to insert at correct position

**Manual Testing 5.3:**
- [ ] Select "product launch ideas", run `/brainstorm` — bullet list inserted after selection
- [ ] No selection + `/brainstorm` — error shown
- [ ] Selection remains intact; bullets appear below it

---

## Phase 6: Freeform Prompts

- [ ] If input does not start with `/`, treat as freeform prompt
- [ ] Send to API with `type: "text"`, prompt = user input, text = selection or full doc
- [ ] Replace selection or full doc with result (same as transformation commands)
- [ ] Block if document is empty

**Manual Testing 6.1:**
- [ ] Type "make this more formal" with some text in doc — replaced correctly
- [ ] Select a sentence, type "add a metaphor" — selection replaced
- [ ] Empty doc — error shown

---

## Phase 7: AI Comments — /review & /comment

### 7.1 Review Prompt

- [ ] Fixed prompt for `/review`: ask Gemini for passage-level feedback, return JSON array `[{target, comment}, ...]`
- [ ] **Critical:** instruct Gemini to quote the `target` text exactly from the document (no paraphrasing)

---

### 7.2 /review Implementation

- [ ] On `/review`: POST with `type: "comments"`, full document text, fixed prompt
- [ ] Parse response: expect `comments` array
- [ ] For each `{target, comment}`:
  - [ ] Find `target` in document via exact string search
  - [ ] If found: wrap/match in highlight element, render comment in sidebar
  - [ ] If not found: skip (no crash)
- [ ] Order comments by document order (first occurrence of target)

**Manual Testing 7.2:**
- [ ] Write a short doc, run `/review` — comments appear in sidebar, passages highlighted
- [ ] Click comment in sidebar → document scrolls to highlight
- [ ] Click highlight in doc → corresponding comment highlighted/focused
- [ ] If a target isn't found, no error; that comment omitted

---

### 7.3 /comment Implementation

- [ ] `/comment` requires text after: `/comment look for passive voice`
- [ ] Parse: command = `/comment`, rest = instructions
- [ ] Block if no instructions: "Please add instructions, e.g. /comment look for passive voice"
- [ ] Build prompt with `{instructions}` and full document `{text}`
- [ ] Same response handling as `/review`: highlight passages, render in sidebar

**Manual Testing 7.3:**
- [ ] Run `/comment improve clarity` — comments appear based on instructions
- [ ] Run `/comment` with no extra text — error shown
- [ ] Click interactions work same as /review

---

## Phase 8: Command Discovery & Polish

### 8.1 Autocomplete

- [ ] When user types `/`, show dropdown of matching commands
- [ ] Filter as they keep typing (e.g. `/imp` → `/improve`)
- [ ] Selecting from dropdown (click or Enter) inserts/selects command
- [ ] Show label + short description if space allows

**Manual Testing 8.1:**
- [ ] Type `/` — dropdown appears with all commands
- [ ] Type `/imp` — dropdown filters to `/improve`
- [ ] Select command — input updated, can add text if needed

---

### 8.2 Help Icon

- [ ] Add hover icon (e.g. "?" or info) near command pill
- [ ] On hover/click: popup listing all commands with brief descriptions
- [ ] Format: command, label, whether it needs selection/extra text

**Manual Testing 8.2:**
- [ ] Hover/click help icon — popup shows command list
- [ ] Descriptions are clear

---

### 8.3 Loading & Error UX

- [ ] Loading: spinner in or near command pill, disable input
- [ ] Error: display inline below pill or in pill area (e.g. "Something went wrong. Please try again.")
- [ ] Empty doc / no selection (when required): block with clear message
- [ ] /comment with no instructions: block with clear message

**Manual Testing 8.3:**
- [ ] Spinner visible during all LLM calls
- [ ] API error (e.g. invalid key) — user sees error message
- [ ] Validation errors (empty doc, no selection, etc.) — clear messages

---

## Phase 9: Edge Cases & Completion

### 9.1 Edge Cases

- [ ] Selection lost on focus: save selection before focusing pill (see Phase 3)
- [ ] Multiple occurrences of target: use first match for comment anchoring (or document order)
- [ ] Gemini returns malformed JSON for comments: try to parse; on failure, show error, don't crash
- [ ] Very long document: consider truncation or token limits (Gemini has limits); document in plan if needed

**Manual Testing 9.1:**
- [ ] Full flow: type doc → /improve → /review → click comments, click highlights
- [ ] Full flow: select text → /brainstorm → /comment look for jargon
- [ ] Verify no console errors during normal use

---

## Completion Checklist

- [ ] `GET /docs-demo/` serves full-page UI (no base.html)
- [ ] `POST /docs-demo/api/generate` handles `type: "text"` and `type: "comments"`
- [ ] All CSS classes use `docs-demo-` prefix
- [ ] Floating command pill visible (or toggled via Gemini sparkle), ~2/3 doc width
- [ ] `/improve`, `/expand`, `/summarize` replace selection or full doc
- [ ] `/brainstorm` inserts bullets after selection; requires selection
- [ ] Freeform prompts work
- [ ] `/review` and `/comment <instructions>` produce comments with highlights
- [ ] Click comment → scroll to passage; click passage → focus comment
- [ ] Autocomplete on `/`; help icon shows commands
- [ ] Loading spinner during requests; errors displayed
- [ ] Empty doc / no selection / no instructions blocked with clear errors

---

## Future Enhancements (Post-V1)

- [ ] localStorage for document survival across refresh
- [ ] Fuzzy text matching for comment anchoring when exact match fails
- [ ] Mobile-optimized layout
- [ ] More slash commands
- [ ] Postgres + auth for saved documents (upgrade path)
