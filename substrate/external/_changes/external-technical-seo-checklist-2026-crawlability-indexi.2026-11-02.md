---
name: change_external-technical-seo-checklist-2026-crawlability-indexi_2026-11-02
type: source-change
chunk: external-technical-seo-checklist-2026-crawlability-indexi
topic: technical SEO checklist 2026 crawlability indexing
source: https://developers.google.com/search/docs/essentials/technical
detected: 2026-11-02
age_days: 106
ttl_days: 30
---

# external-technical-seo-checklist-2026-crawlability-indexi changed on re-fetch (2026-11-02)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-technical-seo-checklist-2026-crawlability-indexi (before)
+++ external-technical-seo-checklist-2026-crawlability-indexi (after)
@@ -1,29 +1,17 @@
-## reference · technical SEO checklist 2026 crawlability indexing
-* Technical SEO involves optimizing a website's infrastructure for search engines and AI systems to crawl, render, and index it.
-* Key pillars of technical SEO: crawlability, indexability, performance, rendering, security, architecture, and readability by AI.
-* HTTP status codes:
-  + 200 OK: page exists and content is available.
-  + 301: permanent redirect, transfers most authority to destination.
-  + 302: temporary redirect, may index original or destination URL.
-  + 404: page not found, may be intentional or accidental.
-  + 410: removal is likely intentional, URL will be removed from index.
-  + 503: temporary server issue, Googlebot will retry later.
-* Robots.txt:
-  + Manages access for bots, including search engine crawlers and AI bots.
-  + Does not handle indexing, use noindex directive instead.
-  + Should not block CSS or JavaScript files.
-  + Declare sitemap file to provide access to priority pages.
-  + Located in domain's root directory, named exactly "robots.txt", UTF-8 encoded, maximum size 500 KiB.
-* AI crawlers:
-  + Designed for training or search, collect data to train models or find sources for responses.
-  + Blocking access may prevent content theft but also reduces visibility.
-  + Not all bots follow robots.txt rules.
-* XML sitemaps:
-  + Essential for facilitating URL discovery, especially on large sites.
-  + Include only canonical URLs.
-* User-agents for AI crawlers:
-  + OpenAI: GPTBot (training), OAI-SearchBot (search/indexing), ChatGPT-User (real-time access).
-  + Perplexity: PerplexityBot (indexing), Perplexity-User (real-time access).
-  + Anthropic: ClaudeBot (training), Claude-SearchBot (search/indexing), Claude-User (real-time access).
-  + Google: Googlebot (search/AI), Google-Extended (training), GoogleOther (support tracking).
-Sources: https://www.debugbear.com/blog/technical-seo-checklist
+## reference · the technical SEO floor: crawlable, working, indexable
+
+The source this chunk was distilled from - DebugBear's "technical SEO checklist" (debugbear.com/blog/technical-seo-checklist)
+- refused every connection on 2026-11-02: curl's TLS handshake was refused, a real browser got
+ERR_CONNECTION_CLOSED, and WebFetch's socket was closed. Its lever ("crawlability and indexability remain the floor")
+now rests on Google's own statement of that floor.
+
+Google Search Central, "Google Search technical requirements" (read 2026-11-02; the page shows no updated date):
+* **Googlebot isn't blocked.** The page is publicly accessible and not blocked from crawling; pages behind a log-in are
+  not crawled.
+* **The page works.** It answers HTTP 200 (success); client and server error pages are not indexed.
+* **The page has indexable content.** A file type Google Search supports, within Google's spam policies.
+* Meeting them makes a page **eligible** for indexing; it does **not guarantee** indexing (and the page says nothing
+  about ranking).
+
+Held on WorkHive's deployed origin by: KA-S (a raw HTTP GET answers 200 and the canonical names the URL),
+sitemap-promise, and seo-technical.
```

## Decision (2026-11-02)

The lever stands, on a better anchor. SEO_AEO_GEO_MAXIMIZATION_ROADMAP.md ('crawlability + indexability remain the floor') cited DebugBear's checklist, which no instrument can reach today (TLS refused, browser connection closed, WebFetch socket closed). Google's own technical requirements say the same floor in three lines - not blocked, HTTP 200, indexable content - and that meeting them makes a page eligible, not indexed. Nothing WorkHive holds moves: KA-S already reads a raw 200 and the canonical on every sitemap URL. The roadmap line now names the Google source.
