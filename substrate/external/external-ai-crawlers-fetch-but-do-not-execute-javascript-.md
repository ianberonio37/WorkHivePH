---
name: external-ai-crawlers-fetch-but-do-not-execute-javascript-
type: reference
source: https://vercel.com/blog/the-rise-of-the-ai-crawler
source_sha: 415db63344160e3b
fetched_at: 2026-10-30T16:24:22Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: AI crawlers fetch but do not execute JavaScript SEO
---

## reference · AI crawlers fetch but do not execute JavaScript SEO

- **JavaScript Execution**: Major AI crawlers (OpenAI GPTBot, Anthropic ClaudeBot, Meta-ExternalAgent, ByteDance Bytespider, PerplexityBot) **fetch** but do **not execute** JavaScript. They cannot read client-side rendered (CSR) content.
- **Rendering Exceptions**:
    - **Google Gemini**: Uses Googlebot infrastructure; supports full JavaScript rendering.
    - **AppleBot**: Renders JavaScript via browser-based crawler (processes JS, CSS, Ajax).
    - **Common Crawl (CCBot)**: Does not render pages.
- **Fetch vs. Execute Metrics**:
    - ChatGPT fetches JS files in ~11.50% of requests but does not execute them.
    - Claude fetches JS files in ~23.84% of requests but does not execute them.
    - Content in the initial HTML response (e.g., JSON, delayed React Server Components) is still indexed by AI models.
- **Traffic Volume (Vercel Network, Dec 2024)**:
    - Googlebot: 4.5 billion fetches.
    - GPTBot: 569 million fetches.
    - Claude: 370 million fetches.
    - AppleBot: 314 million fetches.
    - PerplexityBot: 24.4 million fetches.
    - Combined AI crawler volume (GPTBot, Claude, AppleBot, Perplexity) is ~28% of Googlebot volume.
- **Geographic Distribution**:
    - AI crawlers operate primarily from U.S. data centers (e.g., ChatGPT: Iowa/Arizona; Claude: Ohio).
    - Googlebot operates from multiple U.S. locations (7+).
- **Content Priorities**:
    - ChatGPT: Prioritizes HTML (57.70% of fetches).
    - Claude: Prioritizes images (35.17% of fetches).
    - Googlebot: More evenly distributed (HTML 31%, JSON 29.34%, Text 20.77%, JS 15.25%).
- **Crawling Inefficiency**:
    - High 404 rates: ChatGPT (34.82%) and Claude (34.16%) hit 404s frequently, often targeting outdated `/static/` assets.
    - High redirect rates: ChatGPT spends 14.36% of fetches on redirects.
    - Comparison: Googlebot has only 8.22% 404s and 1.49% redirects.
- **SEO Recommendations**:
    - **Server-Side Rendering (SSR)**: Critical content (articles, product info, meta tags, navigation) must be server-rendered (SSR, ISR, or SSG) to be visible to AI crawlers.
    - **Client-Side Rendering (CSR)**: Acceptable only for non-essential enhancements (view counters, live chat, social feeds).
    - **URL Management**: Maintain accurate sitemaps and consistent URL patterns to mitigate high 404 rates from AI crawlers.
- **Blocking AI Crawlers**:
    - Use `robots.txt` to disallow specific AI user agents (e.g., `GPTBot`, `ClaudeBot`).
    - Use Vercel WAF "Block AI Bots" firewall rule for one-click blocking.
- **User Impact**:
    - AI responses about dynamic web apps may be incomplete or outdated due to lack of JS execution.
    - High 404 rates mean AI-cited URLs may be incorrect; verify sources directly.

Sources: https://vercel.com/blog/the-rise-of-the-ai-crawler
