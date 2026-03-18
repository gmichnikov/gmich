# Gemini-Powered Google Docs Demo

## Project Goal

Build a web-based demo that recreates a Google Docs-like editing experience with two AI-powered features using Gemini:

1. **Slash commands via a bottom command bar** — A Gemini input bar at the bottom of the editor (similar to the latest Google Docs AI bar) where users can type freeform prompts or `/` slash commands to transform, generate, or manipulate document content.
2. **AI-generated document comments** — Triggered via a slash command (e.g., `/review`), Gemini reads the document and returns paragraph-level feedback rendered as Google Docs-style comments in a sidebar.

---

## Architecture Decisions

### Frontend-only state (no Postgres, no login)

- This is a demo, not a production app. No need for user accounts, saved documents, or persistent data.
- All document state lives in memory (or `localStorage` for refresh survival if desired).
- Slash command definitions are hardcoded in a JS config object.
- AI-generated comments are ephemeral — generated on demand, not saved.
- **Upgrade path:** If the demo is successful, Postgres and auth can be added later for persistence, user-specific commands, etc.

### Thin Flask backend (API proxy only)

- Flask serves the frontend and provides **2-3 API routes** that proxy requests to the Gemini API.
- This keeps the Gemini API key server-side and out of the browser.
- No database, no session management, no auth middleware needed.
- The Flask layer is intentionally minimal — just a pass-through to Gemini.

### No editor library (no TipTap, no Quill)

- Priority is speed and simplicity over editor polish.
- Use a `contenteditable` div styled to look like a Google Docs page.
- Skip structured document models, plugin systems, etc.
- The focus of the demo is the AI features, not the editor itself.

---

## UI Layout

```
┌──────────────────────────────────────────────────┐
│  Toolbar (mostly cosmetic — bold, italic, etc.)  │
├────────────────────────────────┬─────────────────┤
│                                │                 │
│   contenteditable div          │   Sidebar:      │
│   (the "document")             │   AI Comments   │
│                                │                 │
│   - White page styling         │   - Each comment│
│   - Clean typography           │     anchored to │
│   - Highlighted passages       │     a passage   │
│     (when comments exist)      │   - Click to    │
│                                │     scroll/     │
│                                │     highlight   │
│                                │                 │
├────────────────────────────────┴─────────────────┤
│  Gemini Command Bar                              │
│  [/ Type a command or ask Gemini anything...]     │
└──────────────────────────────────────────────────┘
```

---

## Feature 1: Gemini Command Bar (Bottom Bar)

### How it works

- A text input fixed to the bottom of the screen, styled like the Google Docs Gemini bar.
- The user can type:
  - **Slash commands** (e.g., `/improve`, `/expand`) — recognized by the `/` prefix, matched against a predefined list, and executed with a specific prompt template.
  - **Freeform prompts** (e.g., "make this more formal") — sent directly to Gemini with the document content as context.

### Selection-aware behavior

- **With text selected in the document:** The command applies only to the selected text. The selection persists in the `contenteditable` div even when the user focuses the bottom bar input. Retrieve it with `window.getSelection()`.
- **Without text selected:** The command applies to the entire document.

### Default slash commands

| Command       | Behavior                                                  |
| ------------- | --------------------------------------------------------- |
| `/improve`    | Rewrite the target text to be clearer                     |
| `/expand`     | Elaborate on the target text                              |
| `/summarize`  | Condense the target text                                  |
| `/brainstorm` | Generate ideas related to the content                     |
| `/review`     | Generate AI comments on the full document (see Feature 2) |

### Slash command definitions

Stored as a simple JS object, e.g.:

```javascript
const SLASH_COMMANDS = {
  "/improve": {
    label: "Improve writing",
    prompt:
      "Rewrite the following text to be clearer, more concise, and more professional. Return only the improved text:\n\n{text}",
  },
  "/expand": {
    label: "Expand",
    prompt:
      "Elaborate on the following text with more detail and supporting points. Return only the expanded text:\n\n{text}",
  },
  // ...
};
```

### Response handling

