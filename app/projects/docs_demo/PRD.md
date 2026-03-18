# Docs Demo — Product Requirements Document

## Overview

A web-based demo that recreates a Google Docs-like editing experience with AI-powered features using Gemini. Users write text in a document and use slash commands or freeform prompts to transform content or get feedback in the form of document comments. No login, no database. All state is ephemeral.

---

## Architecture

### Frontend-only state
- All document state lives in memory
- No localStorage persistence (document does not survive refresh)
- Slash command definitions are hardcoded in a JS config object
- AI-generated comments are ephemeral — generated on demand, not saved

### Thin Flask backend (API proxy only)
- Flask serves the frontend and provides a single API route that proxies requests to Gemini
- API key kept server-side via `GOOGLE_API_KEY` environment variable
- No database, no session management, no auth
- Reuse existing LLM patterns from `ask_many_llms` / `sports_schedules` — use `google.genai` Client with `GOOGLE_API_KEY`

### Editor
- `contenteditable` div styled to look like a Google Docs page
- No editor libraries (TipTap, Quill, etc.)
- No rich formatting support — toolbar and menu items are cosmetic only (do nothing)
- Focus is on: write text, make LLM calls to improve or change it

---

## UI Layout

### Full-page experience
- **Do not extend base.html** — standalone full-page layout (no app navbar/footer)
- Starting point: `docs-ui.html` as the visual reference

### Layout structure

```
┌──────────────────────────────────────────────────┐
│  Top bar (doc icon, title, menus, icons, Share,   │
│  Gemini sparkle, avatar) — menus don't work       │
├──────────────────────────────────────────────────┤
│  Toolbar (bold, italic, font selector, etc.)     │
│  — all buttons cosmetic, do nothing               │
├────────────────────────────────┬─────────────────┤
│                                │                 │
│   contenteditable div          │   Comments      │
│   (the "document")             │   gutter (right) │
│                                │                 │
│   - White page styling         │   - Empty when  │
│   - Clean typography           │     no comments │
│   - Highlighted passages       │   - Renders AI  │
│     when comments exist        │     comments    │
│                                │     when /review│
│                                │     or /comment │
├────────────────────────────────┴─────────────────┤
│  [Floating Gemini command pill — see below]       │
├──────────────────────────────────────────────────┤
│  Status bar (word count, zoom) — optional         │
└──────────────────────────────────────────────────┘
```

### Gemini command bar (floating pill)

- **Not** a bottom-edge bar — a **floating pill** that is:
  - Always visible
  - Horizontally centered
  - ~2/3 of the document width
  - Tall enough for a couple lines of text (multiline input)
- Styled like a Google Docs AI bar
- Placeholder: "Type / for commands or ask Gemini anything..."

### Gemini sparkle in top bar

- The Gemini icon in the top-right of the docs UI
- **Behavior:** Toggles visibility of the floating command pill (hide/show)
- When hidden, clicking the sparkle shows the pill; when visible, clicking hides it (or vice versa — implement whichever feels natural)

### Comments gutter

- **Always present** (as in `docs-ui.html`) — 280px width to the right of the page
- **When empty:** Renders empty (no placeholder needed, or a subtle "Run /review or /comment for feedback" if desired)
- **When populated:** Renders AI comments in document order (see Feature 2)

---

## Slash Commands

### Command discovery

- **Autocomplete:** When user types `/`, show a dropdown with available commands (filter as they keep typing)
- **Help icon:** A hover icon (e.g., "?" or info) with a popup listing all available commands and brief descriptions

### Default slash commands

| Command       | Behavior                                                                 |
| ------------- | ------------------------------------------------------------------------ |
| `/improve`    | Rewrite the target text to be clearer, more concise, more professional   |
| `/expand`     | Elaborate on the target text with more detail                            |
| `/summarize`  | Condense the target text                                                 |
| `/brainstorm` | Generate ideas related to the selection; **insert as bullets** right after the selection. Selection = the topic/prompt to brainstorm about |
| `/review`     | Generate AI comments on the **full document** (see Feature 2)            |
| `/comment`    | **Expects text after** — e.g. `/comment look for passive voice` or `/comment improve clarity`. Reads the whole doc and adds comments where it sees fit based on the user's instructions |

### Selection-aware behavior

- **With text selected:** Command applies only to the selected text (or uses selection as context, e.g. `/brainstorm` topic)
- **Without text selected:** Command applies to the entire document (for `/improve`, `/expand`, `/summarize`) or requires doc-level context (`/review`, `/comment`)
- Implement whatever is simplest that allows text selection and LLM calls to operate on selected text when needed
- **Empty document or empty selection:** Block the action with an error message (e.g. "Please select some text" or "Document is empty")

---

## Feature 1: Text transformation commands

### Commands: `/improve`, `/expand`, `/summarize`

- Send target text (selection or full doc) + prompt template to backend
- Replace the selection (or full document) with Gemini's response
- For `/brainstorm`: Gemini returns a bullet list; **insert as bullets** immediately after the selection (do not replace the selection)

