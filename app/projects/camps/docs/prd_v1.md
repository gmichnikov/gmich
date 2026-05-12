# PRD: Camps — Summer Camp Aggregator (v1)

**Status:** Draft  
**Last Updated:** May 2026  
**Depends on:** [initial_thoughts.md](./initial_thoughts.md) — canonical table fields

---

## 1. Summary

**Camps** is a hub project for discovering summer camps via a **filterable directory** plus **readable camp and session pages**. Data is entered by **admins only**. Public `/camps` stays **logged-out friendly**; create/edit tooling uses **hub login + platform admin** (`login_required` + `admin_required`).

**Simplicity principle:** Small set of orthogonal filter dimensions + clear semantics for how they combine—not maps, scraping, slug SEO, or camp self-service yet.

---

## 2. Goals (v1)

- Public **`/camps`** directory with filtering (composition rules §6).
- **`/camps/camp/<id>`**: camp landing page listing its sessions with links onward.
- **`/camps/session/<id>`**: session detail page (link back to parent camp).
- **Admin-only** CRUD forms for camps, sessions, tag categories & tags; **summer week filter options** are hardcoded (§6.3).
- Conventions: `camps_*` tables, **`camps-*` CSS**, models imported in `app/__init__.py`.

---

## 3. Non-goals (v1)

- Scraping, parent submissions, monetization/leads/maps/slug SEO (`initial_thoughts`).
- Robust tag rename/delete tooling (defer UX for normalizing typo’d tags until after data volume hurts).

---

## 4. Roles & hub fit

| Role              | Access |
| ----------------- | ------ |
| **Anonymous user** | Directory + detail pages. |
| **Platform admin** | `/camps/admin/...` CRUD (`auth` unchanged from rest of hub). |

**Registry:** `auth_required: False` project URL for the listing; admins log in separately as today.

---

## 5. Phased delivery

### Phase 1 (v1)

- Models including **Camp**, **CampSession**, **CampTagCategory**, **CampTag**, **`camps_camp_tag`** junction (see `initial_thoughts`).
- Forms-only admin UX.
- Public pages + filtering per §§6–7.

### Phase 2 (optional accelerator)

**Plain language:** Phase 2 is only an admin convenience—you **paste unstructured text** (email copy, bullets, flyer notes). An **AI draft** guesses camps, sessions, tags, towns, weeks, etc.; you review in the browser, tweak anything wrong, click **Approve** → normal form validation runs and rows are inserted. Nothing goes live automatically without your OK.

Anything about “audit logging / retention for compliance” waits until Phase 2 is real; Phase 1 has no AI.

---

## 6. Filter semantics (canonical)

A **facet** is one independent filter **knob** or **dimension** you can use to narrow the camp list — e.g. town, summer weeks, child age span, grade span, camp-type tags. This is normal **faceted search** vocabulary (like filter sidebars on shopping sites): several facets stack together. Unless noted, **different facets combine with logical AND.**

**Tag categories** (e.g. Camp type) are **not** the same thing as facets: a single facet can expose “pick any tags from this category,” and with **only one** category in v1, multi-select there is simply **OR among those tags**—**AND across tag categories** only matters once **two+ categories** both have something selected.

**Unfiltered directory:** No query params (or cleared filters) ⇒ list **every camp** currently in the database (v1 data is NJ-only by convention, not necessarily enforced with a facet).

### 6.1 Tag facets (camp-level tags grouped by category)

Tags live on **camp** (`initial_thoughts`). Each tag belongs to a **CampTagCategory** (for v1, expect at least **Camp type**).

- **Within one category:** If multiple tags selected (e.g. Soccer **or** Theater), a camp qualifies if its tag set satisfies **ANY** (**OR**) of those selections.
- **Across tag categories:** If the user selects tags from **Camp type** and also from another category (e.g. future **Facility**), the camp must satisfy **both** category selections (**AND**). This is unrelated to combining **town** or **week** facets—those still **AND** with the whole tag outcome as usual.

**Examples**

- Soccer OR Theater ⇒ OR within `Camp type`.
- Soccer AND “Overnight-capable tags” ⇒ AND across categories once the second bucket exists.

**URL sketch:** Repeated params keyed by category or `type_tag=` style—implement with namespaced query keys so future categories remain clear (finalize at build time).

---

### 6.2 Age and grade (**special facet**)

Two optional inputs on the UI: an **age span** and a **grade span** (query param names may differ from DB columns—avoid confusion in implementation). Both use **inclusive integer** ranges matching session fields.

**Interval overlap:** closed ranges **`[low, high]`** overlap iff **`max(low₁, low₂) ≤ min(high₁, high₂)`** (same rule for ages and grades separately).

Stored grade scale on sessions: Pre-K = `-1`, K = `0`, grades **1–12**.

**When BOTH age and grade filters are actively set:**

- A camp qualifies if **at least one** of its sessions matches **either** the age criterion **OR** the grade criterion (logical **union** / OR between these two knobs).

So “filter ages 4–8 **and** filter grades Pre-K–3rd” ⇒ show camps where **some session** overlaps the age span **or some session** overlaps the grade span (not requiring **one** session to satisfy both).

When only one knob is present, behave as intuitive half of the rule.

For **entered data**, treat **sessions as having sensible age or grade bounds** whenever the camp lists restrictions—it is reasonable to omit extra UX for sparse nulls in v1. If age/grade is missing entirely on a session, exclude that session from facet match for **that knob** only (narrow interpretation).

---

### 6.3 Summer week facet (**filter only**; session dates unchanged)

