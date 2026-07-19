---
name: external-technical-seo-checklist-2026-crawlability-indexi
type: reference
source: https://www.debugbear.com/blog/technical-seo-checklist
source_sha: 8978a6b4d850dcf7
fetched_at: 2026-07-18T22:41:37Z
last_verified: 2026-07-19
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: technical SEO checklist 2026 crawlability indexing
---

## reference · technical SEO checklist 2026 crawlability indexing
* Technical SEO involves optimizing a website's infrastructure for search engines and AI systems to crawl, render, and index it.
* Key pillars of technical SEO: crawlability, indexability, performance, rendering, security, architecture, and readability by AI.
* HTTP status codes:
  + 200 OK: page exists and content is available.
  + 301: permanent redirect, transfers most authority to destination.
  + 302: temporary redirect, may index original or destination URL.
  + 404: page not found, may be intentional or accidental.
  + 410: removal is likely intentional, URL will be removed from index.
  + 503: temporary server issue, Googlebot will retry later.
* Robots.txt:
  + Manages access for bots, including search engine crawlers and AI bots.
  + Does not handle indexing, use noindex directive instead.
  + Should not block CSS or JavaScript files.
  + Declare sitemap file to provide access to priority pages.
  + Located in domain's root directory, named exactly "robots.txt", UTF-8 encoded, maximum size 500 KiB.
* AI crawlers:
  + Designed for training or search, collect data to train models or find sources for responses.
  + Blocking access may prevent content theft but also reduces visibility.
  + Not all bots follow robots.txt rules.
* XML sitemaps:
  + Essential for facilitating URL discovery, especially on large sites.
  + Include only canonical URLs.
* User-agents for AI crawlers:
  + OpenAI: GPTBot (training), OAI-SearchBot (search/indexing), ChatGPT-User (real-time access).
  + Perplexity: PerplexityBot (indexing), Perplexity-User (real-time access).
  + Anthropic: ClaudeBot (training), Claude-SearchBot (search/indexing), Claude-User (real-time access).
  + Google: Googlebot (search/AI), Google-Extended (training), GoogleOther (support tracking).
Sources: https://www.debugbear.com/blog/technical-seo-checklist
