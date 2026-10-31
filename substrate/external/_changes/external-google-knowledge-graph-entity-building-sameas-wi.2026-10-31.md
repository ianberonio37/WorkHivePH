---
name: change_external-google-knowledge-graph-entity-building-sameas-wi_2026-10-31
type: source-change
chunk: external-google-knowledge-graph-entity-building-sameas-wi
topic: Google Knowledge Graph entity building sameAs Wikidata
source: https://ahrefs.com/blog/google-knowledge-graph/
detected: 2026-10-31
age_days: 103
ttl_days: 30
---

# external-google-knowledge-graph-entity-building-sameas-wi changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-google-knowledge-graph-entity-building-sameas-wi (before)
+++ external-google-knowledge-graph-entity-building-sameas-wi (after)
@@ -1,18 +1,17 @@
 ## reference · Google Knowledge Graph entity building sameAs Wikidata
-- Google’s Knowledge Graph stores **≈1.6 trillion facts** about **≈54 billion entities**.  
-- In **June 2025** Google performed a major cleanup, **removing >3 billion entities** from the Knowledge Graph in a single week.  
-- **Zero‑click search rates** (searches ending without a click):  
-  - **≈60 %** of all Google searches (Sparktoro 2024).  
-  - **53 %** of searches for “what is SEO” result in no click.  
-  - Only **9 %** of searches for “Taylor Swift age” result in a click (91 % zero‑click).  
-- **AI Overviews** and **AI Mode** explicitly pull entity data from the Knowledge Graph; Google confirms AI Mode’s reliance on KG (Google AI Overview PDF).  
-- **Gemini** (Google Cloud) leverages the Knowledge Graph for entity recognition, relationship mapping, and intent understanding (Google Cloud Gemini docs).  
-- KG powers SERP features: **Knowledge Panels, Knowledge Cards, People Also Ask, AI Overviews, AI Mode responses**.  
-- KG enables Google to satisfy queries that lack exact keyword matches (e.g., “small green guy with lightsaber” → Star Wars character).  
-- To be included in the Knowledge Graph (and thus appear in Knowledge Panels/Cards):  
-  - Provide **consistent entity signals** across your website, structured data (e.g., schema.org), and **authoritative third‑party sources** (e.g., Wikidata, Wikipedia).  
-  - Maintain **high‑quality, verifiable information**; the KG favors reliable, well‑linked data.  
-- Inclusion in the Knowledge Graph **increases SERP real estate and perceived authority** but can **reduce organic click‑through** because users may get answers directly from KG‑driven features.  
-- **SEO strategy tip:** avoid or deprioritize targeting keywords with **high zero‑click rates** if organic traffic is a primary goal.  
-- The Knowledge Graph is a **structured, continuously updated** database; entities can be **pruned** or removed, so monitor for disappearance and refresh signals accordingly.  
+
+- Google’s Knowledge Graph stores **≈ 1.6 trillion facts** about **≈ 54 billion entities**.  
+- Zero‑click searches: **≈ 60 %** of Google queries end without a user click (Sparktoro, 2024).  
+- Keyword‑specific no‑click rates:  
+  - “what is seo” → **53 %** of searches receive no click.  
+  - “Taylor Swift age” → **9 %** of searches receive a click.  
+- In **June 2025** Google removed **> 3 billion entities** from the Knowledge Graph in a single week to improve data quality for AI features.  
+- To increase chances of being recognized as an entity:  
+  - Ensure **consistent, authoritative signals** across your website, structured data (e.g., schema.org `sameAs` linking to Wikidata), and third‑party sources.  
+  - Verify existing presence via the **Google Knowledge Graph API** before building new signals.  
+- Entities in the Knowledge Graph are used by:  
+  - **AI Overviews** – to ground answers in verified facts.  
+  - **AI Mode** – to surface hyperlinked entity panels.  
+  - **Gemini** – for entity recognition, relationship mapping, and intent understanding.  
+- Entities that lack clear signals risk being omitted from both traditional SERP features (Knowledge Panels, Featured Snippets) and AI‑generated answers.  
 
```

## Decision (2026-10-31)

No lever moves. Entity building (consistent sameAs to Wikidata, verify via the Knowledge Graph API first) is the open M2 entity-prep lever in MAXIMIZATION_ROADMAP, whose values (Organization/Person, Wikidata) are Ian's to supply; the re-fetch changes nothing about it. Its zero-click figure (~60%, 2024) is older than the ~68-69% the strategy uses.
