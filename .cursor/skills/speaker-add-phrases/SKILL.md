---
name: speaker-add-phrases
description: >-
  Add phrases to the Speaker AAC app and append any new vocabulary to common.txt.
  Use when the user asks to add Speaker phrases, update the phrase library,
  add words to the speaker word list, or invokes speaker-add-phrases.
disable-model-invocation: true
---

# Speaker — add phrases

Add one or more phrases to the Speaker project and ensure every word is reachable via the letter-filter word picker.

## Files

| File | Purpose |
|------|---------|
| `app/projects/speaker/static/speaker/app.js` | `PHRASE_GROUPS` — phrase library + categories |
| `app/projects/speaker/common.txt` | Frequency-ordered word list (append new words at **end**) |

Do **not** edit `app/projects/registry.py` or routes for phrase-only changes.

## Workflow

Copy this checklist and track progress:

```
- [ ] Parse user phrases (preserve exact wording and punctuation)
- [ ] Skip exact duplicates already in PHRASE_GROUPS
- [ ] Pick category for each new phrase (or ask if unclear)
- [ ] Append phrases to the correct group in app.js
- [ ] Find words missing from core + common; append to common.txt
- [ ] Bump STORAGE_COMMON_WORDS version in app.js if common.txt changed
- [ ] Run validation script
- [ ] Summarize: phrases added, words appended, cache version
```

### 1. Parse phrases

User may paste a bullet list, one phrase per line, or a single phrase. Strip leading `-`/`*`/numbers only; **keep the phrase text exactly** (including `?`, apostrophes, capitalization).

### 2. Avoid duplicates

Before adding, search `PHRASE_GROUPS` for the same text. Ignore trailing `?` differences only if the user explicitly wants a duplicate variant — otherwise skip exact matches.

### 3. Choose category

Use the best-fitting existing group:

| Category | Examples |
|----------|----------|
| Mobility & positioning | wheelchair, bathroom, walk, bed |
| Temperature & clothing | cold, jacket, sweater, blanket |
| Food & drink | coffee, juice, hungry, lunch |
| Health & body | medicine, pain, dizzy, tissue |
| Home & devices | volume, window, door, phone, fan |
| Communication | repeat, understand, write it down |
| Feelings & social | sorry, thank you, never mind |
| Activities & outings | shower, game, read, fresh air |
| Weather & time | temperature, weather, rain, appointment, thermostat |

If a phrase fits nowhere reasonable, ask the user which category to use.

### 4. Edit app.js

Add each new phrase string to the `phrases` array inside the chosen group. Keep the same formatting style as neighboring entries (double-quoted strings, trailing commas).

Phrase IDs (`p0-0`, etc.) are generated at runtime from array index — **do not** hand-edit IDs.

### 5. Add missing words to common.txt

Extract words from new phrases:

- Split on spaces
- Strip trailing `?`, `,`, `.`, `!` from each token
- Keep apostrophes in words (`don't`, `I'm`)

A word is **already covered** if its match key exists in **either**:

- **Core words** in `CORE_WORDS` (e.g. `I`, `Please`, `Don't`, `Thank you`)
- **common.txt** (case-insensitive; treat `'`/`'`/`´` as equivalent; ignore `.` in keys)

Append only **missing** words to the **end** of `common.txt`, one word per line:

- Use straight apostrophe `'` in new entries
- Preserve user-specific casing for names/brands (`sinomed`, `PT`, `Greg`)
- Do not re-sort the file

**Do not** add a word to core words unless the user explicitly asks — default is `common.txt` only.

### 6. Bump word-list cache version

When `common.txt` changes, increment the suffix in `app.js`:

```javascript
var STORAGE_COMMON_WORDS = "speaker_common_words_v4"; // → v5, v6, …
```

This forces browsers to reload the word list from the API.

### 7. Validate

From repo root:

```bash
python3 .cursor/skills/speaker-add-phrases/scripts/check_words.py "Phrase one" "Phrase two"
```

Fix any reported missing words, then re-run until clean.

### 8. Respond to the user

Report:

- Phrases added (and category), skipped duplicates
- Words appended to `common.txt` (or "none needed")
- New `STORAGE_COMMON_WORDS` version if bumped

Do **not** commit unless the user asks.

## Notes

- **Predictions** rebuild automatically from `PHRASE_GROUPS`; no other JS changes needed for phrases alone.
- **Please** is optional at the start of phrases for "Suggested next" matching — no extra work when adding phrases.
- **Contractions**: typed `DONT` resolves to `don't` via existing `CONTRACTION_FORMS`; prefer contraction forms in phrases (`don't`, not `dont`).
- **Multi-word core entries** (`Thank you`) match as a unit in the word picker; individual words still work separately.

## Example

**User:** Add "What is the thermostat set to?"

**Actions:**

1. Add to **Weather & time** in `PHRASE_GROUPS`
2. Check words: `What`, `is`, `the`, `set`, `to` already covered; append `thermostat`
3. Bump `speaker_common_words_v4` → `v5` (or next)

**User output:**

> Added 1 phrase under Weather & time. Appended `thermostat` to common.txt. Bumped cache to v5.
