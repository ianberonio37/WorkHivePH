---
name: change_external-robots-txt-for-ai-bots-blocking-cost-citation-lo_2026-10-31
type: source-change
chunk: external-robots-txt-for-ai-bots-blocking-cost-citation-lo
topic: robots.txt for AI bots blocking cost citation loss per engine 2026
source: https://capston.ai/robots-txt-for-ai-bots/
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-robots-txt-for-ai-bots-blocking-cost-citation-lo changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-robots-txt-for-ai-bots-blocking-cost-citation-lo (before)
+++ external-robots-txt-for-ai-bots-blocking-cost-citation-lo (after)
@@ -1,37 +1,133 @@
 ## reference · robots.txt for AI bots
-* A robots.txt file for AI bots tells AI crawlers which parts of a site they may access, controlling whether content can be read and used by AI engines.
-* Blocking a bot in robots.txt can cost 18-34% of potential AI citations on that engine.
-* Sites that unblock GPTBot, PerplexityBot, and ClaudeBot can see +186% AI-attributed traffic in 90 days.
-* Allow the following search/citation bots in robots.txt:
-	+ OAI-SearchBot
-	+ ChatGPT-User
-	+ PerplexityBot
-	+ Perplexity-User
-	+ ClaudeBot
-	+ Claude-SearchBot
-	+ Google-Extended
-	+ Applebot-Extended
-* Keep sensitive paths blocked for all bots:
-	+ /wp-admin/
-	+ /wp-login.php
-	+ /checkout/
-	+ /account/
-	+ /cart/
-	+ /search?
-	+ /*?utm_
-* Add a sitemap reference to robots.txt:
-	+ Sitemap: https://yourdomain.com/sitemap.xml
-* Validate robots.txt with each engine's documented user-agent.
-* Re-check robots.txt after every CMS upgrade.
-* Common technical errors include:
-	+ Disallowing a bot under a wrong user-agent
-	+ Blocking only the training bot but forgetting the search bot
-	+ Leaving Cloudflare's "Block AI Bots" toggle on
-	+ Blocking /sitemap.xml or sitemap path
-	+ Using noindex meta on pages that should be AI-cited
-* Trade-offs of blocking AI bots:
-	+ Blocking protects content from AI training and answers, but removes the chance of being cited by AI engines.
-* Difference between robots.txt and llms.txt:
-	+ robots.txt controls which crawlers may access a site
-	+ llms.txt is a curated map that guides AI models to important content
-Sources: https://capston.ai/robots-txt-for-ai-bots/
+
+- **Audit existing robots.txt**  
+  - Open `https://yourdomain.com/robots.txt`.  
+  - Search for AI bot names: `GPTBot`, `PerplexityBot`, `ClaudeBot`, `Google-Extended`, `OAI-SearchBot`, `ChatGPT-User`, `Perplexity-User`, `Claude-SearchBot`, `Claude-User`, `Applebot-Extended`.  
+  - Any `Disallow: /` under these agents blocks that bot.
+
+- **Two bot families per engine**  
+  - *Training crawler* (e.g., `GPTBot`, `Google-Extended`, `ClaudeBot`) feeds model knowledge.  
+  - *Search/RAG crawler* (e.g., `OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`, `Claude-SearchBot`) fetches pages at query time for citations.
+
+- **Allow search/citation bots (recommended for all sites)**  
+  ```txt
+  User-agent: OAI-SearchBot
+  Allow: /
+
+  User-agent: ChatGPT-User
+  Allow: /
+
+  User-agent: PerplexityBot
+  Allow: /
+
+  User-agent: Perplexity-User
+  Allow: /
+
+  User-agent: ClaudeBot
+  Allow: /
+
+  User-agent: Claude-SearchBot
+  Allow: /
+
+  User-agent: Claude-User
+  Allow: /
+
+  User-agent: Google-Extended
+  Allow: /
+
+  User-agent: Applebot-Extended
+  Allow: /
+  ```
+
+- **Training‑bot policy**  
+  - *Allow* if you want long‑term brand presence in models (default for marketing sites).  
+  - *Disallow* only for proprietary content you refuse to be memorized.  
+  - Example block for disallowing training bots on a SaaS UI:  
+    ```txt
+    User-agent: GPTBot
+    Disallow: /
+
+    User-agent: Google-Extended
+    Disallow: /
+
+    User-agent: anthropic-ai
+    Disallow: /
+
+    User-agent: CCBot
+    Disallow: /
+
+    User-agent: Bytespider
+    Disallow: /
+    ```
+
+- **Keep sensitive paths blocked for ALL bots**  
+  ```txt
+  User-agent: *
+  Disallow: /wp-admin/
+  Disallow: /wp-login.php
+  Disallow: /checkout/
+  Disallow: /account/
+  Disallow: /cart/
+  Disallow: /search?
+  Disallow: /*?utm_
+  Disallow: /*?fbclid
+  ```
+
+- **Sitemap references**  
+  ```txt
+  Sitemap: https://yourdomain.com/sitemap.xml
+  Sitemap: https://yourdomain.com/sitemap-news.xml
+  ```
+
+- **Production‑ready 2026 template**  
+  ```txt
+  # CapstonAI 2026 reference robots.txt
+  # Allow AI search/citation bots
+  User-agent: OAI-SearchBot
+  User-agent: ChatGPT-User
+  User-agent: PerplexityBot
+  User-agent: Perplexity-User
+  User-agent: ClaudeBot
+  User-agent: Claude-SearchBot
+  User-agent: Google-Extended
+  User-agent: Applebot-Extended
+  Allow: /
+
+  # Default for everyone else
+  User-agent: *
+  Allow: /
+  Disallow: /wp-admin/
+  Disallow: /wp-login.php
+  Disallow: /checkout/
+  Disallow: /account/
+  Disallow: /cart/
+  Disallow: /*?utm_
+  Disallow: /*?fbclid
+
+  Sitemap: https://yourdomain.com/sitemap.xml
+  ```
+
+- **Validate fetchability**  
+  - Use `curl -A "PerplexityBot" -I https://yourdomain.com/your-page/`.  
+  - Expect `HTTP/2 200` and no `X-Robots-Tag: noindex`.
+
+- **CDN / WAF overrides**  
+  - Cloudflare “Block AI Bots” toggle (2024) overrides robots.txt. Set to “Allow”.  
+  - AWS WAF managed rules and Akamai Bot Manager may also block AI bots; disable AI‑bot blocking if you want them crawled.
+
+- **Re‑validate quarterly**  
+  - After CMS migrations, theme updates, security plugin installs, or CDN changes.  
+  - Use monitoring tools (Pingdom, UptimeRobot, CapstonAI robots watcher) to alert on changes.
+
+- **Common errors**  
+  - `Disallow: /` under `GPTBot` blocks both training and search bots.  
+  - Blocking only the training bot but not the search bot kills citations.  
+  - Blocking `/sitemap.xml` prevents bots from discovering URLs.  
+  - `noindex` meta tags block AI‑citation even if robots.txt allows.
+
+- **Impact data (Q1 2026 cohort)**  
+  - 41 % of B2B sites still block at least one major AI bot.  
+  - Each blocked bot costs an estimated 18‑34 % of potential AI citations.  
+  - Unblocking GPTBot + PerplexityBot + ClaudeBot in Q4 2025 led to +186 % AI‑attributed traffic in 90 days.
+
+**Sources:** https://capston.ai/robots-txt-for-ai-bots/, https://capston.ai/platform/, https://capston.ai/insights/, https://capston.ai/generative-engine-optimization/, https://schema.org/, https://platform.openai.com/docs/bots, https://anthropic.com/claudebot, https://developers.google.com/search/docs/crawling-indexing/google-common-crawlers, https://llmstxt.org/, CapstonAI Q1 2026 cohort benchmark.
```

## Decision (2026-10-31)

No lever moves. The audit it prescribes passes as it stands: robots.txt has no 'Disallow: /' line at all, and the search/citation agents (OAI-SearchBot, ChatGPT-User, PerplexityBot, Perplexity-User, Claude-SearchBot, Claude-User) are each named with 'Allow: /' (read 2026-10-31).
