---
name: external-ai-crawler-user-agents-2026-gptbot-claudebot-cla
type: reference
source: https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026
source_sha: 1d803d2fdafbf4a6
fetched_at: 2026-08-05T02:35:57Z
last_verified: 2026-08-05
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: AI crawler user agents 2026 GPTBot ClaudeBot Claude-SearchBot Claude-User PerplexityBot allow list robots.txt
---

## reference · AI crawler user agents
* AI crawlers like GPTBot, ClaudeBot, and PerplexityBot fetch web pages to power AI search and training.
* Each AI company runs multiple bots: one for training, one for search indexing, and one for user-initiated retrieval.
* To allow AI crawlers, add explicit `Allow` directives for each bot in the robots.txt file.
* List crawlers individually in robots.txt to maintain control over which AI engine sees which part of the site.
* OpenAI bots: 
  + GPTBot (training)
  + OAI-SearchBot (search indexing)
  + ChatGPT-User (user fetch)
* Anthropic bots: 
  + ClaudeBot (training)
  + Claude-SearchBot (search indexing)
  + Claude-User (user fetch)
* Perplexity bots: 
  + PerplexityBot (search retrieval)
  + Perplexity-User (user fetch, disputed robots.txt compliance)
* Google bot: 
  + Google-Extended (AI training)
* Honors robots.txt: GPTBot, OAI-SearchBot, ClaudeBot, Claude-SearchBot, Claude-User, PerplexityBot, Google-Extended
* Partially honors robots.txt: ChatGPT-User
* Disputed robots.txt compliance: Perplexity-User
* To track AI engine citations, use a visibility tool like Anagram.
* Blocking AI training crawlers prevents content from being used in model training.
* Blocking AI search and user agents removes content from eligibility for AI search citations and AI-generated answers.
* Verify crawlers with reverse DNS lookup, not just user-agent string.
* Avoid blocking bots by IP, as this can prevent bots from reading robots.txt.
* Control happens at the user-agent level for compliant bots and at the WAF level for non-compliant bots.
Sources: https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026, https://contently.com/2026/05/06/ai-crawlers-explained-gptbot-claudebot-perplexitybot/, https://almcorp.com/blog/anthropic-claude-bots-robots-txt-strategy/
