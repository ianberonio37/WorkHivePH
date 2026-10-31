---
name: change_external-schema-sameas-entity-disambiguation-ai-citations_2026-10-31
type: source-change
chunk: external-schema-sameas-entity-disambiguation-ai-citations
topic: schema sameAs entity disambiguation AI citations Person Organization 2026
source: https://organikpi.com/blog/technical-seo/schema-sameas-entity-disambiguation-ai-citations/
detected: 2026-10-31
age_days: 88
ttl_days: 30
---

# external-schema-sameas-entity-disambiguation-ai-citations changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-schema-sameas-entity-disambiguation-ai-citations (before)
+++ external-schema-sameas-entity-disambiguation-ai-citations (after)
@@ -1,18 +1,31 @@
-## reference · schema sameAs entity disambiguation AI citations
-* The schema.org `sameAs` property is used to link a website entity to authoritative external profiles, confirming identity and enabling AI engines to cite the brand.
-* `sameAs` is used on over 10 million domains, according to Google's May 2026 web index.
-* Entity resolution runs before content retrieval, and brands that fail entity resolution are excluded from citation eligibility.
-* 76.95% of cited URLs in a May 2026 study were outside the organic top-10, indicating that entity recognition outweighs ranking.
-* Priority order for Organization `sameAs` targets: Wikidata, Wikipedia, LinkedIn, Crunchbase, GitHub.
-* Three properties must be identical across all profiles: name, canonical URL, and description.
-* A broken `sameAs` link is worse than no link.
-* Validate `sameAs` implementation with Schema Markup Validator and run direct AI prompt tests at 30-60-90 days post-deployment.
-* `sameAs` applies to Person entities as well as Organization entities, and is used for author disambiguation.
-* For Person entities, priority order for `sameAs` targets: LinkedIn, ORCID, Wikidata, Twitter/X.
-* Entity resolution for authors is not separate from entity resolution for brands, and both layers must be present and cross-referencing each other.
-* Common mistakes that break entity recognition include: dead or redirected `sameAs` URLs, mismatched name strings, HTTP instead of HTTPS, `sameAs` only on the homepage, founder's LinkedIn in the Organization block, and unclaimed profiles.
-* `sameAs` is one layer of a stacked entity signal architecture, and must be used in conjunction with other schema markup and entity optimization techniques.
-* Validate `sameAs` implementation using Schema Markup Validator, Google Rich Results Test, Wikidata Query Service, and direct AI prompt testing.
-* Run `sameAs` URL audit quarterly to ensure all URLs return HTTP 200 with no redirect chain.
-* Set a 30-60-90 day verification cadence after deployment to confirm schema parses cleanly, external profiles resolve, and attribution accuracy.
+## reference · Schema sameAs entity disambiguation
+
+- **Core Function**: `sameAs` is a schema.org property (applies to `Thing`, `Organization`, `Person`) that links a website entity to authoritative external profiles, enabling AI engines to confirm identity before content retrieval.
+- **Pre-Retrieval Gate**: Entity resolution occurs before passage scoring. Brands failing disambiguation are excluded from AI citation pools regardless of organic search rank.
+- **Citation Data (May 2026 Study)**: In a study of 153,425 AI citations, 76.95% of cited URLs were outside the organic top-10, confirming entity recognition outweighs traditional ranking for AI visibility.
+- **Priority Targets for `Organization`**:
+    1. **Wikidata**: Highest weight; direct feed to Google Knowledge Graph. Use Q-number as identifier.
+    2. **Wikipedia**: Very high weight; cited 1,483 times in the 2026 study.
+    3. **LinkedIn**: High weight; cited 2,267 times across 988 queries in the 2026 study.
+    4. **Crunchbase**: High weight; structured business data source.
+    5. **GitHub**: Medium weight; critical for SaaS/technical brands.
+- **Mandatory Consistency**: Three properties must be identical across the website schema and all `sameAs` targets to prevent merge failure:
+    1. Name (exact string match, e.g., "Inc." vs "Inc").
+    2. Canonical URL (HTTPS only; no trailing slash mismatches).
+    3. Description (exact match, particularly with Wikidata).
+- **Person Entity Rules**: Use `Person` schema for authors with `sameAs` links to LinkedIn, ORCID, Wikidata, and X/Twitter. Link `Person` to `Organization` via `worksFor` and `Organization` to `Person` via `founder` to create a connected entity graph.
+- **Common Failures**:
+    - **Broken Links**: A dead or redirected `sameAs` URL is worse than no link; it signals an unresolvable entity.
+    - **Name Mismatch**: Variations like "Acme Corp" vs "ACME" create separate entity nodes.
+    - **Protocol Errors**: Use HTTPS exclusively; HTTP breaks entity matching in some parsers.
+    - **Placement**: `sameAs` must be present on every page emitting `Organization` or `Person` references (e.g., author bylines), not just the homepage.
+    - **Profile Type**: Do not place founder personal LinkedIn profiles in the `Organization` `sameAs` array; use a separate `Person` block.
+- **Multi-Brand Structure**: Create one `Organization` entity per legal brand with its own `sameAs` cluster. Connect brands via `parentOrganization` or `subOrganization` to prevent cross-brand citation confusion.
+- **Validation Protocol**:
+    1. **Structural**: Use Schema Markup Validator and Google Rich Results Test to ensure JSON-LD validity and URL resolution (HTTP 200, no redirects).
+    2. **Behavioral**: Run direct AI prompt tests (ChatGPT, Perplexity, Claude, Gemini) to verify attribution accuracy.
+    3. **Cadence**: Verify at 30 days (schema parse/URL resolution), 60 days (AI attribution logs), and 90 days (citation rate comparison).
+    4. **Threshold**: If citation lift is <15% on at least two platforms at 90 days, audit `sameAs` target authority and name consistency.
+- **Local SEO**: Include Google Business Profile as a `sameAs` target for local businesses to converge AI Search and Maps entity recognition.
+
 Sources: https://organikpi.com/blog/technical-seo/schema-sameas-entity-disambiguation-ai-citations/
```

## Decision (2026-10-31)

No lever moves, one Ian input strengthened. The study it adds (153,425 AI citations, May 2026: 76.95% of cited URLs outside the organic top 10) agrees with the V3 section 5 change made today. Its claim that entity resolution gates citation before passage scoring makes the homepage Organization's empty sameAs (Wikidata, LinkedIn, Crunchbase profiles) the strongest-evidenced Ian-gated input in MAXIMIZATION_ROADMAP line 163; the URLs are his to supply.