Sessions continue to use their real **`start_date` / `end_date`**. This facet is only how parents slice the directory.

- **Options are hardcoded** in app code; **v1 = Summer 2026 only** (more years = copy the pattern + directory season control later; DB/admin weeks still out of scope for v1).
- Each option is **one calendar week anchored on Monday**. **Label:** **`Week of \<that Monday’s calendar date\>`** (e.g. “Week of June 16, 2026”).
- **Date span for overlap:** that **Monday through the following Sunday**, **inclusive**.
- **Overlap rule:** a session matches a week if **`[session.start_date, session.end_date]`** (inclusive) **intersects** that Mon–Sun range.
- **Multiple weeks selected ⇒ OR** among those weeks.
- **v1 catalog:** Assume **Summer 2026 only** — hardcoded Monday-week list targets **that** calendar year only; adding **2027+** implies duplicating/expanding coded weeks and introducing a directory **season-year** control later.

The **exact list of Mondays** included per summer (first/last Monday of the NJ window each year) is an implementation detail—chosen so the UX covers typical June–August-ish camp coverage.

Combined with §6.1 facets with **AND** (week facet AND tag facet AND geography…).

---

### 6.4 Geography (**v1 = NJ**) — towns from data

- **State treated as NJ** for first launch (enforce in UX or constrain admin entry).
- **Town filter:** enumerated **distinct camps’ `camp.city`** (normalized casing)—no substring search initially.
- Combination with everything else ⇒ **AND** (standard facet intersection).

*(Future multi-state repeats same pattern.)*

---

## 7. List presentation & sort

### 7.1 Directory rows

Brief card: camp name; town/state; abbreviated tag badges; cue like “sessions Jun–Aug” optional.

Links to **`/camps/camp/<id>`**.

### 7.2 Camp detail page

Must list **every** session for that camp, ordered **`start_date` ascending**, then stable tie-break (**session `name`**, then **`id`**). Each row links to **`/camps/session/<id>`**.

### 7.3 Directory sort default

Stable **alphabetical by camp name** until analytics suggest otherwise—or “nearest upcoming session starts soon” gated behind week filter adoption.

---

## 8. Admin UX (Phase 1)

Navigation sketch: **`/camps/admin`** dashboard → Camps list/edit → Sessions child forms **or session edit page** linking parent camp → Tag categories + tags CRUD minimal (create only + assign on camp acceptable if simpler).

Seed **one** category on first deploy (**Camp type**) so tags attach immediately—more categories optional later.

Defer sophisticated tag rename/delete policy.

---

## 9. Assisted entry recap (Phase 2)

Paste → propose structured rows → you edit → save. No autonomy for model to mutate DB unchecked.

---

## 10. Success criteria

- Admin inserts camp + sessions + tags without SQL.
- Parent without guidance gets correct results from combined filters (**OR** inside tag-category + week multiplicity, **union** rule for age ∪ grade together, **AND** across facets).

---

## 11. Resolved product decisions

| Topic | Decision |
| ----- | -------- |
| Scraping | Off |
| Multi-town same brand | **Separate Camp rows per location** in v1 (one city per camp); share tags / naming pattern; grouping under a “brand” entity later if needed |
| Resource URLs | **`/camps/camp/<id>`** + **`/camps/session/<id>`**; filters stay **`/camps?`** |
| Tags | Camp-level; **`CampTagCategory` + CampTag`; OR within category, AND across |
| Categories v1 focus | **`Camp type`** seeded; **flat** tags only (Soccer / STEM / Overnight as siblings). **No** two-level nesting (Sports → Soccer) in v1—would complicate UX; add sibling tags (“Soccer”) or split into a **second category** later if needed |
| Grade storage | **`grade_min` / `grade_max`** as ints: Pre-K `-1`, K `0`, `1`…`12`; inclusive overlap |
| Age storage | **`age_min` / `age_max`** as whole-year **ints**; inclusive overlap vs filter ranges |
| Age + grade facets | Applied as **(session matches age) ∨ (session matches grade)** whenever both knobs set |
| Other facets | Combine with age/grade/tags/week/geo using **AND** |
| Weeks | Multiple weeks ⇒ **OR**; each week **Mon–Sun** with label **Week of \<Monday date\>**; **hardcoded** for **Summer 2026** in v1 |
| Season / year | **Year** always on session **`start_date` / `end_date`**. **v1:** all data **2026**; **no** public year filter; **2027+** adds season-year UI + week lists later |
| Geo v1 | **NJ**; towns = distinct city values driven from camps |
| Town filter | Exhaustive selectable list—not free-text substring |
| Tag rename/delete tooling | Deferred post-v1 |
| Admin enforcement “must be Summer 2026” | **None**—no bespoke extra validation beyond normal form checks |
| Session age vs grade completeness | Operators enter **meaningful bands** habitually (**age or grade** as appropriate); sparse null combos are acceptable edge paths only |
| Deleting camps | **Easiest sensible default**: hard delete camps with **sessions + tag links removed** DB-side (FK cascade)—no archival flag requirement in v1 |

---

## 12. Remaining finer points (engineering / polish)

Pick at implementation—not blockers:

- Exact **query param names** mirroring facets (readable + stable bookmarks)  
- Choosing the **first and last Monday** in the coded summer-week list each **season year**  
- Whether session pages use flat `/camps/session/<id>` only or also nested URLs for breadcrumbs  

---

Anything else?

- Data quality safeguards in admin (**warn on overlapping nonsense sessions**) optional.  
- When multiple seasons exist, align **admin session dates** and **week filter year** so listings never mix years unintentionally.  
