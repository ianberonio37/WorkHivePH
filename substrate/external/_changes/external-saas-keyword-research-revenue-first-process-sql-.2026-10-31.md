---
name: change_external-saas-keyword-research-revenue-first-process-sql-_2026-10-31
type: source-change
chunk: external-saas-keyword-research-revenue-first-process-sql-
topic: SaaS keyword research revenue-first process SQL 2026
source: https://kingmakersearch.com/blog/saas-keyword-research
detected: 2026-10-31
age_days: 88
ttl_days: 30
---

# external-saas-keyword-research-revenue-first-process-sql- changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-saas-keyword-research-revenue-first-process-sql- (before)
+++ external-saas-keyword-research-revenue-first-process-sql- (after)
@@ -1,16 +1,32 @@
-## reference · SaaS keyword research revenue-first process
-* Focus on 6 BOFU keyword types: competitor alternatives, product comparisons, best-for-use-case, best-for-industry, best-for-customer-type, and problem-solution queries.
-* These 6 keyword categories are: 
-  + Competitor alternatives (e.g., "Salesforce alternatives")
-  + Product vs. product (e.g., "HubSpot vs Pipedrive")
-  + Best tool for use case (e.g., "best CRM for real estate agents")
-  + Best tool for industry (e.g., "best accounting software for contractors")
-  + Best tool for customer type (e.g., "best project management for small teams")
-  + How to solve [problem] (e.g., "how to track sales pipeline")
-* Use a BOFU-first keyword research method to find, prioritize, and dominate keywords that drive demos and signups.
-* Utilize a Claude Prompt to create a revenue-driven keyword strategy by dropping your website URL and extracting necessary information.
-* Generate 75-150 unique keywords that each target a distinct SERP, avoiding duplicates and synonyms.
-* Prioritize keywords using a Priority Score column: (Volume × CPC) / KD, and sort descending.
-* Start with the top 10 keywords and create listicles for each on your own site, then do outreach to get mentioned in competing listicles already ranking for those terms.
-* Aim for co-occurrence across the web to build a reliable consensus that AI draws on when making recommendations.
+## reference · SaaS keyword research revenue-first process SQL 2026
+
+- **Target only BOFU/MOFU keywords**: focus on competitor alternatives, product comparisons, best‑for‑use‑case, best‑for‑industry, best‑for‑customer‑type, and problem‑solution queries.  
+- **Ignore TOFU “what is” or “benefits” queries**: AI overviews answer these instantly; they generate impressions but no pipeline.  
+- **Generate 75‑150 unique keywords**: each must target a distinct SERP; avoid synonyms that hit the same listicle or comparison article.  
+- **Use AI prompt workflow**:  
+  1. Drop your website URL to let Claude analyze site, competitors, customers, niche.  
+  2. Claude returns 75‑150 keywords covering all six BOFU categories.  
+  3. Upload list to Ahrefs to get volume, KD, CPC.  
+- **Competitor research steps**:  
+  - Search “[brand]”, “[brand] alternatives”, “[brand] competitors”, “[brand] vs”.  
+  - Extract direct competitors (alternatives/competitors listicles), indirect competitors (adjacent tools), and market leaders.  
+  - Compile a comprehensive competitor list for keyword generation.  
+- **Keyword templates**:  
+  - Competitor alternatives: “[Competitor] alternatives”  
+  - Product vs. product: “[Your product] vs [Competitor]”, “[Competitor A] vs [Competitor B]”  
+  - Best tool for use case: “best [category] for [use case]”  
+  - Best tool for industry: “best [category] for [industry]”  
+  - Best tool for customer type: “best [category] for [customer type]”, “best [category] for [company size]”, “best [category] for [role]”  
+  - Problem‑solution: “how to [solve problem]”, “how to [achieve outcome]”  
+- **Deduplication rule**: if two keywords would surface the same listicle/comparison, keep only the simpler, higher‑volume version.  
+- **Output format**:  
+  1. Full analysis table (Keyword | Category | Intent | Priority Notes).  
+  2. Ahrefs‑ready single‑column list for bulk import.  
+- **Prioritization**:  
+  1. Import Ahrefs list, export volume, KD, CPC.  
+  2. Add Priority Score = (Volume × CPC) ÷ KD.  
+  3. Sort descending; start with top 10.  
+  4. Create listicles for each; pursue outreach to existing ranking listicles to build co‑occurrence.  
+- **Proof of concept**: TxtCart shifted from “how to send video via text” to “Cartloop alternatives”, “OneText alternatives”, etc., achieving AI‑overview placement and landing a $500M+ client (HexClad).  
+
 Sources: https://kingmakersearch.com/blog/saas-keyword-research
```

## Decision (2026-10-31)

No lever moves. Its revenue-first rule (target comparison, alternative and best-for queries; skip 'what is' queries that AI Overviews answer) is how the query taxonomy in STRATEGY_V2 section 2.2 and the comparison pages already lean; the prompt-and-Ahrefs workflow is a method, not a claim the strategy quotes.
