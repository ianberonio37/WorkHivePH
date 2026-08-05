---
name: external-anthropic-official-crawler-documentation-claudeb
type: reference
source: https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
source_sha: 94249fac3bfcb84c
fetched_at: 2026-08-05T03:59:50Z
last_verified: 2026-08-05
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Anthropic official crawler documentation ClaudeBot Claude-User Claude-SearchBot robots.txt crawl-delay
---

## reference · Anthropic crawler documentation
* Anthropic uses three robots to gather data from the public web: ClaudeBot, Claude-User, and Claude-SearchBot.
* ClaudeBot collects web content for AI model training datasets.
* Claude-User supports Claude AI users by accessing websites in response to user queries.
* Claude-SearchBot navigates the web to improve search result quality for users.
* To block a Bot from a website, add a "Disallow: /" directive to the robots.txt file for the specific User-agent (e.g. ClaudeBot).
* To limit crawling activity, use the non-standard Crawl-delay extension to robots.txt (e.g. "Crawl-delay: 1").
* Anthropic's Bots respect "do not crawl" signals by honoring industry standard directives in robots.txt.
* Anthropic's Bots respect anti-circumvention technologies (e.g. CAPTCHAs).
* To opt out of being crawled by Anthropic Bots, modify the robots.txt file; blocking IP addresses may not work correctly.
* A list of source IP addresses for Anthropic Bots can be found at https://claude.com/crawling/bots.json.
Sources: https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
