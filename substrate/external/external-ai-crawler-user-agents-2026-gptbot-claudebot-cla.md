---
name: external-ai-crawler-user-agents-2026-gptbot-claudebot-cla
type: reference
source: https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026
source_sha: 22a909fa001dec23
fetched_at: 2026-10-25T21:55:59Z
last_verified: 2026-10-26
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: AI crawler user agents 2026 GPTBot ClaudeBot Claude-SearchBot Claude-User PerplexityBot allow list robots.txt
---

## reference · AI crawler user agents 2026 GPTBot ClaudeBot Claude-SearchBot Claude-User PerplexityBot allow list robots.txt

- **Bot Roles & User Agents**: AI vendors operate distinct bots for training, search indexing, and user-initiated fetches. Blocking one does not block the others; each requires a separate `robots.txt` directive.
  - **OpenAI**: `GPTBot` (training), `OAI-SearchBot` (search indexing), `ChatGPT-User` (user fetch).
  - **Anthropic**: `ClaudeBot` (training), `Claude-SearchBot` (search indexing), `Claude-User` (user fetch).
  - **Perplexity**: `PerplexityBot` (search retrieval), `Perplexity-User` (user fetch).
  - **Google**: `Google-Extended` (AI training; distinct from `Googlebot` which handles standard search).
- **robots.txt Configuration**:
  - Use explicit `User-agent` and `Allow: /` directives for each specific bot to maintain granular control.
  - **Allow for Visibility**: To appear in AI-generated answers, allow search and user agents (`OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`, `ChatGPT-User`, `Claude-User`).
  - **Block for Training**: To prevent model training while retaining search visibility, disallow training agents (`GPTBot`, `ClaudeBot`, `Google-Extended`).
  - **Google-Extended**: Blocking this prevents Gemini training but does not affect standard Google Search rankings.
- **Compliance & Verification**:
  - **Reverse DNS**: Verify bot authenticity via reverse DNS lookup (e.g., ClaudeBot IPs resolve to `anthropic.com`). Do not trust user-agent strings alone.
  - **IP Blocking**: Avoid IP-based blocking for compliant bots; they often use public cloud IPs, and blocking may prevent them from reading `robots.txt`.
  - **Non-Compliant Bots**: `Perplexity-User` is disputed (Perplexity claims it is an "agent" not a bot) and has been documented using undeclared crawlers to evade directives. `ChatGPT-User` is not fully governed by `robots.txt` per OpenAI documentation. For non-compliant bots, use WAF or server-level controls.
- **Impact Metrics (2025–2026)**:
  - AI search visits grew 42.8% YoY (15.6B to 27.4B) between Q1 2025 and Q1 2026.
  - 87.4% of AI referral traffic originates from ChatGPT.
  - ChatGPT reached 700M weekly active users by September 2025.
- **Operational Checks**:
  - Audit `robots.txt` for blanket `Disallow: /` under `User-agent: *`, which silently blocks all AI bots.
  - Monitor server logs for specific user-agent tokens to confirm crawler access.
  - Crawler access is necessary but not sufficient for citations; content structure and originality determine actual citation frequency.

Sources: https://www.anagram.ai/blog/ai-crawlers-explained-gptbot-claudebot-perplexitybot-and-how-to-let-them-in-2026
