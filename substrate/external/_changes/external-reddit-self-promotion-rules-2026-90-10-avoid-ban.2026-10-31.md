---
name: change_external-reddit-self-promotion-rules-2026-90-10-avoid-ban_2026-10-31
type: source-change
chunk: external-reddit-self-promotion-rules-2026-90-10-avoid-ban
topic: Reddit self-promotion rules 2026 90/10 avoid ban brand marketing
source: https://redship.io/blog/reddit-self-promotion-rules
detected: 2026-10-31
age_days: 88
ttl_days: 30
---

# external-reddit-self-promotion-rules-2026-90-10-avoid-ban changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-reddit-self-promotion-rules-2026-90-10-avoid-ban (before)
+++ external-reddit-self-promotion-rules-2026-90-10-avoid-ban (after)
@@ -1,13 +1,33 @@
-## reference · Reddit self-promotion rules 2026 90/10 avoid ban brand marketing
+## reference · Reddit self-promotion rules
 
-* **90/10 rule**: 90% of your activity should be genuine participation (comments, upvotes, discussions, helping people) and no more than 10% should involve mentioning your own product or content.
-* **Read subreddit rules before posting**: Every subreddit has its own rules in the sidebar, and posting without reading them is the fastest way to get banned.
-* **Never use multiple accounts to promote the same product**: Creating separate accounts to upvote your own content, post fake recommendations, or simulate multiple people praising your product will get all your accounts permanently suspended.
-* **Tone matters more than you think**: Reddit users detect marketing language from a mile away. Use honest, conversational language instead of sales-y language.
-* **Disclose your affiliation**: If you're the founder, an employee, or in any way connected to the product you're mentioning, say so. Reddit communities respect transparency and punish deception.
-* **Don't post the same thing across multiple subreddits**: Cross-posting identical promotional content to many subreddits at once is a major red flag and can get your account banned.
-* **Find conversations, don't create them**: Look for existing threads where someone asks about a problem your product solves, and respond to the question first. Mention your product only if genuinely relevant.
-* **Lead with value, mention your product second**: Answer the question first, share useful context, and then mention your product as one option among several.
-* **Be transparent and humble**: Disclose your connection, acknowledge limitations, and recommend competitors when they're a better fit.
-* **Respect the outcome**: If your comment gets downvoted or removed, don't argue. Learn and adjust.
+*   **Core Principle:** Reddit prohibits "bad" self-promotion, not self-promotion itself. The guiding ethos is "be a redditor with a website, not a website with a Reddit account."
+*   **The 90/10 Rule:** Maintain a ratio of at least 90% genuine community participation (comments, upvotes, helpful answers) to no more than 10% self-promotional content.
+    *   *Strict Subreddits:* Some communities enforce a 99/1 ratio; any self-promotion in history may trigger removal.
+    *   *Verification:* Moderators routinely check user profiles for prior activity before allowing promotional comments. A history of only product links results in instant flagging.
+*   **Subreddit-Specific Rules:**
+    *   Always read the sidebar rules of every subreddit before posting. Rules vary wildly (e.g., r/freelance bans all self-promo; r/SideProject encourages it).
+    *   Subreddit bans are usually permanent.
+    *   Some subs allow promotion only in designated weekly threads (e.g., r/startups "Share Your Startup").
+*   **Prohibited Actions (Instant Ban Triggers):**
+    *   **Sockpuppeting:** Using multiple accounts to upvote, recommend, or simulate community interest in your product. This leads to permanent suspension of all associated accounts.
+    *   **Cross-Posting:** Posting identical promotional content to multiple subreddits simultaneously. Reddit’s ML spam filters detect this pattern within minutes, often resulting in a sitewide shadow ban.
+    *   **Launch Day Blasts:** Posting product links in 5+ subreddits in one day with no prior comment history is the fastest way to get shadow banned.
+*   **Tone and Content Guidelines:**
+    *   **Avoid Marketing Jargon:** Words like "revolutionary," "game-changing," or "best solution" trigger skepticism and downvotes.
+    *   **Adopt a Peer Tone:** Write as a friend giving honest advice. Acknowledge limitations and recommend competitors if they are a better fit for specific needs.
+    *   **Disclose Affiliation:** Always state if you are the founder, employee, or affiliated with the product (e.g., "Full disclosure: I built this"). Transparency increases trust.
+    *   **Value-First Structure:** Answer the user's question or provide useful context *before* mentioning your product. Frame your product as one option among several, not the only solution.
+*   **Enforcement Levels:**
+    *   **Removal:** Content deleted; account remains active.
+    *   **Shadow Ban (Subreddit):** Posts invisible in that specific community.
+    *   **Shadow Ban (Sitewide):** Posts invisible everywhere. Hard to detect (engagement drops to zero) and very difficult to reverse. Check r/ShadowBan to verify status.
+    *   **Account Suspension:** Permanent ban from the entire platform.
+*   **Safe Subreddits for Promotion:**
+    *   r/SideProject, r/IndieBiz, r/IMadeThis, r/SomebodyMakeThis, r/AlphaAndBetaUsers.
+    *   *Note:* These have smaller audiences than niche industry subs. Long-term value comes from authentic participation in larger, niche-specific communities.
+*   **Practical Framework:**
+    1.  **Build History:** Spend 2–4 weeks actively participating and building karma before promoting.
+    2.  **Find Conversations:** Respond to existing threads where users ask about problems your product solves; do not create new promotional posts.
+    3.  **Lead with Value:** Provide the answer first; mention the product only if directly relevant.
+    4.  **Respect Outcomes:** If downvoted or removed, do not argue with mods or users. Adjust strategy instead.
 
```

## Decision (2026-10-31)

No lever moves; the strategy's '90/10 rule - 90% genuine help, at most 10% self-mention, disclose affiliation' (STRATEGY_V2 line 147) is exactly what the re-fetch states. New detail (some subreddits enforce 99/1; read each sidebar) is execution guidance for whoever posts, quoted nowhere.
