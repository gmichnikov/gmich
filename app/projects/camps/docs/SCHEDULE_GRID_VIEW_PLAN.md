# Schedule grid view (camps × weeks)

Alternate public UI to cards: **rows = camps**, **columns = weeks (Monday-based)**. Each cell encodes whether the camp runs that week, **half vs full day**, and **days per week (3–5)** via fill width inside the cell.

## Decisions

| Topic | Choice |
|--------|--------|
| Week identity | Monday of the week; column header **Monday only** (e.g. **`Jun 16`**). |
| Week range | **Min / max** of session dates across **filtered** camps (same filter query as cards). |
| Session bounds | All sessions **Mon–Fri**; no weekend handling. |
| Cell “on” | Session date range overlaps that column’s **Monday–Friday** dates (column keyed by the Monday). |
| Half vs full day | **Half** = **≤ 4.5 hours** scheduled per day (`start_time`→`end_time`). **Full** = longer, OR **missing times** (treat as full day). |
| Days per week | **Count** of distinct weekdays the session runs **in that calendar week** (within M–F), **3–5** expected. |
| Multiple sessions / same week | **Out of scope** (not present in data today). |
| Legend | **Minimal**: only clarify half vs full (no full legend for bar width initially). |
| View switch | **URL only**: `view=timeline` alongside existing filter params. |
| Which camps appear | Same as **filtered** camp list. **Dataset:** every camp has at least one session (no empty-session rows to handle). |
| Scale | **~20 camps** on desktop. **Mobile:** horizontal scroll + **sticky first column** (camp name). |

## Visual encoding (v1)

- **Grid**: one row per camp, one column per week in the computed range.
- **Off week**: empty / neutral cell.
- **On week**: inner bar **width ∝ days / 5** (e.g. 3 days ⇒ 60%, left-aligned); track shows **lighter “in session” / darker “not that week”** so partial weeks read clearly.
- **Half vs full**: **half-day bars ~50% height** (same row); full-day bars full height; **stripes + hue** on half so it is not color-only.

## Deferred

- **Hover / tooltip** with session details (step 2).
- “Current week” marker, map view, other layouts.

## Implementation notes

- Reuse the same **`apply_filters`** / query path as the card index so behavior matches.
- Compute per **(camp, week)** aggregates server-side or once in the template from loaded sessions—keep logic in one place.

---

*Last updated from product Q&A — schedule grid specification.*