- For text-transformation commands (`/improve`, `/expand`, `/summarize`, `/brainstorm`): Replace the selected text (or full document) with Gemini's response.
- For `/review`: Parse the response as a comment array and render in the sidebar (see Feature 2).

---

## Feature 2: AI-Generated Document Comments

### How it works

1. User types `/review` in the command bar.
2. The full document text is sent to Gemini with a prompt asking for passage-level feedback.
3. Gemini returns structured JSON: an array of `{target, comment}` objects where `target` is an exact quote from the document and `comment` is the feedback.
4. The frontend:
   - Finds each `target` string in the document via string search.
   - Highlights the matched passage (background color or underline).
   - Renders the comment in the sidebar, visually anchored to the highlight.

### Expected Gemini response format

```json
[
  {
    "target": "The results were very good",
    "comment": "Consider using specific metrics instead of 'very good' — e.g., 'revenue increased 15%.'"
  },
  {
    "target": "In conclusion",
    "comment": "The conclusion restates the introduction. Try ending with a forward-looking statement or call to action."
  }
]
```

### Comment interaction

- **Click a comment in the sidebar** → scroll the document to the highlighted passage.
- **Click a highlight in the document** → highlight the corresponding comment in the sidebar.
- Comments are listed in document order in the sidebar (no complex positional anchoring needed).

### Handling imperfect matches

- Prompt Gemini to quote the target text exactly.
- If a target string isn't found in the document, skip it gracefully (don't crash, just don't render that comment).
- For the demo, exact string matching is sufficient. Fuzzy matching is a future enhancement.

---

## Flask Backend

### Routes

| Route           | Method | Purpose                                                                                                    |
| --------------- | ------ | ---------------------------------------------------------------------------------------------------------- |
| `/`             | GET    | Serve the frontend HTML                                                                                    |
| `/api/generate` | POST   | Proxy slash commands and freeform prompts to Gemini                                                        |
| `/api/feedback` | POST   | Proxy `/review` requests to Gemini (could also just use `/api/generate` with a different prompt structure) |

**Note:** `/api/generate` and `/api/feedback` could be a single route if preferred. The separation is optional — it just makes it clearer what each call does.

### Request/response shape (example)

**`/api/generate`**

```
POST /api/generate
{
  "prompt": "Rewrite the following text to be clearer...",
  "text": "The results were very good and we think..."
}

Response:
{
  "result": "Revenue increased by 15%, exceeding projections..."
}
```

**`/api/feedback`**

```
POST /api/feedback
{
  "text": "<full document content>"
}

Response:
{
  "comments": [
    {"target": "...", "comment": "..."},
    {"target": "...", "comment": "..."}
  ]
}
```

### Gemini API integration

- Use the Gemini API (Google's `generativelanguage` endpoint or the `google-generativeai` Python SDK).
- API key stored as an environment variable, never sent to the frontend.
- Each Flask route constructs the appropriate prompt, calls Gemini, and returns the response.

---

## Tech Stack

| Layer    | Technology            | Notes                              |
| -------- | --------------------- | ---------------------------------- |
| Frontend | Vanilla JS + HTML/CSS | No frameworks, no editor libraries |
| Backend  | Flask (Python)        | Minimal — just API proxy routes    |
| AI       | Gemini API            | Called server-side from Flask      |
| Database | None                  | All state is ephemeral / in-memory |
| Auth     | None                  | No login required                  |

---

## File Structure (suggested)

```
project/
├── app.py                  # Flask app — routes and Gemini proxy
├── .env                    # GEMINI_API_KEY (gitignored)
├── static/
│   ├── style.css           # All styles — page, toolbar, sidebar, command bar
│   └── app.js              # All frontend logic — editor, commands, comments
└── templates/
    └── index.html          # Main page template
```

---

## Out of Scope (for now)

- User authentication / login
- Postgres or any database
- Saving documents between sessions
- User-defined slash commands (all commands are hardcoded)
- Collaborative editing / real-time sync
- Rich formatting logic (bold/italic/headings are cosmetic only)
- Fuzzy text matching for comment anchoring
- Mobile-optimized layout
