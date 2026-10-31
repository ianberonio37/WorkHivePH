---
name: change_external-comparison-vs-page-patterns-aeo-feature-matrix-p_2026-10-31
type: source-change
chunk: external-comparison-vs-page-patterns-aeo-feature-matrix-p
topic: comparison vs-page patterns AEO feature matrix pros cons best-for citation
source: https://citevera.com/blog/comparison-pages-aeo-vs-page-patterns
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-comparison-vs-page-patterns-aeo-feature-matrix-p changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-comparison-vs-page-patterns-aeo-feature-matrix-p (before)
+++ external-comparison-vs-page-patterns-aeo-feature-matrix-p (after)
@@ -1,16 +1,18 @@
-## reference · comparison pages AEO
-* Comparison pages cite at roughly 2.4x the rate of generic blog posts on the same topics.
-* A cited vs-page opens with a direct comparison verdict in the first 100 words.
-* Include a side-by-side feature table with structured markup for machine-extractable data.
-* Write an independent verdict, not marketing puff, to increase citation rates.
-* Provide concrete pricing with effective dates to avoid stale pricing and down-ranking.
-* Include migration paths and switching costs to answer implicit follow-up questions.
-* Use schema beyond the basics, such as Product, AggregateRating, and FAQPage schema.
-* Avoid "best of" lists with weak comparisons, hidden conclusions, and marketing-tone copy.
-* Update vs-pages quarterly for pricing and feature accuracy, and annually for full structural review.
-* Build both vs-pages (head-to-head) and alternative pages (one product, many competitors) for different queries.
-* Use FAQPage and Product schema markup to make the biggest difference on vs-pages.
-* Limit vs-pages to 2-3 head-to-head comparisons per page, rather than listing many competitors.
-* Replace adjectives with concrete factual claims, such as "supports 12 integrations" instead of "powerful".
-* A vs-page should have a clear verdict, a comparison table, and schema markup to increase citation rates.
+## reference · comparison vs-page patterns
+
+- **Verdict first**: Open with a 2‑3 sentence verdict naming both products, the recommended choice for specific audiences, and the criteria driving the decision.  
+- **Side‑by‑side table**: Include a clean HTML table (or Dataset schema) with consistent rows for criteria such as Pricing, Free Tier, Free Trial, Best For, Integrations, Customer Support, Mobile Apps, Reporting Depth.  
+- **Independent verdict**: Avoid marketing puff; state where each product wins on specific criteria.  
+- **Current pricing**: List pricing with an “as of” date or link to the canonical pricing page; review quarterly.  
+- **Migration paths**: Add sections on how to migrate from X to Y (and vice‑versa) to address switching costs.  
+- **Rich schema**: Use BlogPosting (required), Product (one per tool), FAQPage (buyer questions), and AggregateRating if valid data exists.  
+- **Avoid**:  
+  - “Best of” lists with weak comparisons (directory style).  
+  - Hidden conclusions buried after long descriptions.  
+  - Comparing a product to a non‑product (e.g., spreadsheets).  
+  - Marketing‑tone adjectives; replace with concrete facts.  
+- **Content volume**: One vs‑page per top competitor pair; 5‑8 pages for a 10‑competitor category, plus 2‑3 plural alternative pages.  
+- **Update cadence**: Quarterly for pricing/feature accuracy; annually for full structural review.  
+- **Citation impact**: Well‑structured vs‑pages can raise overall citation rate by ~2.4× compared to generic blog posts.  
+
 Sources: https://citevera.com/blog/comparison-pages-aeo-vs-page-patterns
```

## Decision (2026-10-31)

No lever moves. The pattern it re-states (verdict first, a side-by-side table, prices with an 'as of' date, migration paths, FAQPage) is the one the live comparison pages already follow - the UpKeep page dates its price 'as of 27 October 2026'.
