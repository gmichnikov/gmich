# Summer Camp Aggregator — Product Planning Notes

Product framing and **[prd_v1.md](./prd_v1.md)** + **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)** carry phased delivery detail.

## The Problem

Parents have no good way to find a comprehensive list of summer camps near them. Existing platforms like ActivityHero only show camps that have opted in to their marketplace, leaving out the majority of camps — especially well-established ones that fill via word of mouth and have no incentive to pay for listings. The Google Flights equivalent for summer camps does not exist.

## The Opportunity

- A parent-first discovery tool that aggregates all camps in a geography, regardless of whether the camp participates
- Data entered manually (mostly by you)—no scraping pipeline assumed for now
- Hyperlocal to start (e.g. one metro area), then expand
- Monetization likely via camps paying for leads or featured listings, not charging parents directly

---

## Data Models

Table names namespaced (`camps_*`, e.g. `camps_camp`, `camps_session`, `camps_tag_category`, `camps_tag`, `camps_camp_tag`).

### Camp

The core entity representing a camp organization.

| Field       | Required | Notes                          |
| ----------- | -------- | ------------------------------ |
| id          | Yes      | Primary key                    |
| name        | Yes      |                                |
| website_url | No       |                                |
| email       | No       |                                |
| phone       | No       |                                |
| address     | No       |                                |
| city        | Yes      | Normalize to consistent casing (“town” filter in UI builds from distinct cities in data) |
| state       | Yes      | Two-letter code e.g. "NJ"      |
| zip         | No       |                                |

**v1 geography:** Assume **NJ only** initially; towns list filter is built from camps in the dataset (distinct `city` values).

**Same operator, multiple towns:** One **physical offering** ⇒ one **Camp** row (camp has a single city/address today; sessions don’t carry their own town). Examples: **“Acme Camps — Whippany”** and **“Acme Camps — Short Hills”** as two camps; reuse the **same tags** so discovery lines up; a shared “brand” model is deferred.

Tags are assigned at **camp level** (not per session). Filters use tag **categories** (see below).

---

### CampSession

A specific time-bounded program a camp runs. One camp can have many sessions.

| Field      | Required | Notes                                                                 |
| ---------- | -------- | --------------------------------------------------------------------- |
| id         | Yes      | Primary key                                                           |
| camp_id    | Yes      | Foreign key → Camp                                                    |
| name       | No       | e.g. "Session 1", "Robotics Week"                                     |
| start_date | Yes      | Calendar date **includes year** (canonical “which summer”)              |
| end_date   | Yes      | Calendar date **includes year**                                       |
| start_time | No       | Daily start time local to camp location, e.g. 9:00am                  |
| end_time   | No       | Daily end time local to camp location, e.g. 3:00pm                   |
| age_min    | No       | Integer **years**, inclusive overlap vs filter (semantics below); **expect** entries to fill age and/or grade for real camps |
| age_max    | No       | Integer **years**, inclusive overlap vs filter (semantics below); **expect** entries to fill age and/or grade for real camps |
| grade_min  | No       | Integer overlap filtering (scale below)                               |
| grade_max  | No       | Integer overlap filtering (scale below)                              |
| price      | No       |                                                                       |

**Age (v1, stored as integers):** Typical **whole-year ages** (`4` … `12`, etc.). **Overlap semantics are inclusive** on both endpoints (`age_min ≤ child_age ≤ age_max` when evaluating a filter range against a session’s band). Matching does **not** depend on campers’ birthdays mid-session—that level of fidelity is deferred. Operators should fill **meaningful age and/or grade** ranges for normal listings.

**Grade scale (v1, stored as integers):** Pre-K = `-1`, Kindergarten = `0`, grades **1–12** = `1` … `12`. Overlap semantics are inclusive on both endpoints (`grade_min ≤ x ≤ grade_max`). Admin UI maps labels ⇄ ints.

**Season year:** “Which summer” is always identifiable from **`start_date` / `end_date`**. **v1** assumes **everything in the catalog is Summer 2026**; no separate year picker on the public directory. The **Monday week filter** is hardcoded for **that 2026** window only. When you later host **multiple summers**, add an explicit directory **season-year** facet (and week lists keyed by year).

Note: `start_time` / `end_time` are session-level fields even though many camps use the same hours across all sessions.

---

### CampTagCategory

Groups tags so filtering can combine **OR within a category** with **AND across categories** (see [prd_v1.md](./prd_v1.md)).

| Field | Required | Notes                                                                          |
| ----- | -------- | ------------------------------------------------------------------------------ |
| id    | Yes      | Primary key                                                                    |
| name  | Yes      | Globally unique, e.g. `Camp type`                                              |

For **v1**, **`Camp type`** is the seeded category (**flat tags only** — e.g. Soccer, STEM, Overnight as siblings; **no** parent/child like Sports→Soccer). To group “sport” intuition in the UX, rely on sibling tags (**Soccer**) or add a **second category** later; hierarchy is intentionally out of scope for v1.

---

### CampTag

Belongs to one category. Many-to-many with **Camp** only (sessions inherit their camp’s tags for discovery).

No separate slug for now—query params carry ids once filtering is wired (see PRD).

| Field        | Required | Notes                                      |
| ------------ | -------- | ------------------------------------------ |
| id           | Yes      | Primary key                                |
| category_id  | Yes      | Foreign key → CampTagCategory              |
| name         | Yes      | Unique **within** `category_id`            |

---

### CampTagAssignment

Join table connecting camps to tags.

| Field   | Required | Notes              |
| ------- | -------- | ------------------ |
| camp_id | Yes      | Foreign key → Camp |
| tag_id  | Yes      | Foreign key → CampTag |

Composite primary key `(camp_id, tag_id)` (or surrogate id).

---

## Public URLs

### Filtering: query params on the directory **only**

List + filters remain on **`/camps?…`** — see PRD for exact filter algebra (tags by category, weeks, age/grade union, geography).

### Readable pages for resources

Separate paths for reading—**does not duplicate filter state**:

- **`/camps/camp/<camp_id>`** — camp overview plus list of sessions (links to session pages).
- **`/camps/session/<session_id>`** — one session detail (shows parent camp link).

(Filter composition stays bookmarkable via `/camps?…` only.)

---

## URL and Routing Structure (historical rationale)

Originally: path-based URLs were deferred for filtering to avoid ambiguity between towns and identifiers. That still applies to **filters**.

**Examples (illustrative; param names finalized in PRD):**

```
/camps?town=Summit&type_tag=12&type_tag=7&week=2026-06-15&week=2026-07-07…
```

- `town` aligns with normalized `camp.city`; v1 sourced from NJ data only.
- `week=` values encode the **Monday** starting that filter week (**ISO calendar date**, `YYYY-MM-DD`) so bookmarks are stable; the UI labels each option **Week of** that Monday’s date (e.g. Week of June 16, 2026).

**Rationale (filters on `/camps`):**

- Composable, shareable search URLs
- Simpler than encoding every dimension in segments
- Path-based SEO for **browse** combos remains a future optimization once traffic justifies it
