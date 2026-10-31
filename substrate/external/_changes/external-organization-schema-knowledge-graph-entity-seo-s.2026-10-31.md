---
name: change_external-organization-schema-knowledge-graph-entity-seo-s_2026-10-31
type: source-change
chunk: external-organization-schema-knowledge-graph-entity-seo-s
topic: Organization schema knowledge graph entity SEO sameAs
source: https://www.stackmatix.com/blog/organization-schema-knowledge-graph
detected: 2026-10-31
age_days: 103
ttl_days: 30
---

# external-organization-schema-knowledge-graph-entity-seo-s changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-organization-schema-knowledge-graph-entity-seo-s (before)
+++ external-organization-schema-knowledge-graph-entity-seo-s (after)
@@ -1,55 +1,34 @@
-## reference · Organization schema knowledge graph entity SEO sameAs  
+## reference · Organization schema knowledge graph
 
-- **Required Organization schema properties**  
-  - `@type` – e.g., `Organization`, `Corporation`, `LocalBusiness`  
-  - `name` – official legal name  
-  - `url` – primary website URL  
+- Use **JSON‑LD** for Organization markup; place the `<script type="application/ld+json">` in the `<head>` of the homepage (required) and optionally on About/Contact pages.  
+- **Required properties**:  
+  - `@type` = `"Organization"` (or `"Corporation"` / `"LocalBusiness"` as appropriate)  
+  - `name` – exact legal or brand name  
+  - `url` – canonical website URL (e.g., `https://www.example.com`)  
+- **Strongly recommended properties** (add for Knowledge Graph impact):  
+  - `logo` – full URL to a high‑resolution logo image (provide width/height if using `ImageObject`)  
+  - `sameAs` – array of verified, authoritative profile URLs (see tier list)  
+  - `description` – concise brand description (used in Knowledge Panel)  
+  - `foundingDate` – ISO‑8601 date (`YYYY` or `YYYY-MM-DD`)  
+  - `founder` – `@type":"Person"` object with `name` (creates entity relationships)  
+- **Additional useful properties**: `address`, `contactPoint`, `telephone`, `email`, `numberOfEmployees`, `areaServed`, `parentOrganization`.  
+- **@id**: assign a persistent URI for the organization, e.g. `"@id": "https://www.example.com/#organization"`. Use this ID in other schema blocks (`publisher`, `mainEntityOfPage`) to link entities without duplication.  
+- **sameAs – high‑value targets**:  
+  - **Tier 1** (must‑have): Wikipedia page, Wikidata entry, official social media profiles (LinkedIn, X/Twitter if verified).  
+  - **Tier 2**: Crunchbase, Google Business Profile, industry directories.  
+  - **Tier 3**: Facebook, YouTube, GitHub, other ancillary profiles.  
+- **sameAs best practices**:  
+  1. Include only URLs you control and that are active.  
+  2. Prioritize Tier 1 sources; they carry the most weight for entity verification.  
+  3. Keep profile information consistent with your site (name, logo, description).  
+  4. Audit quarterly; remove dead links, add new authoritative profiles.  
+- **knowsAbout**: list up to ~10 core topics the organization is expert in (e.g., `"knowsAbout": ["Digital Marketing","SEO","Structured Data"]`). Helps AI search assess expertise.  
+- **mainEntityOfPage**: in content types (BlogPosting, Article, FAQPage) set `mainEntityOfPage` to the page’s canonical URL and reference the Organization via its `@id` in `publisher`. This clarifies which entity a page represents.  
+- **Schema stacking**: combine Organization with other types (BlogPosting, Article, FAQPage) that reference the Organization’s `@id`. This creates a connected graph, improves trust signals, and unlocks multiple SERP features (logo in Knowledge Panel, FAQ rich results, sitelinks searchbox).  
+- **Rich snippet impact**: pages with structured data see 20‑30 % higher CTR than plain results; inclusion of Organization markup is a prerequisite for Knowledge Panel and many rich results.  
+- **Implementation tools**:  
+  - Manual insertion of JSON‑LD in any CMS.  
+  - WordPress plugins: **Rank Math** (full support for `@id`, `sameAs`, `knowsAbout`) or **Yoast SEO** (auto‑generates basic Organization schema).  
+  - Google Structured Data Markup Helper – visual builder for initial JSON‑LD.  
 
