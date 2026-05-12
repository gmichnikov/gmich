# Camps — Implementation Plan

Implementation order and checkpoints for Camps v1.

**References:** Behavior and filtering rules → [prd_v1.md](./prd_v1.md). Table/column definitions → [initial_thoughts.md](./initial_thoughts.md). If code and docs disagree, update whichever is wrong—don’t let them drift silently.

Run **`flask db migrate`** and **`flask db upgrade`** yourself. Finish each phase’s **Manual checks** before starting the next one.

---

## Repo conventions

- SQL tables prefixed `camps_*`; Python classes like **`Camp`**, **`CampSession`**, …
- CSS classes prefixed `camps-*` so styling doesn’t collide with other hub projects.
- Register the Camps blueprint and import **all** Camps models in **`app/__init__.py`** for Flask‑Migrate.

---

## Roadmap

| Phase | What ships | Primary PRD pointer |
| ----- | ----------- | ------------------- |
| **1** | Models + migration | `initial_thoughts`, §2 |
| **2** | Admin `/camps/admin/` — seed **Camp type**, tags, camps, sessions, camp↔tag links | §4, §8, §11 |
| **3** | Public `GET /camps`: filters + cards + A→Z sort | §6, §7.1, §7.3 |
| **4** | `/camps/camp/<id>` and `/camps/session/<id>` | §2 goals, §7.2 |
| **5** | Friendly 404s, `price` when NULL, small polish | deferred fine points in §12 |

**Deferred from this lane:** assisted LLM entry (PRD §5 Phase 2), prettier SEO slash URLs for filters, multi‑year homepage, standalone “brand” entity.

---

## Likely modules

| File | Role |
| ---- | ---- |
| `models.py` | Tables & relationships |
| `weeks.py` | Summer 2026 Mondays + overlap helper (**Mon→Sun inclusive** vs session dates) |
| `filters.py` | Query params → filtered camp list (implements PRD §6) |
| `routes.py` (split if helpful) | Public + admin URLs |
| `forms.py` | Admin validation |

Parameter names (`?town=`, `?week=`, …) can wait until routing work (PRD §12). Weeks can use **`YYYY-MM-DD`** for that Monday (**`initial_thoughts`**).

Templates: `templates/camps/` and `templates/camps/admin/`. Styles: `static/css/camps.css`.

---

## Hub integration notes

**After models**

- Deleting a camp must remove sessions and **`camps_camp_tag`** rows (PRD §11 — hard delete).
- Deleting a tag removes its junction rows (strip associations) rather than blocking deletion.

**Admin & public routes**

- All `/camps/admin/...` endpoints: **`@login_required`** + **`@admin_required`** on reads and writes (PRD §4). Normal POST + CSRF.
- Add Camps admin link to the main "Admin" dropdown in the navbar.
- **`log_project_visit('camps', ...)`** on public **`GET /camps`** (same pattern as other projects).

---

## Phase 1 — Models & migration

Match **`initial_thoughts`** (grades **−1…12**, require city/state at validation).

### Manual checks

1. `flask db migrate` — read the revision.
2. `flask db upgrade`
3. `flask shell` — toy camp + sessions + tagged camp.

---

## Phase 2 — Admin CRUD

**Who:** admins only.** Suggested sequence:

1. `CampTagCategory` + `CampTag` endpoints/forms.
2. Ensure **Camp type** exists right after deploy (PRD §8): Add manually via Admin UI as the simplest path.
3. `Camp` CRUD with tag picker (many‑many junction).
4. `CampSession` CRUD scoped to **`camp_id`**, validate **`start_date` ≤ `end_date`**.

### Manual checks

- Tag one camp Soccer + STEM; create two camps with **different cities** sharing tags (PRD §11 multi-town).
- Delete a camp and confirm cascades behave (no orphan sessions/links).

---

## Phase 3 — Public directory (`GET /camps`)

### `weeks.py`

Enumerate NJ-ish Summer 2026 Mondays. Chip label **Week of \<Monday date\>**; intersect each calendar week (**Mon … Sun**) with inclusive session **`start_date`**…**`end_date`** (PRD §6.3).

### `filters.py` (PRD §6)

- Empty query ⇒ **all camps** (matches PRD notion of unfiltered homepage).
- When multiple facets are active, **narrow with AND**: town facet, chosen weeks facet, tag facet bundle, combined age/grade bundle—each participates when populated.
- **Tags:** selections within one category use **OR**; when ≥2 interacting categories eventually exist those category-level results combine with **AND**, and **that composite tag predicate still ANDs with** town/week/age facets (spirit of §6.1).
- **Ages ∪ grades:** if spans are provided for both, camps pass when some session overlaps ages **or** some session overlaps grades—even different rows (**§6.2**). Use inclusive integer overlap `max(lows) ≤ min(highs)`. Sparse session ages or grades omit only that slice of filtering (**§6.2** sparse rule).
- **Weeks:** OR across selected Mondays (**§6.3`).
- **Towns:** options from **`SELECT DISTINCT Camp.city`** (optional casing normalization helpers) (**§6.4**).

### Listing UI (**§7.1**, **§7.3`)

Cards show name, town/state, tag badges, optional date hint → link **`/camps/camp/<id>`**. Sort **A→Z** by camp name (simple case‑insensitive collation is plenty).
- Render **`price`** as "Contact for price" if `NULL` (simplest approach).

### Manual checks (**logged out**)

- **`GET /camps`** shows real facets + results (purge placeholder skeleton before release if Phase 4 still hasn’t stripped it).
- Exercise varied mixes: town + OR weeks + OR tags + ages only + simultaneous ages & grades (**§6** union sanity).

---

## Phase 4 — Detail pages

- **`GET /camps/camp/<id>`** — contact/details + ordered sessions (**`start_date` ASC**, **`name`**, **`id`**; PRD §7.2).
- **`GET /camps/session/<id>`** — session detail + upward link.

### Manual checks

- Accessible logged out; scramble session inserts to validate ordering edge cases.

---

## Phase 5 — Hardening

- Friendly 404 handling.
- Decide how **`price`** renders when **`NULL`**.
- Optional duplicate warning (**same name + town**).

---

## Deferred scope (explicitly out of this plan)

Captured in **`prd_v1.md` / **`initial_thoughts`:** LLM bulk ingest, fancier SEO filter URLs, richer season/year controls, heavyweight tag renaming UX, eventual brand rollup model.

---

## PRD cheat sheet

| Topic | Builds mostly in |
| ----- | ----------------- |
| §6 filters | Phase **3** |
| §7 list + cards + sort | Phase **3** |
| §7.2 camp detail ordering | Phase **4** |
| §8 admin | Phase **2** |
