---
name: external-ai-user-agent-landscape-2026-complete-reference-
type: reference
source: https://nohacks.co/blog/ai-user-agents-landscape-2026
source_sha: 88d0265b9f149fec
fetched_at: 2026-08-05T02:39:41Z
last_verified: 2026-08-05
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: AI user agent landscape 2026 complete reference training vs retrieval bots tokens
---

## reference · AI user agent landscape 2026
* There are at least 5 functionally distinct categories of AI user agents: Training Crawlers, Search and Retrieval Crawlers, User-Triggered Fetchers, Opt-Out Tokens, and Undeclared and Masquerading Traffic.
* `robots.txt` was designed in 1994 for a world with one kind of crawler and is no longer sufficient for modern AI traffic.
* AI crawlers can be blocked using `robots.txt` directives, but the effectiveness of these directives varies by vendor.
* Training Crawlers:
  + GPTBot (OpenAI): respects `robots.txt`, user-agent `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)`, published IP ranges `https://openai.com/gptbot.json`.
  + ClaudeBot (Anthropic): respects `robots.txt`, user-agent `Mozilla/5.0 (compatible; ClaudeBot/1.0; +claudebot@anthropic.com)`, no published IP ranges.
  + Amazonbot: respects `robots.txt`, user-agent `Mozilla/5.0 (compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot) Chrome/119.0.6045.214 Safari/537.36`, no published IP ranges.
  + Meta-ExternalAgent: respects `robots.txt`, user-agent `meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)`, no published IP ranges.
  + CCBot (Common Crawl): respects `robots.txt`, user-agent `CCBot/2.0 (https://commoncrawl.org/faq/)`, published IP ranges `https://index.commoncrawl.org/ccbot.json`.
* Search and Retrieval Crawlers:
  + OAI-SearchBot (OpenAI): respects `robots.txt`.
  + Claude-SearchBot (Anthropic): respects `robots.txt`.
  + PerplexityBot (Perplexity): respects `robots.txt`.
  + Bingbot (Microsoft): respects `robots.txt`.
* User-Triggered Fetchers:
  + Google-Agent (Google): ignores `robots.txt`.
  + ChatGPT-User (OpenAI): respects `robots.txt`.
  + Claude-User (Anthropic): respects `robots.txt`.
* Opt-Out Tokens:
  + Google-Extended (Google): opt-out token for training, does not appear in access logs.
  + Applebot-Extended (Apple): opt-out token for training, does not appear in access logs.
* Undeclared and Masquerading Traffic:
  + Bytespider (ByteDance): no vendor documentation, treat as undocumented.
  + xAI Grok (xAI): no vendor documentation, treat as undocumented.
* Over 2.5 million websites have chosen to completely disallow AI training through Cloudflare's managed `robots.txt` feature or its managed rule blocking AI crawlers.
* Cloudflare reported that AI crawlers were generating over 50 billion requests per day in March 2025.
Sources: https://nohacks.co/blog/ai-user-agents-landscape-2026, https://blog.cloudflare.com/ai-labyrinth/, https://blog.cloudflare.com/uk-google-ai-crawler-policy/
