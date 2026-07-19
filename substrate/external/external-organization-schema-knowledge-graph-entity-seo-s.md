---
name: external-organization-schema-knowledge-graph-entity-seo-s
type: reference
source: https://www.stackmatix.com/blog/organization-schema-knowledge-graph
source_sha: 92e675f43a2acad4
fetched_at: 2026-07-18T22:50:03Z
last_verified: 2026-07-19
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Organization schema knowledge graph entity SEO sameAs
---

## reference · Organization schema knowledge graph entity SEO sameAs  

- **Required Organization schema properties**  
  - `@type` – e.g., `Organization`, `Corporation`, `LocalBusiness`  
  - `name` – official legal name  
  - `url` – primary website URL  

- **Strongly recommended properties**  
  - `logo` – image URL (displayed in Knowledge Panel)  
  - `sameAs` – list of verified authoritative URLs (Wikipedia, Wikidata, official social media)  
  - `description` – concise business description  
  - `foundingDate` – ISO‑8601 date (e.g., `"2015-03-15"`)  
  - `founder` – person or entity that founded the organization  

- **Additional useful properties**  
  - `address` (PostalAddress)  
  - `contactPoint` (telephone, email, contactType, availableLanguage)  
  - `telephone` – primary phone number  
  - `email` – primary email address  
  - `numberOfEmployees` – company size indicator  
  - `areaServed` – geographic service area  
  - `parentOrganization` – corporate hierarchy  

- **JSON‑LD format is the recommended implementation**  
  - Place the `<script type="application/ld+json">` block in the `<head>` of each page.  
  - Include on the homepage (required), About page (recommended), and Contact page (if location‑specific).  

- **Advanced properties that strengthen entity recognition**  
  - `@id` – persistent URI (e.g., `"https://www.yourcompany.com/#organization"`) for cross‑referencing across schema blocks.  
  - `knowsAbout` – array of expertise topics (e.g., `["Digital Marketing","SEO","Structured Data"]`).  
  - `mainEntityOfPage` – links a page to its canonical URL, clarifying the page’s primary entity.  

- **SameAs best practices**  
  1. Include only verified, active profiles you control.  
  2. Prioritize authoritative sources: Wikipedia → Wikidata → official social media.  
  3. Keep profile information consistent across all linked URLs.  
  4. Remove dead links and add new authoritative profiles promptly.  

- **SameAs high‑value tiers**  
  - **Tier 1 (Highest Impact)**: Wikipedia page, Wikidata entry, official social media profiles.  
  - **Tier 2 (Strong Impact)**: LinkedIn company page, Crunchbase profile, Google Business Profile, industry‑specific directories.  
  - **Tier 3 (Supporting)**: Twitter/X, Facebook, YouTube channel, GitHub organization.  

- **Entity‑based SEO context**  
  - Google processes queries by mapping entities and their relationships; structured Organization schema declares your brand as a discrete, verifiable entity.  
  - Accurate schema increases chances of a Knowledge Panel and AI search citations.  

- **Rich‑snippet benefits**  
  - Stacking Organization with BlogPosting, FAQPage, etc., unlocks multiple SERP features (logo, FAQ dropdowns, sitelinks searchbox, breadcrumbs).  
  - Studies show 20‑30 % higher click‑through rates for pages with rich snippets versus plain listings.  
  - Presence of structured data correlates with featured‑snippet eligibility.  

- **Implementation workflow**  
  1. Verify all data (name, URLs, logo dimensions, contact info).  
  2. Generate JSON‑LD using the provided templates or a visual tool (e.g., Google Structured Data Markup Helper).
