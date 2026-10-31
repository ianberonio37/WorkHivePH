---
name: external-organization-schema-knowledge-graph-entity-seo-s
type: reference
source: https://www.stackmatix.com/blog/organization-schema-knowledge-graph
source_sha: 743344062687357c
fetched_at: 2026-10-30T16:58:36Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Organization schema knowledge graph entity SEO sameAs
---

## reference · Organization schema knowledge graph

- Use **JSON‑LD** for Organization markup; place the `<script type="application/ld+json">` in the `<head>` of the homepage (required) and optionally on About/Contact pages.  
- **Required properties**:  
  - `@type` = `"Organization"` (or `"Corporation"` / `"LocalBusiness"` as appropriate)  
  - `name` – exact legal or brand name  
  - `url` – canonical website URL (e.g., `https://www.example.com`)  
- **Strongly recommended properties** (add for Knowledge Graph impact):  
  - `logo` – full URL to a high‑resolution logo image (provide width/height if using `ImageObject`)  
  - `sameAs` – array of verified, authoritative profile URLs (see tier list)  
  - `description` – concise brand description (used in Knowledge Panel)  
  - `foundingDate` – ISO‑8601 date (`YYYY` or `YYYY-MM-DD`)  
  - `founder` – `@type":"Person"` object with `name` (creates entity relationships)  
- **Additional useful properties**: `address`, `contactPoint`, `telephone`, `email`, `numberOfEmployees`, `areaServed`, `parentOrganization`.  
- **@id**: assign a persistent URI for the organization, e.g. `"@id": "https://www.example.com/#organization"`. Use this ID in other schema blocks (`publisher`, `mainEntityOfPage`) to link entities without duplication.  
- **sameAs – high‑value targets**:  
  - **Tier 1** (must‑have): Wikipedia page, Wikidata entry, official social media profiles (LinkedIn, X/Twitter if verified).  
  - **Tier 2**: Crunchbase, Google Business Profile, industry directories.  
  - **Tier 3**: Facebook, YouTube, GitHub, other ancillary profiles.  
- **sameAs best practices**:  
  1. Include only URLs you control and that are active.  
  2. Prioritize Tier 1 sources; they carry the most weight for entity verification.  
  3. Keep profile information consistent with your site (name, logo, description).  
  4. Audit quarterly; remove dead links, add new authoritative profiles.  
- **knowsAbout**: list up to ~10 core topics the organization is expert in (e.g., `"knowsAbout": ["Digital Marketing","SEO","Structured Data"]`). Helps AI search assess expertise.  
- **mainEntityOfPage**: in content types (BlogPosting, Article, FAQPage) set `mainEntityOfPage` to the page’s canonical URL and reference the Organization via its `@id` in `publisher`. This clarifies which entity a page represents.  
- **Schema stacking**: combine Organization with other types (BlogPosting, Article, FAQPage) that reference the Organization’s `@id`. This creates a connected graph, improves trust signals, and unlocks multiple SERP features (logo in Knowledge Panel, FAQ rich results, sitelinks searchbox).  
- **Rich snippet impact**: pages with structured data see 20‑30 % higher CTR than plain results; inclusion of Organization markup is a prerequisite for Knowledge Panel and many rich results.  
- **Implementation tools**:  
  - Manual insertion of JSON‑LD in any CMS.  
  - WordPress plugins: **Rank Math** (full support for `@id`, `sameAs`, `knowsAbout`) or **Yoast SEO** (auto‑generates basic Organization schema).  
  - Google Structured Data Markup Helper – visual builder for initial JSON‑LD.  

**Sources:** https://www.stackmatix.com/blog/organization-schema-knowledge-graph