-- **Strongly recommended properties**  
-  - `logo` – image URL (displayed in Knowledge Panel)  
-  - `sameAs` – list of verified authoritative URLs (Wikipedia, Wikidata, official social media)  
-  - `description` – concise business description  
-  - `foundingDate` – ISO‑8601 date (e.g., `"2015-03-15"`)  
-  - `founder` – person or entity that founded the organization  
-
-- **Additional useful properties**  
-  - `address` (PostalAddress)  
-  - `contactPoint` (telephone, email, contactType, availableLanguage)  
-  - `telephone` – primary phone number  
-  - `email` – primary email address  
-  - `numberOfEmployees` – company size indicator  
-  - `areaServed` – geographic service area  
-  - `parentOrganization` – corporate hierarchy  
-
-- **JSON‑LD format is the recommended implementation**  
-  - Place the `<script type="application/ld+json">` block in the `<head>` of each page.  
-  - Include on the homepage (required), About page (recommended), and Contact page (if location‑specific).  
-
-- **Advanced properties that strengthen entity recognition**  
-  - `@id` – persistent URI (e.g., `"https://www.yourcompany.com/#organization"`) for cross‑referencing across schema blocks.  
-  - `knowsAbout` – array of expertise topics (e.g., `["Digital Marketing","SEO","Structured Data"]`).  
-  - `mainEntityOfPage` – links a page to its canonical URL, clarifying the page’s primary entity.  
-
-- **SameAs best practices**  
-  1. Include only verified, active profiles you control.  
-  2. Prioritize authoritative sources: Wikipedia → Wikidata → official social media.  
-  3. Keep profile information consistent across all linked URLs.  
-  4. Remove dead links and add new authoritative profiles promptly.  
-
-- **SameAs high‑value tiers**  
-  - **Tier 1 (Highest Impact)**: Wikipedia page, Wikidata entry, official social media profiles.  
-  - **Tier 2 (Strong Impact)**: LinkedIn company page, Crunchbase profile, Google Business Profile, industry‑specific directories.  
-  - **Tier 3 (Supporting)**: Twitter/X, Facebook, YouTube channel, GitHub organization.  
-
-- **Entity‑based SEO context**  
-  - Google processes queries by mapping entities and their relationships; structured Organization schema declares your brand as a discrete, verifiable entity.  
-  - Accurate schema increases chances of a Knowledge Panel and AI search citations.  
-
-- **Rich‑snippet benefits**  
-  - Stacking Organization with BlogPosting, FAQPage, etc., unlocks multiple SERP features (logo, FAQ dropdowns, sitelinks searchbox, breadcrumbs).  
-  - Studies show 20‑30 % higher click‑through rates for pages with rich snippets versus plain listings.  
-  - Presence of structured data correlates with featured‑snippet eligibility.  
-
-- **Implementation workflow**  
-  1. Verify all data (name, URLs, logo dimensions, contact info).  
-  2. Generate JSON‑LD using the provided templates or a visual tool (e.g., Google Structured Data Markup Helper).
+**Sources:** https://www.stackmatix.com/blog/organization-schema-knowledge-graph
```

## Decision (2026-10-31)

No lever moves. The homepage Organization JSON-LD carries the required name and url and the recommended logo (ImageObject); sameAs is empty, which is the open M2 entity-prep item already named Ian-gated in MAXIMIZATION_ROADMAP (his verified profile URLs) - the source restates why it matters, not a new lever.
