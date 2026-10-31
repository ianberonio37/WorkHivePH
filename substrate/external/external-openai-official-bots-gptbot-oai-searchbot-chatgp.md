---
name: external-openai-official-bots-gptbot-oai-searchbot-chatgp
type: reference
source: https://platform.openai.com/docs/bots
source_sha: b1678d0501dc7a42
fetched_at: 2026-10-30T17:18:56Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: OpenAI official bots GPTBot OAI-SearchBot ChatGPT-User user agents ranges
---

## reference · OpenAI official bots GPTBot OAI-SearchBot ChatGPT-User user agents ranges

*   **Bot Independence**: `OAI-SearchBot` and `GPTBot` operate independently. Webmasters can allow one while disallowing the other (e.g., allow search visibility but block training data).
*   **Crawl Deduplication**: If a site allows both `OAI-SearchBot` and `GPTBot`, OpenAI may use a single crawl for both purposes to avoid duplication.
*   **Propagation Delay**: Changes to `robots.txt` take approximately **24 hours** to be reflected in OpenAI's search systems.
*   **IP Verification**: Always verify requests against published IP ranges to prevent spoofing.
    *   `OAI-SearchBot`: `https://openai.com/searchbot.json`
    *   `OAI-AdsBot`: `https://openai.com/adsbot.json`
    *   `GPTBot`: `https://openai.com/gptbot.json`
    *   `ChatGPT-User`: `https://openai.com/chatgpt-user.json`

### User Agent Strings & Behavior

*   **OAI-SearchBot**
    *   **Purpose**: Surfaces websites in ChatGPT search results.
    *   **Opt-out**: Disallowing this bot removes the site from search answers (may still appear as navigational links).
    *   **UA String**: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36; compatible; OAI-SearchBot/1.4; +https://openai.com/searchbot`
    *   **Robots.txt Fetch**: May include `robots.txt` marker in UA: `...OAI-SearchBot/1.4; robots.txt; +https://openai.com/searchbot`

*   **GPTBot**
    *   **Purpose**: Crawls content for training generative AI foundation models.
    *   **Opt-out**: Disallowing this bot indicates content should not be used for model training.
    *   **UA String**: `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.4; +https://openai.com/gptbot`
    *   **Robots.txt Fetch**: May include `robots.txt` marker in UA.

*   **ChatGPT-User**
    *   **Purpose**: Represents user-initiated actions (e.g., visiting a page when a user asks a question, or interacting via GPT Actions).
    *   **Crawling**: **Not** used for automatic web crawling.
    *   **Robots.txt**: `robots.txt` rules **may not apply** because actions are user-initiated. Do not use this bot for managing search opt-outs.
    *   **UA String**: `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot`

*   **OAI-AdsBot**
    *   **Purpose**: Validates safety of web pages submitted as ads on ChatGPT.
    *   **Scope**: Only visits pages explicitly submitted as ads.
    *   **Training**: Data collected is **not** used to train generative AI foundation models.
    *   **UA String**: `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-AdsBot/1.0; +https://openai.com/adsbot`

Sources: https://platform.openai.com/docs/bots
