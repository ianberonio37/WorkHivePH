---
name: change_external-ai-crawler-user-agents-2026-gptbot-claudebot-cla_2026-10-26
type: source-change
chunk: external-ai-crawler-user-agents-2026-gptbot-claudebot-cla
topic: AI crawler user agents 2026 GPTBot ClaudeBot Claude-SearchBot Claude-User PerplexityBot allow list robots.txt
source: https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026
detected: 2026-10-26
age_days: 81
ttl_days: 30
---

# external-ai-crawler-user-agents-2026-gptbot-claudebot-cla changed on re-fetch (2026-10-26)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-ai-crawler-user-agents-2026-gptbot-claudebot-cla (before)
+++ external-ai-crawler-user-agents-2026-gptbot-claudebot-cla (after)
@@ -1,28 +1,26 @@
-## reference · AI crawler user agents
-* AI crawlers like GPTBot, ClaudeBot, and PerplexityBot fetch web pages to power AI search and training.
-* Each AI company runs multiple bots: one for training, one for search indexing, and one for user-initiated retrieval.
-* To allow AI crawlers, add explicit `Allow` directives for each bot in the robots.txt file.
-* List crawlers individually in robots.txt to maintain control over which AI engine sees which part of the site.
-* OpenAI bots: 
-  + GPTBot (training)
-  + OAI-SearchBot (search indexing)
-  + ChatGPT-User (user fetch)
-* Anthropic bots: 
-  + ClaudeBot (training)
-  + Claude-SearchBot (search indexing)
-  + Claude-User (user fetch)
-* Perplexity bots: 
-  + PerplexityBot (search retrieval)
-  + Perplexity-User (user fetch, disputed robots.txt compliance)
-* Google bot: 
-  + Google-Extended (AI training)
-* Honors robots.txt: GPTBot, OAI-SearchBot, ClaudeBot, Claude-SearchBot, Claude-User, PerplexityBot, Google-Extended
-* Partially honors robots.txt: ChatGPT-User
-* Disputed robots.txt compliance: Perplexity-User
-* To track AI engine citations, use a visibility tool like Anagram.
-* Blocking AI training crawlers prevents content from being used in model training.
-* Blocking AI search and user agents removes content from eligibility for AI search citations and AI-generated answers.
-* Verify crawlers with reverse DNS lookup, not just user-agent string.
-* Avoid blocking bots by IP, as this can prevent bots from reading robots.txt.
-* Control happens at the user-agent level for compliant bots and at the WAF level for non-compliant bots.
-Sources: https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026, https://contently.com/2026/05/06/ai-crawlers-explained-gptbot-claudebot-perplexitybot/, https://almcorp.com/blog/anthropic-claude-bots-robots-txt-strategy/
+## reference · AI crawler user agents 2026 GPTBot ClaudeBot Claude-SearchBot Claude-User PerplexityBot allow list robots.txt
+
+- **Bot Roles & User Agents**: AI vendors operate distinct bots for training, search indexing, and user-initiated fetches. Blocking one does not block the others; each requires a separate `robots.txt` directive.
+  - **OpenAI**: `GPTBot` (training), `OAI-SearchBot` (search indexing), `ChatGPT-User` (user fetch).
+  - **Anthropic**: `ClaudeBot` (training), `Claude-SearchBot` (search indexing), `Claude-User` (user fetch).
+  - **Perplexity**: `PerplexityBot` (search retrieval), `Perplexity-User` (user fetch).
+  - **Google**: `Google-Extended` (AI training; distinct from `Googlebot` which handles standard search).
+- **robots.txt Configuration**:
+  - Use explicit `User-agent` and `Allow: /` directives for each specific bot to maintain granular control.
+  - **Allow for Visibility**: To appear in AI-generated answers, allow search and user agents (`OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`, `ChatGPT-User`, `Claude-User`).
+  - **Block for Training**: To prevent model training while retaining search visibility, disallow training agents (`GPTBot`, `ClaudeBot`, `Google-Extended`).
+  - **Google-Extended**: Blocking this prevents Gemini training but does not affect standard Google Search rankings.
+- **Compliance & Verification**:
+  - **Reverse DNS**: Verify bot authenticity via reverse DNS lookup (e.g., ClaudeBot IPs resolve to `anthropic.com`). Do not trust user-agent strings alone.
+  - **IP Blocking**: Avoid IP-based blocking for compliant bots; they often use public cloud IPs, and blocking may prevent them from reading `robots.txt`.
+  - **Non-Compliant Bots**: `Perplexity-User` is disputed (Perplexity claims it is an "agent" not a bot) and has been documented using undeclared crawlers to evade directives. `ChatGPT-User` is not fully governed by `robots.txt` per OpenAI documentation. For non-compliant bots, use WAF or server-level controls.
+- **Impact Metrics (2025–2026)**:
+  - AI search visits grew 42.8% YoY (15.6B to 27.4B) between Q1 2025 and Q1 2026.
+  - 87.4% of AI referral traffic originates from ChatGPT.
+  - ChatGPT reached 700M weekly active users by September 2025.
+- **Operational Checks**:
+  - Audit `robots.txt` for blanket `Disallow: /` under `User-agent: *`, which silently blocks all AI bots.
+  - Monitor server logs for specific user-agent tokens to confirm crawler access.
+  - Crawler access is necessary but not sufficient for citations; content structure and originality determine actual citation frequency.
+
+Sources: https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026
```
