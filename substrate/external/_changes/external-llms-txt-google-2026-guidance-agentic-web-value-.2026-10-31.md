---
name: change_external-llms-txt-google-2026-guidance-agentic-web-value-_2026-10-31
type: source-change
chunk: external-llms-txt-google-2026-guidance-agentic-web-value-
topic: llms.txt Google 2026 guidance agentic web value caveats
source: https://www.getpassionfruit.com/blog/should-i-create-an-llms.txt-file-google-s-2026-guidance-explained
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-llms-txt-google-2026-guidance-agentic-web-value- changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-llms-txt-google-2026-guidance-agentic-web-value- (before)
+++ external-llms-txt-google-2026-guidance-agentic-web-value- (after)
@@ -1,15 +1,35 @@
-## reference · llms.txt guidance
-* Do not create an llms.txt file if your only goal is Google Search visibility, including AI Overviews and AI Mode.
-* Create an llms.txt file if you run developer documentation, API references, or technical documentation, as it can improve agent readability.
-* Create an llms.txt file if Anthropic Claude or OpenAI agents are a meaningful referrer or use case for your site.
-* Create an llms.txt file if you are building for the agentic browser layer specifically, as it is part of Lighthouse 13.3's Agentic Browsing audit.
-* Create an llms.txt file if your site has fewer than 1,000 pages and you can maintain the file without burdening your CMS workflow.
-* Do not create an llms.txt file if your site has 10,000+ pages, as the maintenance cost is high.
-* Do not create an llms.txt file if your team is already stretched on higher-impact AI search work.
-* If you already have an llms.txt file, keep it if your site falls into any of the "create one" scenarios, otherwise delete or stop maintaining it.
-* To write a useful llms.txt file, treat it as an editorial document, prefer Markdown mirror pages, keep descriptions short and literal, and refresh the file when your content strategy shifts.
-* The llms.txt file should be placed at the root of the domain, use Markdown format, and contain 10 to 50 curated links.
-* Google Search does not use llms.txt for ranking or citation, but some AI platforms like Anthropic and OpenAI do use it for agent-to-agent and agent-readiness workflows.
-* Maintenance cost for llms.txt is low at small scale, but high at large scale.
-* Do not rely on llms.txt as a shortcut to AI visibility, as it is not a substitute for other AI search work like content structure, entity consistency, and third-party platform presence.
+## reference · llms.txt Google 2026 guidance agentic web value caveats
+
+- **Google Search Stance (May 2026)**: Google explicitly states `llms.txt` is **not needed** for AI Overviews, AI Mode, or generative AI Search features. It is grouped with content chunking and AI-specific rewriting as tactics that do not improve Google AI visibility.
+- **Lighthouse 13.3 Audit**: Chrome’s Lighthouse 13.3 (released early May 2026) includes an "Agentic Browsing" category that audits for `llms.txt`.
+    - A 404 response marks the audit as "Not Applicable."
+    - Server errors are flagged if the file cannot be retrieved.
+    - This audit targets browser-agent readiness (e.g., Chrome agent capabilities, Project Mariner), not Search ranking.
+- **Empirical Usage**:
+    - Google indexes 30,000–60,000 `llms.txt` files globally (per Wix Studio AI Search Lab, Oct 2025), implying crawling occurs even if not used for ranking.
+    - **Anthropic**: Explicitly recommends `llms.txt` in "Writing for Agents" guidance for documentation sites.
+    - **OpenAI**: Uses `llms.txt` for the Agents SDK and Agentic Commerce Protocol.
+    - **Perplexity**: Observed to surface `llms.txt` content independently of standard RAG.
+- **Decision Framework**:
+    - **Create if**:
+        - You run developer documentation, API references, or technical docs.
+        - Anthropic Claude or OpenAI agents are a meaningful referrer or use case.
+        - You are optimizing for the agentic browser layer (Lighthouse 13.3 compliance).
+        - Your site has <1,000 pages (low maintenance cost).
+    - **Skip if**:
+        - Your only goal is Google Search visibility (including AI Overviews/AI Mode).
+        - Your site has >10,000 pages (high maintenance cost outweighs agent-readiness upside).
+        - Your team is stretched; prioritize high-impact AI search work (entity-consistent content, third-party presence) over `llms.txt`.
+- **Best Practices for Writing `llms.txt`**:
+    - **Location**: Root of the domain (`yourdomain.com/llms.txt`).
+    - **Format**: Markdown.
+    - **Content**: Curate 10–50 key links; do not mirror the full sitemap. 20 curated links outperform 200 uncurated ones.
+    - **Links**: Prefer `.md` mirrors of canonical pages over HTML landing pages for faster agent parsing.
+    - **Descriptions**: Keep to one line; use exact terminology buyers/agents search for. Avoid marketing copy.
+    - **Maintenance**: Review quarterly to prevent stale data from damaging agent trust.
+- **Impact Comparison**:
+    - `llms.txt`: No impact on Google Search; indirect impact on ChatGPT/Perplexity; high impact on browser-agent readiness and Claude workflows.
+    - **Higher-ROI Levers**: Direct-answer content, structured data (schema.org), technical SEO health, and third-party platform presence (Reddit, YouTube, Wikipedia) drive citation across all AI surfaces simultaneously.
+- **Caveat**: Do not treat `llms.txt` as a substitute for core SEO/AEO work. It is a narrow lever for agent-readiness, not a universal visibility booster.
+
 Sources: https://www.getpassionfruit.com/blog/should-i-create-an-llms.txt-file-google-s-2026-guidance-explained
```

## Decision (2026-10-31)

No lever moves; llms.txt stays hygiene, not a citation lever (MAXIMIZATION_ROADMAP line 83): Google re-confirms it is not used for AI search. New: Lighthouse 13.3's Agentic Browsing audit flags a llms.txt that errors (a 404 is 'not applicable') - the site's llms.txt is served (local 200, read 2026-10-31), so the audit passes as it stands.
