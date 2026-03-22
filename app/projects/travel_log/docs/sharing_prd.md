# Travel Log — Collection sharing (PRD)

Product requirements for **sharing a collection with other users** as **editors**. This document captures decisions agreed for v1; implementation can follow in phases.

---

## Goals

- Let a **collection owner** invite other registered users (by **email**) to collaborate on a collection.
- **Editors** can maintain the trip journal (entries, photos, tags) without owning the collection.
- **Trust-sensitive actions** (who can access the collection at all) stay **owner-only**.
- On the **Travel Log home** page, separate **collections I own** from **collections shared with me**.

---

## Roles

| Role | Meaning |
|------|--------|
| **Owner** | The user who created the collection (`TlogCollection.user_id`). Exactly one per collection. |
| **Editor** | Invited collaborator. Stored with an explicit role value (e.g. `editor`) so **viewers** or other roles can be added later without schema churn. |

- v1 only assigns **`editor`**. Do not use implicit “everyone is editor”; the membership row must carry **`role = editor`**.

---

## What editors **can** do

- **Add** entries to the shared collection.
- **Edit** any entry in that collection (same fields as today: name, address, place details, notes, visited date, tags).
- **Delete** entries in that collection (any entry, not only their own — simplest rule).
- **Upload and remove photos** on entries in that collection.
- **Change tags** on entries in that collection.
- **See the collection** everywhere owners see it for **journal work**, including **choosing the collection on Log Place** (dropdown / picker) when creating a new entry.

---

## What editors **cannot** do

- **Invite or share** the collection with others (no access to share UI / invite API).
- **Remove** other editors (or the owner).
- **Rename** the collection.
- **Delete** the collection.

---

## What only the **owner** can do

- Open **Share** (modal) and add collaborators by email.
- **Remove** an editor’s access.
- **Rename** the collection.
- **Delete** the collection.
- (Future) Any “visibility” or “public link” settings, if added.

---

## Sharing mechanics (v1)

### Input

- Owner enters **one or more email addresses** (UX: comma-separated and/or one per line — implementation detail).
- Normalize emails the **same way** as signup/login (e.g. trim + lowercase) before lookup.

### Matching users

- For each address, look up an existing **`User`** with that email.
- **If the user exists:** grant **`editor`** on that collection (idempotent membership row with `role = editor`).
- **If the user does not exist:** **ignore** — no pending-invite table, no email sent, no in-app notification in v1.

### Duplicates

- If that user **already has editor** access: **no-op**; show a **small inline message** in the modal (e.g. “Already has access”) — no separate notification system.

### Owner in lists

- In “who has access,” show the **owner** once as **Owner** (from collection ownership).
- List **editors** separately; **do not** duplicate the owner as an editor row.

---

## UI

### Share button + modal

- **Share** control on the collection (owner-only), opens a **modal** that supports:
  - **Invite:** email input(s) + submit to add editors (per rules above).
  - **People with access:** owner row + list of editors (email, display name if available, role label).
  - **Remove editor** (owner-only, per row).

### Home page (`/travel-log` index)

- **My collections** — collections where `current_user` is the **owner**.
- **Shared with me** — collections where `current_user` is an **editor** (not owner).
- Optional polish: badge on cards (“Owner” / “Editor”) — implementation detail.

### Showing the owner to editors

Anyone using a collection **as an editor** (not the owner) should be able to see **who owns** it — so they know whose trip they’re editing and can tell shared collections apart.

**Where to show it**

1. **Collection page header** (journal list for that trip) — e.g. under or beside the collection title: *Owner: [display name]* (and optionally email — see privacy below).
2. **“Shared with me” cards** on the home list — e.g. *“[Owner name]’s collection”* or a line *Owner: [name]* so editors can distinguish trips before opening.
3. **Log Place** — when the collection picker includes shared collections, a **subtitle or group label** (e.g. *Shared — Owner: [name]*) reduces mistakes when choosing where to log.

**Share modal**

- **Owners** see the full share modal (invite, people list, remove editors).
- **Editors** do **not** get share/remove controls. Optionally show a **read-only** “Owner: …” line if editors ever open a read-only variant of the modal; **simpler v1** is to show owner **only** on the collection header (and home / Log Place as above), not in a modal for editors.

**Privacy**

- Default to the owner’s **display name** (or username) from `User`.
- Show **email** only if product policy allows (small trusted groups); otherwise name alone is enough.

---

## Data model (intended)

- New table, e.g. **`tlog_collection_member`** (name TBD), minimally:
  - `collection_id` (FK)
  - `user_id` (FK)
  - `role` — v1 values: `editor` only; reserve for `viewer` later.
  - `created_at` (optional)
  - Unique constraint on `(collection_id, user_id)`.

- **Owner** remains on **`TlogCollection.user_id`**; membership rows are **only for non-owner editors** (or owner is never inserted here — aligns with “owner shown separately”).

---

## Authorization (implementation note)

- Replace or augment checks of the form **`collection.user_id == current_user.id`** with a helper, e.g. **`can_edit_collection(user, collection)`** → owner **or** editor where editor permissions apply.
- **Owner-only** endpoints/UI: share modal, remove editor, rename collection, delete collection, invite API.
- **Editors** must pass the same checks as owners for: list/show collection, create/update/delete entry, photos, tags, Log Place collection list.

---

## When an editor is removed

- **Their past entries remain** in the collection. No deletion or reassignment of entries in v1.

---

## Out of scope (v1)

- **Pending invites** for emails not yet registered.
- **Email notifications** when shared or when someone signs up.
- **Viewer** role (schema may allow it later; no v1 UI).
- **Editors** inviting others or removing anyone.

---

## Related files (for implementers)

- Models: `app/projects/travel_log/models.py`
- Routes: `app/projects/travel_log/routes.py`
- Templates: `app/projects/travel_log/templates/travel_log/`
- Implementation plan parent: `docs/PLAN.md`, `docs/PRD.md`

---

## Implementation status

Implemented in app code (membership model, permissions, routes, UI). **Run a database migration** after pulling:

```bash
flask db migrate -m "tlog collection editors (sharing)"
flask db upgrade
```

New model: `TlogCollectionMember` (`tlog_collection_member` table).

---

## Changelog

| Date | Change |
|------|--------|
| (doc created) | Initial sharing PRD from product decisions. |
| — | Added: editors see collection owner (header, shared cards, Log Place); privacy note. |
| — | Implementation: model, APIs, share modal, index + Log Place split. |
