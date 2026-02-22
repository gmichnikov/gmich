# Kids Words – Product Requirements Document

## Overview

Kids Words is a Wordle-style game (similar to [Quordle](https://www.quordle.com/), [Octordle](https://octordle.com/), etc.) with simplified word sets so kids can play with age‑appropriate vocabulary.

---

## Core Concept

- **Same mechanics as Quordle/Octordle**: Multiple target words, shared keyboard, color feedback per word. All words are 5 letters.
- **Simplified answer sets**: Three difficulty levels control which words can be answers.
- **Shared guess list**: All valid guesses come from a combined list; only some of those can be answers.

---

## Difficulty Levels & Answer Sets

### Grade 2

- **Answers**: Only words where `data/grade2_words.json` has `"yes"`.
- **Example**: “about”, “apple”, “happy” → yes; “abate”, “abbey” → no.

### Grade 4

- **Answers**: Only words where `data/grade4_words.json` has `"yes"`.
- **Example**: “abort”, “actor”, “adapt” → yes; “abate”, “abbey” → no.

### Adult

- **Answers**: All words in the JSON files (same keys as grade 2 and 4).
- **Example**: Any word in the JSON files can be an answer.

---

## Data Files

| File | Purpose |
|------|---------|
| `data/grade2_words.json` | `{word: "yes" or "no"}` – grade 2 answers |
| `data/grade4_words.json` | Same structure – which words are answers in grade 4 |
| `data/wordle_guesses.txt` | One word per line – acceptable guesses |

**Note:** Valid guesses = **union** of JSON keys + `wordle_guesses.txt`. The two JSON files have the same keys but different `yes`/`no` values.

---

## Valid Guesses

A guess is valid if it appears in **either**:

1. **The JSON files** (all keys from `data/grade2_words.json` and `data/grade4_words.json`), or  
2. **`data/wordle_guesses.txt`**.

Valid guesses = union of both sources. Invalid guesses (not in either source) are rejected and give feedback (e.g. “Not in word list”).

---

## Game Configuration

Config is chosen **fresh each time** you start a new game (no persistence of settings).

### Number of words

User chooses **1–8** target words before play (e.g. slider or buttons).

### Number of guesses

- Formula: `# words + 5`
- Examples: 1 word → 6 guesses; 4 words → 9 guesses; 8 words → 13 guesses.

---

## Gameplay Flow (like Quordle/Octordle)

1. **Setup**
   - Select difficulty: Grade 2, Grade 4, or Adult.
   - Select number of words: 1–8.

2. **Play**
   - One shared guess line per attempt.
   - Each guess is evaluated against all active target words.
   - Color feedback per word:
     - Green: correct letter, correct position
     - Yellow: correct letter, wrong position
     - Gray: letter not in that word

3. **Win**
   - Win when all target words are solved (any order).

4. **Lose**
   - Lose when guesses run out with at least one unsolved word. Reveal all answers on loss (like Wordle).

5. **Reset**
   - Option to start a new game (choose difficulty + word count again).

---

## Technical Notes

- **No login** – play as guest.
- **No database** – all state in memory; persistence via `localStorage`.
- **Client-side** – answer selection and validation can run in the browser; server can serve data and static assets.

---

## Decided

### Answer Selection

- **No duplicate answers** – the same word cannot appear twice as an answer in one game.

- **Close words OK** – similar words like "apple" and "apply" are allowed as separate answers.
- **Random selection** – answers chosen at random from the valid answer set.

### Valid Guesses

- **Union** – valid guesses = all keys from the JSON files + all words in `data/wordle_guesses.txt`. Merge both when building the guess list.

### UI/UX

- **Layout** – Quordle-style grid (e.g. 2×2 for 4 words, 2×4 for 8).
- **Mobile** – stacked, but up to two words can fit side by side.
- **Word labels** – no "Word 1 of 4" display.
- **Virtual keyboard** – yes. Each letter shows its best status across all words: green (correct somewhere) > yellow (in word, wrong spot) > gray (not in word).

### Features

- **Hard mode** – not for now.
- **Sound/haptics** – not for now.
- **Share results** – no.
- **Refresh Wordle list** – no; use current `data/wordle_guesses.txt`.
- **More grade levels** – maybe later.

### Persistence

- **Game state** – persist to `localStorage` so refresh doesn't lose progress.
- **Stats** – track games played and win rate in `localStorage`.
- **Settings** – difficulty and word count chosen fresh each new game (not persisted).

---

## Summary of Requirements

| Item | Requirement |
|------|-------------|
| Difficulty | Grade 2, Grade 4, Adult (chosen each new game) |
| Answer sets | From JSON `yes`/`no`; Adult = all words |
| Valid guesses | Union of JSON keys + `data/wordle_guesses.txt` |
| Duplicate answers | Not allowed |
| Words per game | 1–8 (user choice each new game) |
| Guesses | `# words + 5` |
| Layout | Quordle-style grid; mobile: stacked, 2 per row max |
| Virtual keyboard | Yes, with colored feedback |
| localStorage | Game state + stats |
| Share | No |
| Auth / DB | None |
| Platform | Web, client-heavy |
