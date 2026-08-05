---
name: external-robots-txt-for-ai-bots-blocking-cost-citation-lo
type: reference
source: https://capston.ai/robots-txt-for-ai-bots/
source_sha: 1f50d6c564bd9c2b
fetched_at: 2026-08-05T02:42:29Z
last_verified: 2026-08-05
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: robots.txt for AI bots blocking cost citation loss per engine 2026
---

## reference · robots.txt for AI bots
* A robots.txt file for AI bots tells AI crawlers which parts of a site they may access, controlling whether content can be read and used by AI engines.
* Blocking a bot in robots.txt can cost 18-34% of potential AI citations on that engine.
* Sites that unblock GPTBot, PerplexityBot, and ClaudeBot can see +186% AI-attributed traffic in 90 days.
* Allow the following search/citation bots in robots.txt:
	+ OAI-SearchBot
	+ ChatGPT-User
	+ PerplexityBot
	+ Perplexity-User
	+ ClaudeBot
	+ Claude-SearchBot
	+ Google-Extended
	+ Applebot-Extended
* Keep sensitive paths blocked for all bots:
	+ /wp-admin/
	+ /wp-login.php
	+ /checkout/
	+ /account/
	+ /cart/
	+ /search?
	+ /*?utm_
* Add a sitemap reference to robots.txt:
	+ Sitemap: https://yourdomain.com/sitemap.xml
* Validate robots.txt with each engine's documented user-agent.
* Re-check robots.txt after every CMS upgrade.
* Common technical errors include:
	+ Disallowing a bot under a wrong user-agent
	+ Blocking only the training bot but forgetting the search bot
	+ Leaving Cloudflare's "Block AI Bots" toggle on
	+ Blocking /sitemap.xml or sitemap path
	+ Using noindex meta on pages that should be AI-cited
* Trade-offs of blocking AI bots:
	+ Blocking protects content from AI training and answers, but removes the chance of being cited by AI engines.
* Difference between robots.txt and llms.txt:
	+ robots.txt controls which crawlers may access a site
	+ llms.txt is a curated map that guides AI models to important content
Sources: https://capston.ai/robots-txt-for-ai-bots/
