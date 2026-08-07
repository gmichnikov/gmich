---
name: git-commit-message
description: >-
  Inspect git changes and output a succinct commit message as gc "message".
  Use when the user asks for a commit message, says gc, wants help committing,
  or invokes git-commit-message.
disable-model-invocation: true
---

# Git commit message

Produce a **succinct** commit message for the user's current changes and output it in this exact format:

```text
gc "<message here>"
```

The user can copy-paste that line to commit. **Do not run `git commit` unless they explicitly ask you to commit.**

## Workflow

1. Inspect changes (run in parallel when possible):
   - `git status`
   - `git diff` (unstaged)
   - `git diff --cached` (staged)
   - `git log -5 --oneline` (match repo tone)

2. If staged and unstaged both exist, base the message on **staged** changes if the user is about to commit; otherwise cover **all** current changes and say so briefly if needed.

3. Draft the message:
   - 1–2 sentences max inside the quotes
   - Focus on **why** / user-visible outcome, not a file list
   - Use imperative mood ("Add…", "Fix…", "Replace…")
   - Accurate verb: add vs update vs fix vs refactor

4. **Output only** the `gc "..."` line (optional: one short line above it if staged vs unstaged is ambiguous).

## Rules

- Never commit secrets (.env, credentials, keys). Warn if those files are in the diff.
- Do not commit, push, or stage unless the user explicitly asks.
- Do not wrap the `gc` line in extra markdown fences unless the user prefers that — a plain `gc "..."` line is the deliverable.
- Escape double quotes inside the message with `\"` or rephrase to avoid nested quotes.

## Examples

**Input:** Speaker letter-filter UI, new phrases, bigger touch targets.

**Output:**

```text
gc "Replace Speaker spell keyboard with letter filter and expand AAC phrases and sizing."
```

**Input:** Pin More/Less only on empty sentence; yellow bar shows 10 suggestions.

**Output:**

```text
gc "Tune Speaker predictions: empty-state More/Less pins and 10 suggestion chips."
```
