---
name: change_external-ai-search-javascript-rendering-empirical-test_2026-10-31
type: source-change
chunk: external-ai-search-javascript-rendering-empirical-test
topic: AI search JavaScript rendering empirical test
source: https://www.gsqi.com/marketing-blog/ai-search-javascript-rendering/
detected: 2026-10-31
age_days: 103
ttl_days: 30
---

# external-ai-search-javascript-rendering-empirical-test changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-ai-search-javascript-rendering-empirical-test (before)
+++ external-ai-search-javascript-rendering-empirical-test (after)
@@ -1,8 +1,21 @@
 ## reference · AI search JavaScript rendering empirical test
-* Most AI platforms (e.g. ChatGPT, Perplexity, Claude) do not render JavaScript, causing visibility and ranking problems for sites relying on client-side rendering.
-* Google and Bing can render JavaScript fine and are not affected.
-* AI Search platforms may not display content, favicons, or snippets for sites with JavaScript rendering issues.
-* Site owners can test their site by turning off JavaScript, checking AI prompts, and verifying content rendering in ChatGPT, Perplexity, and Claude.
-* Solutions include using server-side rendering, reducing JavaScript reliance, or implementing changes to ensure AI search platforms can find content.
-* Testing and adjusting site content rendering is crucial as AI Search continues to grow.
+
+- **Core Finding**: Major AI search platforms (ChatGPT, Perplexity, Claude) do **not** render client-side JavaScript. Content delivered exclusively via JS is invisible to these crawlers, resulting in blank pages or "Access Denied" errors.
+- **Platform Exceptions**: Google (Search, AI Overviews, AI Mode) and Bing (Search with Copilot) **can** render JavaScript effectively. Their AI features leverage existing search infrastructure that supports JS rendering.
+- **Visibility Symptoms**:
+  - **Favicon Failure**: Sites relying on JS rendering often display generic/default favicons in ChatGPT and Perplexity, even if favicons render correctly in Google/Bing.
+  - **Citation Demotion**: Affected URLs are frequently excluded from primary "Citations" or "Selected" sections. Instead, they appear in secondary "More" (ChatGPT) or "Reviewed" (Perplexity) sections, often without content snippets.
+  - **Explicit Failure**: When prompted to read specific JS-rendered URLs, ChatGPT, Perplexity, and Claude explicitly state they cannot read the content or that the page returned no visible text.
+- **Control Group Validation**: The same AI platforms successfully retrieve and quote content from server-rendered or static HTML pages, confirming the issue is specific to JS rendering capabilities, not site-specific blocking.
+- **Diagnosis Method**:
+  1. Disable JavaScript in the browser; if key content disappears, the site is vulnerable.
+  2. Prompt AI platforms with specific URLs and ask for the first/last paragraphs. If the AI reports inability to read the page, JS rendering is the cause.
+  3. Check citation placement; demotion to "More" or "Reviewed" sections is a strong indicator of rendering failure.
+- **Remediation Strategies**:
+  - **Server-Side Rendering (SSR)**: Migrate from client-side to server-side rendering to ensure HTML is fully populated before delivery.
+  - **Reduce JS Dependency**: Audit content delivery to minimize reliance on JavaScript for core content visibility.
+  - **Testing Protocol**: Regularly test top-performing URLs against AI search prompts to monitor visibility and citation treatment.
+- **Tooling Gap**: As of the source date, there is no "AI Search Console" equivalent to Google Search Console for inspecting how AI platforms render specific URLs. Site owners must rely on manual prompt testing.
+- **Timeline Note**: An update dated October 19, 2026, confirms that ChatGPT and Claude still cannot render JS-based content, indicating this limitation persists over time.
+
 Sources: https://www.gsqi.com/marketing-blog/ai-search-javascript-rendering/
```

## Decision (2026-10-31)

No lever moves. The Oct 19, 2026 update the re-fetch picked up confirms ChatGPT and Claude still cannot render JS-only content - the reason the public pages keep their content in static HTML (MAXIMIZATION_ROADMAP). The rule stands.
