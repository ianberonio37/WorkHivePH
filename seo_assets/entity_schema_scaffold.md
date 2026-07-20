# Entity schema scaffold (M2/M3) — fill the [PLACEHOLDER]s, then inject into index.html

**Why this is the #1 lever:** the 2026 harvest (`external-schema-markup-structured-data-strategies-after-m`, DigitalApplied) found **Organization + Person schema with `sameAs` is the single highest-leverage schema type** — AI Mode uses it for entity resolution + claim verification, independent of any rich result. Today `index.html` has a strong Organization node but **`sameAs: []` is empty** and there is **no standalone E-E-A-T Person node**. This scaffold closes both.

**Ian provides:** the profile URLs + a 1-2 line bio + the registered business address. Then I (or you) drop the JSON into the `@graph`.

---

## 1. Fill the Organization `sameAs` (replace `index.html` line ~103 `"sameAs": []`)

Order matters less than presence. High-value per the harvest: **G2 / Capterra** (software-review profiles = ~3× AI-citation probability), then owned social, then the business directories WorkHive is listed on.

```json
"sameAs": [
  "[PLACEHOLDER: LinkedIn company page URL]",
  "[PLACEHOLDER: Facebook page URL]",
  "[PLACEHOLDER: YouTube channel URL]",
  "[PLACEHOLDER: X/Twitter URL]",
  "[PLACEHOLDER: G2 product profile URL — claim it, high AI-citation value]",
  "[PLACEHOLDER: Capterra product profile URL — claim it]",
  "[PLACEHOLDER: Crunchbase URL]",
  "[PLACEHOLDER: Wikidata item URL once created — see layer_b_playbook_assets.md]"
]
```

## 2. Add a full Person (founder E-E-A-T) node to the `@graph`

Replace the minimal inline `founder` object (line ~58-61) with a reference, and add a standalone Person node. This gives AI engines an author/entity to attribute expertise to (E-E-A-T).

Change the Organization `founder` to a reference:
```json
"founder": { "@id": "https://workhiveph.com/#founder" },
```

Add this node inside `@graph` (after the Organization node):
```json
{
  "@type": "Person",
  "@id": "https://workhiveph.com/#founder",
  "name": "Ian Lumayno Beronio",
  "jobTitle": "[PLACEHOLDER: e.g. Founder & Maintenance Engineer]",
  "worksFor": { "@id": "https://workhiveph.com/#organization" },
  "description": "[PLACEHOLDER: 1-2 line bio — e.g. Philippine industrial maintenance engineer; founder of WorkHive.]",
  "knowsAbout": [
    "Industrial maintenance", "Reliability-centered maintenance",
    "Overall Equipment Effectiveness", "Preventive maintenance",
    "Philippine industrial standards"
  ],
  "alumniOf": "[PLACEHOLDER: school/PRC license if you want to claim it, else remove]",
  "sameAs": [
    "[PLACEHOLDER: your personal LinkedIn URL]",
    "[PLACEHOLDER: any personal author profile / GitHub]"
  ]
}
```

## 3. (Now unblocked) LocalBusiness node — the DTI registration already exists

The Organization already carries DTI Business Name Reg No. 8080496. LocalBusiness is the harvest's #2 schema lever ("critical for map-pack + local AI answers"). It only needs the **registered address**.

```json
{
  "@type": "LocalBusiness",
  "@id": "https://workhiveph.com/#localbusiness",
  "name": "WorkHive Engineering Services",
  "parentOrganization": { "@id": "https://workhiveph.com/#organization" },
  "url": "https://workhiveph.com",
  "email": "admin@workhiveph.com",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "[PLACEHOLDER: registered street address]",
    "addressLocality": "[PLACEHOLDER: city/municipality]",
    "addressRegion": "[PLACEHOLDER: province/region]",
    "postalCode": "[PLACEHOLDER: ZIP]",
    "addressCountry": "PH"
  },
  "areaServed": { "@type": "Country", "name": "Philippines" },
  "identifier": [
    { "@type": "PropertyValue", "name": "DTI Business Name Registration", "value": "8080496", "propertyID": "https://www.dti.gov.ph" }
  ]
}
```

---

**Injection checklist (when values are in):**
1. Replace `sameAs: []` with the filled array (section 1).
2. Swap the inline `founder` for the `@id` ref + add the Person node (section 2).
3. Add the LocalBusiness node (section 3) once the address is confirmed.
4. Run `python tools/seo_technical_gate.py` — confirm `jsonld_valid` stays 0 (valid).
5. Validate at validator.schema.org / Google Rich Results Test before committing.
6. Only aggregateRating remains (needs real reviews) — leave it out until then (no fabricated ratings — see the seo-content skill "no fabricated hard-percentage metric" lesson).
