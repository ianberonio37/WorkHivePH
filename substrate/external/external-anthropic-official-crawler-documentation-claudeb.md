---
name: external-anthropic-official-crawler-documentation-claudeb
type: reference
source: https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
source_sha: 4793810b75f7de90
fetched_at: 2026-10-30T16:39:01Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: Anthropic official crawler documentation ClaudeBot Claude-User Claude-SearchBot robots.txt crawl-delay
---

## reference · Anthropic crawler robots.txt configuration

- **Bot Identification**: Anthropic uses three distinct user-agents for web access:
  - `ClaudeBot`: Collects public web content for AI model training and safety enhancement.
  - `Claude-User`: Retrieves content in response to specific user-initiated queries (user-directed web search).
  - `Claude-SearchBot`: Indexes and analyzes content to improve the relevance and accuracy of general search results.
- **Blocking via robots.txt**: To opt out of crawling, modify the `robots.txt` file in the top-level directory of the domain.
  - **Block entire site**: Use `Disallow: /` under the specific user-agent.
    ```text
    User-agent: ClaudeBot
    Disallow: /
    ```
  - **Subdomains**: The `robots.txt` directive must be applied to **every** subdomain individually to ensure complete opt-out.
  - **Crawl-delay**: Anthropic supports the non-standard `Crawl-delay` extension to limit request frequency.
    ```text
    User-agent: ClaudeBot
    Crawl-delay: 1
    ```
- **IP Blocking Limitations**: Blocking Anthropic's source IP addresses is **not** a reliable or persistent method for opting out. IP blocking may prevent the crawler from reading the `robots.txt` file, potentially invalidating the opt-out signal.
- **IP Verification**: Verify if a crawler originates from Anthropic by checking its source IP against the public list at `https://claude.com/crawling/bots.json`.
- **Compliance Principles**:
  - Anthropic honors standard `robots.txt` directives.
  - Anthropic respects anti-circumvention technologies (e.g., will not bypass CAPTCHAs).
  - Crawling is designed to be non-intrusive, respecting `Crawl-delay` to minimize domain disruption.
- **Contact**: For malfunction reports or further questions, contact `claudebot@anthropic.com`. The sender's email domain must match the domain being reported for verification purposes.

Sources: https://support.anthropic.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