### Freeform prompts

- User types something other than a slash command (e.g. "make this more formal")
- Send as direct prompt to Gemini with document/selection as context
- Replace selection or full doc with response (same behavior as transformation commands)

---

## Feature 2: AI-generated document comments

### Commands: `/review`, `/comment`

**`/review`**
- Full document sent to Gemini with a fixed prompt asking for passage-level feedback
- Returns structured JSON: `[{target, comment}, ...]` where `target` is an exact quote from the document

**`/comment`**
- User supplies instructions after the command, e.g. `/comment look for passive voice`
- Full document + user instructions sent to Gemini
- Same response format: `[{target, comment}, ...]`

### Expected response format

```json
[
  {"target": "The results were very good", "comment": "Consider using specific metrics instead of 'very good' — e.g., 'revenue increased 15%.'"},
  {"target": "In conclusion", "comment": "The conclusion restates the introduction. Try ending with a forward-looking statement."}
]
```

### Frontend behavior

1. Parse Gemini's JSON response
2. For each `{target, comment}`:
   - Find `target` in the document via exact string search
   - If found: highlight the passage (background color or underline), render comment in sidebar
   - If not found: skip gracefully (no crash, no render for that comment)
3. Comments listed in document order in the sidebar

### Comment interaction

- **Click a comment in the sidebar** → scroll the document to the highlighted passage
- **Click a highlight in the document** → highlight/focus the corresponding comment in the sidebar

---

## Flask Backend

### Routes

| Route             | Method | Purpose                                              |
| ----------------- | ------ | ---------------------------------------------------- |
| `GET /docs-demo/` | GET    | Serve the full-page frontend HTML                    |
| `POST /docs-demo/api/generate` | POST | Single route for all LLM calls (text + comments)    |

### Single API route: `POST /docs-demo/api/generate`

**Request body:**
```json
{
  "type": "text" | "comments",
  "prompt": "Rewrite the following text...",
  "text": "The document or selection content..."
}
```

- `type: "text"` — for `/improve`, `/expand`, `/summarize`, `/brainstorm`, freeform prompts
- `type: "comments"` — for `/review`, `/comment`; prompt includes instructions (fixed for review, user-provided for comment)

**Response for `type: "text"`:**
```json
{
  "result": "The transformed or generated text..."
}
```

**Response for `type: "comments"`:**
```json
{
  "comments": [
    {"target": "...", "comment": "..."},
    {"target": "...", "comment": "..."}
  ]
}
```

### Gemini integration

- **Model:** `gemini-3-flash-preview` (as used in `sports_schedules`)
- **Client:** `google.genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))` — same pattern as `ask_many_llms`
- **API key:** `GOOGLE_API_KEY` in `.env` (already used elsewhere in the app)

---

## Loading & error handling

### Loading state

- While waiting for Gemini: show a **spinner** in or near the command pill
- Disable the input during the request

### Error handling

- **Empty document / no selection when required:** Block with an error message in the UI
- **API failure (rate limit, timeout, etc.):** Show error message to user (e.g. "Something went wrong. Please try again.")
- Keep it simple — no retries, no elaborate error recovery

---

## Technical requirements

### CSS class prefixing

- All project-specific CSS classes must use the `docs-demo-` prefix to avoid collisions with other projects in the Flask app
- Example: `docs-demo-top-bar`, `docs-demo-toolbar-wrapper`, `docs-demo-command-pill`, etc.

### File structure

```
app/projects/docs_demo/
├── routes.py              # Flask routes: index, api/generate
├── gemini_service.py      # Thin wrapper to call Gemini (or inline in routes)
├── templates/docs_demo/
│   └── index.html         # Full-page docs UI (from docs-ui.html, prefixed)
└── static/docs_demo/
    ├── style.css          # Prefixed styles
    └── app.js             # Editor, slash commands, comments, command pill
```

---

## Out of scope

- User authentication / login
- Database persistence
- Saving documents between sessions
- localStorage for document survival
- User-defined slash commands
- Collaborative editing
- Toolbar/menu functionality (bold, italic, etc.) — cosmetic only
- Fuzzy text matching for comment anchoring
- Mobile-optimized layout

---

## Success criteria

1. User can type and edit text in a Docs-like document area
2. Floating command pill is visible (or toggled via Gemini sparkle), centered, ~2/3 doc width
3. Typing `/` shows autocomplete; help icon shows command list
4. `/improve`, `/expand`, `/summarize` replace selection or full doc with Gemini output
5. `/brainstorm` inserts bullet list after selection
6. `/review` and `/comment &lt;instructions&gt;` produce comments in the sidebar with highlighted passages
7. Click comment → scroll to passage; click passage → focus comment
8. Loading spinner during LLM calls; errors shown on failure
9. Empty doc/selection blocked with clear error
10. Full-page layout, no app chrome; all classes prefixed with `docs-demo-`
