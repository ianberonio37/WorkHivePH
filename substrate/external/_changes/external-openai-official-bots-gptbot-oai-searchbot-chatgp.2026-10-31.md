---
name: change_external-openai-official-bots-gptbot-oai-searchbot-chatgp_2026-10-31
type: source-change
chunk: external-openai-official-bots-gptbot-oai-searchbot-chatgp
topic: OpenAI official bots GPTBot OAI-SearchBot ChatGPT-User user agents ranges
source: https://platform.openai.com/docs/bots
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-openai-official-bots-gptbot-oai-searchbot-chatgp changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-openai-official-bots-gptbot-oai-searchbot-chatgp (before)
+++ external-openai-official-bots-gptbot-oai-searchbot-chatgp (after)
@@ -1,14 +1,38 @@
-## reference · OpenAI Bots and User Agents
-* OpenAI provides various bots and user agents, including GPTBot and OAI-SearchBot.
-* The OpenAI API supports multiple models, including GPT-5.6.
-* User agents can be used to identify and interact with OpenAI bots.
-* The OpenAI API has a rate limit and spend control to manage infrastructure and access.
-* The API supports Terraform provider for infrastructure management.
-* Private Link and workload identity federation are available for secure access.
-* OpenAI provides safety best practices, red teaming, and safety checks for secure development.
-* The API supports multiple tools, including shell, computer use, and code interpreter.
-* Realtime and audio features are available, including voice agents, live translation, and transcription.
-* The OpenAI API has a deployment checklist and production best practices for go-live.
-* Cost optimization, prompt caching, and batch processing are available for cost and throughput management.
-* OpenAI provides guides for safety, governance, and infrastructure management.
-Sources: https://platform.openai.com/docs/bots, https://developers.openai.com/api/docs
+## reference · OpenAI official bots GPTBot OAI-SearchBot ChatGPT-User user agents ranges
+
+*   **Bot Independence**: `OAI-SearchBot` and `GPTBot` operate independently. Webmasters can allow one while disallowing the other (e.g., allow search visibility but block training data).
+*   **Crawl Deduplication**: If a site allows both `OAI-SearchBot` and `GPTBot`, OpenAI may use a single crawl for both purposes to avoid duplication.
+*   **Propagation Delay**: Changes to `robots.txt` take approximately **24 hours** to be reflected in OpenAI's search systems.
+*   **IP Verification**: Always verify requests against published IP ranges to prevent spoofing.
+    *   `OAI-SearchBot`: `https://openai.com/searchbot.json`
+    *   `OAI-AdsBot`: `https://openai.com/adsbot.json`
+    *   `GPTBot`: `https://openai.com/gptbot.json`
+    *   `ChatGPT-User`: `https://openai.com/chatgpt-user.json`
+
+### User Agent Strings & Behavior
+
+*   **OAI-SearchBot**
+    *   **Purpose**: Surfaces websites in ChatGPT search results.
+    *   **Opt-out**: Disallowing this bot removes the site from search answers (may still appear as navigational links).
+    *   **UA String**: `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36; compatible; OAI-SearchBot/1.4; +https://openai.com/searchbot`
+    *   **Robots.txt Fetch**: May include `robots.txt` marker in UA: `...OAI-SearchBot/1.4; robots.txt; +https://openai.com/searchbot`
+
+*   **GPTBot**
+    *   **Purpose**: Crawls content for training generative AI foundation models.
+    *   **Opt-out**: Disallowing this bot indicates content should not be used for model training.
+    *   **UA String**: `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.4; +https://openai.com/gptbot`
+    *   **Robots.txt Fetch**: May include `robots.txt` marker in UA.
+
+*   **ChatGPT-User**
+    *   **Purpose**: Represents user-initiated actions (e.g., visiting a page when a user asks a question, or interacting via GPT Actions).
+    *   **Crawling**: **Not** used for automatic web crawling.
+    *   **Robots.txt**: `robots.txt` rules **may not apply** because actions are user-initiated. Do not use this bot for managing search opt-outs.
+    *   **UA String**: `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot`
+
+*   **OAI-AdsBot**
+    *   **Purpose**: Validates safety of web pages submitted as ads on ChatGPT.
+    *   **Scope**: Only visits pages explicitly submitted as ads.
+    *   **Training**: Data collected is **not** used to train generative AI foundation models.
+    *   **UA String**: `Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-AdsBot/1.0; +https://openai.com/adsbot`
+
+Sources: https://platform.openai.com/docs/bots
```

## Decision (2026-10-31)

No lever moves. OpenAI's bots are independent (GPTBot, OAI-SearchBot, OAI-AdsBot, ChatGPT-User) and robots.txt names each (read 2026-10-31); the 24-hour propagation and published IP ranges change nothing the site does.
