# Entity Layer Package — make WorkHive resolvable to AI engines

**Why this is #1:** *entity resolution runs BEFORE content retrieval; brands that fail entity resolution are excluded from citation eligibility* `[external-schema-sameas-entity-disambiguation-ai-citations]`. WorkHive's homepage Organization schema is rich, but its `sameAs` is currently **`[]` (empty)** — so no engine can confirm the entity, and 76.95% of cited URLs sit *outside* the organic top-10, meaning entity recognition outweighs ranking. This package makes WorkHive a resolvable entity.

**Owner split:** I've prepared every asset. The `[IAN]` steps create the live profiles (I cannot create accounts in your name, and *a broken `sameAs` is worse than none* — so I will only wire URLs that are live and correct).

---

## Step 1 — Create the profiles (priority order)

`sameAs` priority per the evidence: **Wikidata → Wikipedia → LinkedIn → Crunchbase → GitHub**. Do the un-gated ones first (LinkedIn/Crunchbase/GitHub have no notability gate); Wikidata/Wikipedia need references.

| # | Profile | `[IAN]` action | Resulting URL (send me these) |
|---|---|---|---|
| 1 | **LinkedIn company page** | Create at linkedin.com/company/setup — name "WorkHive", tagline "Free offline-first maintenance platform for Philippine plants", website workhiveph.com | `https://www.linkedin.com/company/<handle>/` |
| 2 | **Crunchbase** | Add organization at crunchbase.com/add-new — same name/description/website + DTI reg 8080496, founded 2026-04-06 | `https://www.crunchbase.com/organization/<handle>` |
| 3 | **GitHub org** | If WorkHive has/creates a GitHub org, confirm the handle | `https://github.com/<handle>` |
| 4 | **Facebook page** | If a WorkHive FB page exists (marketing runs on Meta), send the URL | `https://www.facebook.com/<handle>` |
| 5 | **Google Business Profile** | Optional for SaaS; only if you want local signals | GBP profile URL |
| 6 | **Wikidata item** | Create only once you have ≥2 serious public references (press, directory, DTI). Draft statements below. | `https://www.wikidata.org/wiki/Q<id>` |

**Consistency rule (non-negotiable):** the **name, canonical URL, and description must be byte-identical** across every profile `[external-schema-sameas-entity-disambiguation-ai-citations]`. Use exactly:
- **Name:** `WorkHive`
- **URL:** `https://workhiveph.com`
- **Description:** `Free, offline-first maintenance management platform for Philippine industrial plants — digital logbook, PM scheduler, inventory, skill matrix, engineering calculators, and an AI work assistant.`

---

## Step 2 — The `sameAs` JSON-LD (I wire this once you send the URLs)

Replaces the empty `"sameAs": []` on `index.html` line ~102 (inside `#organization`). I'll drop in only the URLs that are live:

```json
"sameAs": [
  "https://www.linkedin.com/company/<handle>/",
  "https://www.crunchbase.com/organization/<handle>",
  "https://github.com/<handle>",
  "https://www.facebook.com/<handle>",
  "https://www.wikidata.org/wiki/Q<id>"
]
```

I'll also add a **`founder` `sameAs`** (Person E-E-A-T) once you have a LinkedIn personal URL:
```json
"founder": {
  "@type": "Person",
  "name": "Ian Lumayno Beronio",
  "sameAs": ["https://www.linkedin.com/in/<handle>/"]
}
```

---

## Step 3 — Wikidata item statements (draft — create when notability is met)

Wikidata needs a valid Wikimedia sitelink **or** serious, publicly-available references `[external-wikidata-notability-criteria-create-item-company]`. Until WorkHive has press coverage, hold this; the statements are ready:

| Property | Value |
|---|---|
| Label (en) | WorkHive |
| Description (en) | free offline-first maintenance management platform for Philippine industrial plants |
| `P31` instance of | `Q7397` software **and** `Q4830453` business |
| `P571` inception | 2026-04-06 |
| `P17` country | `Q928` (Philippines) |
| `P856` official website | https://workhiveph.com |
| `P112` founded by | Ian Lumayno Beronio |
| `P452` industry | maintenance / industrial software |
| References | DTI Business Name Reg. No. 8080496; official website; any press/directory listing |

---

## Step 4 — Validate (I run these after wiring)

1. **Schema Markup Validator** (validator.schema.org) — confirm the Organization + `sameAs` parse with zero errors.
2. **Direct AI prompt tests at 30 / 60 / 90 days** `[external-schema-sameas-entity-disambiguation-ai-citations]`: ask ChatGPT/Perplexity/Gemini "What is WorkHive (workhiveph.com)?" and record whether they resolve the entity correctly. Track in the SOV harness (`prompt_audit_queries.json`).
3. Re-run the homepage through the platform's schema gates (they already pass; adding valid `sameAs` keeps them green).

**Definition of done:** ≥3 live `sameAs` URLs wired + validating, and at least one engine correctly resolves "WorkHive" as the PH maintenance platform in a direct prompt test.
