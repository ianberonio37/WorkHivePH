---
name: change_external-anthropic-official-crawler-documentation-claudeb_2026-10-31
type: source-change
chunk: external-anthropic-official-crawler-documentation-claudeb
topic: Anthropic official crawler documentation ClaudeBot Claude-User Claude-SearchBot robots.txt crawl-delay
source: https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-anthropic-official-crawler-documentation-claudeb changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-anthropic-official-crawler-documentation-claudeb (before)
+++ external-anthropic-official-crawler-documentation-claudeb (after)
@@ -1,12 +1,27 @@
-## reference · Anthropic crawler documentation
-* Anthropic uses three robots to gather data from the public web: ClaudeBot, Claude-User, and Claude-SearchBot.
-* ClaudeBot collects web content for AI model training datasets.
-* Claude-User supports Claude AI users by accessing websites in response to user queries.
-* Claude-SearchBot navigates the web to improve search result quality for users.
-* To block a Bot from a website, add a "Disallow: /" directive to the robots.txt file for the specific User-agent (e.g. ClaudeBot).
-* To limit crawling activity, use the non-standard Crawl-delay extension to robots.txt (e.g. "Crawl-delay: 1").
-* Anthropic's Bots respect "do not crawl" signals by honoring industry standard directives in robots.txt.
-* Anthropic's Bots respect anti-circumvention technologies (e.g. CAPTCHAs).
-* To opt out of being crawled by Anthropic Bots, modify the robots.txt file; blocking IP addresses may not work correctly.
-* A list of source IP addresses for Anthropic Bots can be found at https://claude.com/crawling/bots.json.
+## reference · Anthropic crawler robots.txt configuration
+
+- **Bot Identification**: Anthropic uses three distinct user-agents for web access:
+  - `ClaudeBot`: Collects public web content for AI model training and safety enhancement.
+  - `Claude-User`: Retrieves content in response to specific user-initiated queries (user-directed web search).
+  - `Claude-SearchBot`: Indexes and analyzes content to improve the relevance and accuracy of general search results.
+- **Blocking via robots.txt**: To opt out of crawling, modify the `robots.txt` file in the top-level directory of the domain.
+  - **Block entire site**: Use `Disallow: /` under the specific user-agent.
+    ```text
+    User-agent: ClaudeBot
+    Disallow: /
+    ```
+  - **Subdomains**: The `robots.txt` directive must be applied to **every** subdomain individually to ensure complete opt-out.
+  - **Crawl-delay**: Anthropic supports the non-standard `Crawl-delay` extension to limit request frequency.
+    ```text
+    User-agent: ClaudeBot
+    Crawl-delay: 1
+    ```
+- **IP Blocking Limitations**: Blocking Anthropic's source IP addresses is **not** a reliable or persistent method for opting out. IP blocking may prevent the crawler from reading the `robots.txt` file, potentially invalidating the opt-out signal.
+- **IP Verification**: Verify if a crawler originates from Anthropic by checking its source IP against the public list at `https://claude.com/crawling/bots.json`.
+- **Compliance Principles**:
+  - Anthropic honors standard `robots.txt` directives.
+  - Anthropic respects anti-circumvention technologies (e.g., will not bypass CAPTCHAs).
+  - Crawling is designed to be non-intrusive, respecting `Crawl-delay` to minimize domain disruption.
+- **Contact**: For malfunction reports or further questions, contact `claudebot@anthropic.com`. The sender's email domain must match the domain being reported for verification purposes.
+
 Sources: https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
```

## Decision (2026-10-31)

No lever moves. Anthropic's three agents (ClaudeBot, Claude-User, Claude-SearchBot) are all named in robots.txt (read 2026-10-31); the per-subdomain rule needs nothing, as the site serves one host; Crawl-delay is not used and not needed.
