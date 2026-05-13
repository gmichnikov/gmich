# LLM prompt: camp JSON for import

Copy the **Prompt for the model** section into your LLM together with your tag list and camp source material. The JSON shape matches the Camps admin import (see `ImportCampForm` / `import_camp` in `routes.py`).

---

## Prompt for the model

You are a careful data-entry assistant. Your job is to produce **valid JSON** that I can paste into a “Camp import” tool for a **Summer 2026** camp directory in **New Jersey** (most camps are NJ; use the city/state given in the source).

### Output rules (critical)

1. Reply with **only JSON**—no markdown fences, no commentary before or after.
2. Return **one camp** as a **single JSON object**, OR multiple camps as a **JSON array of objects**.
3. Use **double-quoted** keys and strings. No trailing commas.
4. Omit unknown fields or set them to `null` (do not invent email/phone/URL).
5. **Required for each camp:** `name`, `city`. Import fails without both.
6. **`state`:** use two-letter USPS code; default **`"NJ"`** if the source does not say otherwise and the camp is clearly local to this directory.
7. **Duplicate handling:** In our database, **(name + city)** must be unique. Match spelling/capitalization of the source for `name` and `city` so we do not accidentally duplicate an existing camp.

### Camp object schema

```json
{
  "name": "string (required)",
  "city": "string (required)",
  "state": "string, optional, default NJ",
  "zip": "string or null",
  "address": "string or null",
  "website_url": "string or null (full https URL if known)",
  "email": "string or null",
  "phone": "string or null",
  "tags": [
    { "category": "exact category name from allowed list", "name": "exact tag name from allowed list" }
  ],
  "sessions": []
}
```

### Sessions

Each session is one **enrollment block** (often one week). Use **one session object per distinct date range** we should list.

- **`start_date` / `end_date`:** required on each session. Format **`YYYY-MM-DD`**. `start_date` must be **on or before** `end_date`.
- **Year:** assume **2026** when the source only gives month/day or “summer 2026”.
- **Weekly camps:** If the source says “each week Mon–Fri” with the same times/price/ages, create **one session per week** with explicit dates (do not use ranges like “every week in July” inside one session—split into multiple objects).
- **`name`:** optional string (e.g. `"Week 1"`, `"Robotics Week"`, or `null` if unnamed).
- **`start_time` / `end_time`:** optional. Prefer **24-hour ISO local time** as `"HH:MM:SS"` (e.g. `"09:00:00"`, `"15:30:00"`). You may also use `"HH:MM"`. If unknown, use `null` for that field—do not guess.
- **`age_min` / `age_max`:** optional integers (years). Use inclusive bounds when the source says “ages 7–12”.
- **`grade_min` / `grade_max`:** optional integers, **using this encoding (critical)**:
  - **`-1`** = Pre-K
  - **`0`** = Kindergarten
  - **`1`–`12`** = grades 1–12  
  If the source says “entering 3rd grade”, map to the grade **for summer 2026** as best you can; if ambiguous (e.g. “rising K”), prefer ages if given, or choose the most likely integers and stay consistent.
- **`price`:** optional number (USD), **numeric** not a string (e.g. `450` or `450.00`). If “contact for pricing”, use `null`.

### Tags

Tags are **not** free text. Each tag must be an object `{ "category": "…", "name": "…" }` where **both strings match exactly** one allowed pair from the list I provide below.

- For **category**, match spelling/casing from the allowlist (admin category names).
- For **name**, our database stores tag names **lowercased**—use the exact allowed tag string (typically lowercase, e.g. `day camp`).
- Use **only** pairs from the **ALLOWED TAGS** section I paste in.
- If the source implies a tag we do not have, **omit** it rather than inventing a new tag name (imports *can* create tags, but we want consistency).
- Pick the **smallest** set of tags that honestly describes the camp.

### ALLOWED TAGS (I will paste below)

```
<<<PASTE_FROM_ADMIN_OR_BULK_EXPORT>>>
```

### SUMMER 2026 reference (optional)

If I paste Monday dates or week notes, use them when converting “week of July 6” style text to `start_date` / `end_date`.

```
<<<OPTIONAL>>>
```

### Source material for the camp(s)

```
<<<PASTE_WEBSITE_TEXT_BROCHURE_EMAIL_SCREENSHOT_OCR_ETC>>>
```

### Examples (follow this shape)

**Example A — minimal viable camp (one week, ISO times):**

```json
{
  "name": "Sample STEM Week",
  "city": "Maplewood",
  "state": "NJ",
  "website_url": "https://example.org/camp",
  "tags": [
    { "category": "Type", "name": "day camp" }
  ],
  "sessions": [
    {
      "name": "Week of July 6",
      "start_date": "2026-07-06",
      "end_date": "2026-07-10",
      "start_time": "09:00:00",
      "end_time": "15:30:00",
      "age_min": 7,
      "age_max": 12,
      "grade_min": 2,
      "grade_max": 6,
      "price": 450.00
    }
  ]
}
```

**Example B — two weeks, some unknowns:**

```json
{
  "name": "Sample Sports Camp",
  "city": "South Orange",
  "state": "NJ",
  "phone": "973-555-0100",
  "tags": [],
  "sessions": [
    {
      "name": null,
      "start_date": "2026-07-13",
      "end_date": "2026-07-17",
      "start_time": "08:30:00",
      "end_time": "14:00:00",
      "age_min": 6,
      "age_max": 10,
      "grade_min": null,
      "grade_max": null,
      "price": null
    },
    {
      "name": null,
      "start_date": "2026-07-20",
      "end_date": "2026-07-24",
      "start_time": "08:30:00",
      "end_time": "14:00:00",
      "age_min": 6,
      "age_max": 10,
      "grade_min": null,
      "grade_max": null,
      "price": null
    }
  ]
}
```

Now produce the JSON for the camp(s) described in **Source material**, obeying **ALLOWED TAGS** and all rules above.

If you are about to add any prose, instead output **raw JSON only**.

---

## How to use this doc

1. Copy from **“You are a careful data-entry assistant…”** through the final instruction paragraph (or the whole **Prompt for the model** section).
2. Replace the `<<<…>>>` placeholders with your tag list, optional week reference, and camp source text.
3. Run **Camps admin → Import camp → Preview** on the result before confirming.

## Tag list quick reference

Export from production/local: use an existing camp’s **Export** button and reuse its `tags` array as a vocabulary guide, or copy category/tag lines from the admin dashboard.
