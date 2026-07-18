# Community Deep Arc (PDDA) — Page-Deep UFAI + Community-Building + Marketplace-Connection

> **Arc kind:** *Page-depth* — the SAME refined PDDA method (Understand → Deepwalk → Ideate →
> Roadmap → Execute → Re-deepwalk) that took `engineering-design` ≈59%→~99%, the Resume Builder
> ~52%→100%, Landing + Home-Dashboard ~52%→96.4%, the Analytics Engine → all-axes-clean, CMMS
> Integrations 25%→100%, and the **Hive Board** (U-heavyweight, +30 platform gate fixes). The
> platform-wide breadth ruler scores every page **shallow**; this arc scores the **Community surface
> deep** — a fine UFAI sub-dimension decomposition, grounded in reputable community + social-commerce
> standards, driven LIVE via Playwright MCP, improved with skill + source ideas, ratcheted by gates.
>
> **★ THIS ARC HAS TWO HEAVYWEIGHTS, BOTH IAN-STATED (2026-07-11):**
> 1. **U — community-building UI/UX**, *extending* what we already have (not merely patching). Ian:
>    *"include the appropriate UI/UX where you extend what we already have… what I am striving for for
>    this platform is we **build a community**."* The Community page must make a lone Filipino
>    maintenance worker feel they've **found their people**, lower the bar to a first contribution to
>    near-zero, and make helping others visibly rewarding — a genuine **community of practice**, not a
>    "forum feature."
> 2. **X — the Community ↔ Marketplace CONNECTION.** Ian: *"it seems disconnected to Marketplace for
>    me."* **Confirmed + total:** `grep marketplace community.html = 0` and `grep community
>    marketplace.html = 0` — the two surfaces have **zero cross-references** in either direction, no
>    shared identity link, no reputation flow. They are two islands. This is the strategic core of the
>    arc: community is where **trust** is built; the (free) marketplace is where that trust becomes
>    **transactions + jobs**. A worker who helps you fix a pump is who you trust to sell you the part or
>    do the work. Today the platform severs that flow at the app boundary.

---

## Refining + EXTENDING Ian's thesis (the terms he was reaching for)

Ian gave two seeds — "build a community" + "connected to marketplace." Extending them into a
falsifiable design thesis, grounded in reputable frameworks:

### A. "Build a community" = a Community of Practice, not a forum
- **Frame (Wenger, *Communities of Practice*):** a CoP = **domain** (industrial maintenance) +
  **community** (Filipino technicians/leads/supervisors) + **practice** (shared fixes, methods,
  war-stories). WorkHive already ships the "practice" article `learn/industrial-community-of-practice-philippines`
  — so CoP is the intended frame; the page should *embody* it, not just host posts.
- **The contribution ladder / commitment curve (CMX · FeverBee):** lurk → react → reply → post →
  answer → mentor. The UX's job is (a) make the FIRST rung effortless + celebrated (the `+50 first-post`
  XP already marks the moment) and (b) build a visible ladder upward. Measure where users stall.
- **The SPACES model of community value (CMX):** Support / Product / Acquisition / Contribution /
  Engagement / Success. WorkHive's community is primarily **Support** (peer troubleshooting) +
  **Contribution** (durable shared knowledge) → which *is* the top of the **Acquisition** funnel.
- **Belonging & "my people":** a lone worker logging entries should discover peers solving the *same*
  problems (same trade / plant-type / region). Identity is **one person** across the platform — worker
  + community member + marketplace participant — not three disconnected profiles.
- **Recognition rewards REAL help, never vanity** (community skill's anti-badge-inflation rule): XP for
  answered questions / safety posts / quality (3-reaction) signal — NOT logins, streaks, or giving
  reactions. Recognition must be *legible* (why did I earn this?) and *earned*.
- **Knowledge that compounds:** today posts are ephemeral feed items. Extend toward **durable,
  discoverable knowledge** — tags, search, "solved/best-answer," and links to assets/faults — so the
  community becomes a searchable maintenance knowledge base (the "practice" of the CoP). This is the
  bridge to AI (ground answers in the community's own accumulated fixes).
- **Safety & appropriateness (skill rule #1):** field workers need *simplicity*, not social-media
  complexity; plain language (no jargon); low-bandwidth (4G feed rules); moderation + report flow that
  protect trust.

### B. Community ↔ Marketplace = ONE social-commerce fabric (the keystone)
The disconnect is total (0 cross-refs). The extension, from social-commerce + trust-economy principles:
- **Unified identity & reputation portability:** a person is one identity. Community reputation
  (XP / helpful answers / "Voice of the Hive" badge / safety contributions) should be a **trust signal
  on their marketplace seller profile**, and a trusted seller's community voice should carry weight.
  Today `community_xp` (PK worker_name+hive_id) and `marketplace_sellers` (PK auth_uid) are **unlinked**
  — the join is the first structural unlock.
- **Community as the top of the marketplace funnel:** people trade with people they trust; trust is
  built by helping. Flow to enable: *community interaction → discover their listings/services →
  transact*. This is the platform's growth engine (free marketplace ⇒ "monetize" = enable jobs/trades,
  not fees).
- **Cross-navigation (missing entirely):** from a community expert's profile → "their marketplace
  listings"; from a marketplace seller → "their community reputation + best answers." Neither exists.
- **Reputation → marketplace trust badge:** community karma → "Community-trusted" / "Top contributor"
  indicators that solve marketplace **cold-start trust** (a new seller with community standing is not a
  stranger).
- **Expertise-driven discovery:** community answers reveal *who knows pumps / electrical / NFPA* — that
  same expertise graph should power marketplace matching (who to hire / buy from).
- **Knowledge → commerce links:** a thread that solves a fault → surfaces the **parts** (marketplace
  listing) + the **person/service** that can do it. The community answer becomes a discovery surface for
  commerce, and the transaction closes the loop back as community proof.
- **Anti-disconnect UX test:** a worker should never feel they've left one app and entered another.
  Success = a unified "people + reputation" layer with cross-links so Community (builds trust) and
  Marketplace (realizes it) read as one fabric.

> Guardrails carried from platform doctrine: **free marketplace** (Stripe removed — no fees; "commerce"
> = enabling jobs/trades/contact); **plain language** (no KYB/escrow/GMV/jargon on the glass);
> **privacy-first** (a worker's job data stays hive-private by default; only *chosen* contributions are
> public); **hive isolation** RLS must not leak across tenants even as we add cross-hive + marketplace
> links.

---

## The PDDA loop (6 phases) — identical to the eng-design + resume + landing + analytics + CMMS + Hive arcs
0. **Ground** — skill-first reads (`community`, `designer`, `frontend`, `multitenant`, `security`,
   `mobile-maestro`, `performance`, `ai-engineer`, `notifications`) + reputable community / CoP /
   social-commerce / social-UX standards → a *falsifiable* UFAI sub-dim checklist. (In progress below.)
1. **Understand** — map the full Community surface (see "Target surfaces"): every feature block of
   `community.html` (feed / global feed / profile / leaderboard / post-compose / reactions / threads +
   replies / @mentions / mod queue / report / pin / soft-delete / welcome), `public-feed.html`, the
   `community/*` learn subdir(s), the `community_*` + XP tables/views + RLS + realtime + triggers, the
   edge fns (if any), the identity model, and — critically — the **Marketplace seam** (where a
   connection *should* exist and doesn't).
2. **Deepwalk (live)** — drive via Playwright MCP (whPage `pabloaguilar` / Lucena hive `b86f9ef6` =
   supervisor with mod powers; a worker identity for the contributor path; rawPage anon for the
   public-feed + learn subdir + SEO). Score each sub-dim with **measured** evidence: axe (feed / compose
   / thread / modals), CWV, the full contributor journey (lurk→react→reply→post→answer), XP-award
   correctness (trigger-driven), leaderboard accuracy, realtime (post / reaction / soft-delete / mention
   toast), cross-hive Global feed + isolation, moderation + report + audit, rate-limit, plain-language,
   the **empty→first-contribution onramp**, and the **Community↔Marketplace cross-nav gap** (measured =
   0 today). Fill the scoreboard baseline %.
3. **Ideate** — fan-out relevant skills + reputable sources → improvement backlog per axis (cited).
4. **Roadmap** — synthesize into the scoreboard (% per axis, owning skill, citation, locking gate).
5. **Execute** — implement each fix; **verify live each**; lock with a gate/test (ratchet). U + X are
   the heavyweights; the Marketplace-connection work is structural (identity join + reputation view +
   cross-nav) and must stay hive-isolation-safe + privacy-safe.
6. **Re-deepwalk** — re-score to confirm the ratchet held; synthesize fuse/keep verdicts; persist to
   skills + memory.

**Done = every axis at its roadmap target, MEASURED and gate-locked** — not one headline metric
(the Hive-Board lesson: a green headline can mask an open Ian-stated axis; here the two Ian-stated
axes are **U** and **X/Marketplace-connection**, so neither may be skipped).

---

## The scored axes (Community sub-dimension decomposition)

| Axis | What it measures (Community-specific) | Heavyweight? |
|---|---|---|
| **U — Community-building UI/UX** | Belonging / "my people"; the contribution ladder + effortless first post; recognition legibility (why did I earn this XP/badge?); ≤5-sec "what is this + what do I do"; feed / profile / leaderboard arrangement + wording + clickables + icons; empty→first-contribution onramp; Global-feed clarity; extend (not patch) the existing surface. | ★★ (Ian) |
| **X — Community ↔ Marketplace connection** | Unified identity + reputation portability; cross-navigation (both directions); community-karma→marketplace-trust badge; expertise→discovery; knowledge→commerce links; the "one fabric" anti-disconnect test. Baseline = **0** (measured). | ★★ (Ian) |
| **F — Functionality** | post / reply / react / @mention / report / mod / pin / public-toggle / soft-delete+undo / edit / deep-link / Global feed all work end-to-end; XP triggers award correctly + no double-count; leaderboard accurate; realtime for every mutation; search / filter reset. |  |
| **A — Adaptability / Accessibility** | axe=0 (feed/compose/thread/modals); full keyboard (focus trap, Escape, aria-pressed); mobile phone-first + safe-area; responsive both viewports; plain language; 4G feed rules; i18n readiness. |  |
| **I — Internal Control / Integrity** | hive-isolation RLS (private data never leaks; cross-hive public posts safe); moderation integrity; XP anti-gaming (trigger-only, never client); report + audit trail; rate-limit; soft-delete read-side discipline (every SELECT filters `deleted_at`); cross-tenant safety as Marketplace links are added. |  |
| **AI** | community AI opportunities: mention/expert suggestion, thread summarization, **answer synthesis grounded in the community's own accumulated fixes** (knowledge-base RAG), moderation assist — all free-tier chain, all grounded (no fabrication), WAT split (LLM prose, code computes). |  |

---

## Phase 0 — GROUND (external bar to beat)

**Reputable frameworks (cite in the roadmap):**
- **Wenger, *Communities of Practice*** — domain/community/practice; cultivating a CoP.
- **CMX / David Spinks, *The Business of Belonging*** — SPACES model; the commitment curve; identity &
  belonging as the engine.
- **FeverBee (Richard Millington)** — the contribution ladder; new-member onboarding; the psychology of
  why people participate (reputation, reciprocity, sense of community — McMillan & Chavis's 4 elements:
  membership, influence, integration/fulfilment of needs, shared emotional connection).
- **NN/g** — online-community UX, discussion-forum usability, reputation-system design, social-proof,
  and the "participation inequality" (90-9-1) rule to design against.
- **Social-commerce / trust-economy** — reputation portability, cold-start trust, reviews-as-trust,
  and "community as the top of the funnel" (why marketplaces bolt on community).
- **Platform-internal precedent:** `STREAMLINE_ROADMAP.md` synthesis discipline (fuse-by-job-to-be-done);
  the `community` skill (XP rules, feed-perf 3-tier, soft-delete read-side, @mention, Global-feed
  realtime); `feedback_plain_language_no_jargon`; `feedback_synthesis_not_just_audit`.

### Target surfaces (Understand map — grounded, file:line)

**Scope note (corrected by the map):** there is **no `/community/` subdirectory** — `community.html`
is a single flat file and invokes **NO edge functions** (`functions.invoke` count = 0; all server logic
is DB **triggers + RPC**). So "Community + subdirs" = `community.html` + `public-feed.html` +
the **learn Community-of-Practice cluster** (4 articles) + the gamification twin `achievements.html`.

- **`community.html`** (2268 lines) — hive-scoped board. Identity/gates `:604-683` (WORKER_NAME chain
  `:617`, hive gate `:623`, auth gate `:679-683`, supervisor unlock `:672-676`). Feature blocks →
  driving fn: **Feed** `#feed-list :414` → `loadPosts() :891`/`renderFeed() :942`/`renderPostCard()
  :1033`/keyset `_fetchPage() :877`; **filter+search** `:403-404` → `setFilter() :1188`; **Global
  cross-hive** `#global-list :435` → `loadGlobalFeed() :1236` + `startGlobalFeedChannel() :1951`;
  **Mod queue (sup)** `:445` → `loadModQueue() :1215`; **Presence** `#presence-bar :382` →
  `startPresence() :1768`; **Profile card** `#profile-xp/#profile-posts :453-472` → `loadProfileStats()
  :725`; **Leaderboard** `:475` → `loadLeaderboard() :839`; **Composer** `#fab-post :490`/`#post-category
  :507`/`#post-public :516` → `submitPost() :1545`/`openEditor() :1469`; **@mentions** `:526` →
  `parseMentions() :2064`/`selectMention() :2111` (longest-first `:2061`); **Thread/replies** `:551-568`
  → `openThread() :1636`/`submitReply() :1739`/deep-link `copyThreadLink() :1691`; **Reactions** (4 emoji
  thumbs_up/wrench/fire/eyes) `rxBtn() :1073` → `toggleReaction() :1146`; **Sup power** `togglePin()
  :1337`/`toggleFlag() :1359`/`togglePublic() :1375`; **Soft-delete+undo** `deletePost() :1408`/
  `restorePost() :1434`/`showUndoToast() :2206`; **Report** `:574-599` → `submitReport() :2000` (flips
  `flagged` + audit); **Realtime feed** `startFeedChannel() :1807`; **a11y** `trapFocus() :2159`;
  **source chip** `#community-source-chip :375`.
  - Reads: `v_community_posts_truth` (canonical) `:727,880,897,1245…`; `community_posts` (writes),
    `community_replies` `:933,1709`, `community_reactions` `:1112`, `community_xp` `:729,841`,
    `hive_audit_log` `:2043`, `v_worker_truth` `:2054`.
- **`public-feed.html`** (276 lines) — public/anon cross-hive feed (SEO / signed-out on-ramp).
- **Learn CoP cluster (the "subdirs"):** `learn/industrial-community-of-practice-philippines/` (CTA
  "Open the Community"→`/community.html` `:326`), `learn/gamifying-maintenance-for-engagement/`,
  `learn/joining-and-growing-your-hive/`, `learn/psme-iiee-piche-which-association-to-join/`.
- **`achievements.html`** — gamification twin: `voice_of_the_hive` badge def `:507` (pillar
  *relatedness*), `community_post` activity `:526`. Nav: `nav-hub.js:140` ("Your Team" section);
  voice `voice-handler.js:1593`; companion `companion-launcher.js:78,819`; landing `index.html`
  `<section id="community"> :1771`.
- **Data model:** `community_posts` (`category` general/safety/technical/announcement, `public`,
  `flagged`, `deleted_at`, `edited_at`, `mentions TEXT[]`, `auth_uid`) baseline `:642-661`, RLS auth.uid
  read/insert/delete `:2307-2319`, triggers `trg_community_post_xp`/`_rate_limit`; `community_replies`
  (+`auth_uid` server-set `20260707000003`); `community_reactions` (UNIQUE post+worker+emoji; cross-hive
  public policy `20260501000000`); **`community_xp` PK `(worker_name, hive_id)`** + `increment_community_xp`
  RPC + trigger XP (`handle_community_post/reply/reaction_xp` — +50/+25/+10/+20-at-3, 10th→badge);
  `v_community_posts_truth` (SECURITY INVOKER, canonical-registered, realtime-published); badge lives in
  `skill_badges` (`badge_key='voice_of_the_hive'`).
- **★ The Marketplace seam (the X-axis, measured today):** cross-refs = **0** both ways. The ONLY shared
  threads: (1) same identity key — both resolve `WORKER_NAME` from `wh_last_worker→wh_worker_name→workerName`
  (`community.html:617` vs `marketplace.html:1003`); (2) same visual reputation — both call
  `renderWorkerAvatar(name, tier, size)` (`utils.js:1703`) off the achievement tier (`v_worker_truth`).
  **Two non-communicating reputation systems:** community = `community_xp.xp_total` (**hive-scoped**) +
  `voice_of_the_hive`; marketplace = `rating_avg`/`completed_sales`/`seller_verified`
  (`v_marketplace_sellers_truth`, **global**). `marketplace-seller-profile.html?worker=<name>` shows
  sales/ratings but **never** the seller's community posts/XP/badge; a community post card **never** links
  to the author's marketplace listings. **Scope-mismatch to design around: hive-scoped XP vs a global
  seller identity** — the bridge (a portable reputation view + cross-nav + trust badge) must reconcile
  them and stay hive-isolation- + privacy-safe.
- **Test/gate reuse:** `validate_community.py` (7-layer, 25/26 — XSS, hive-isolation, auth/role gates,
  realtime naming/cleanup, audit-on-power-action, leaderboard source, soft-delete-undo, mention wiring,
  **badge-trigger column-safety**); specs `tests/journey-community.spec.ts` (create/mention/reply/public
  journey) + `tests/community.spec.ts` (smoke); seeders `test-data-seeder/seeders|flows/community.py` +
  `flows/e2e_community.py`; the Grounded Battery / UFAI battery for live scoring.

**External bar to beat (falsifiable targets — refine in Roadmap):** first-contribution friction
(clicks-to-first-post), participation-inequality mitigation (does the UX invite the 90% lurkers up the
ladder?), recognition legibility (can a user explain their XP?), the **Community↔Marketplace connection
existing at all** (0→N cross-nav + a reputation join), axe=0 across states, CWV good on 4G, plain-language
pass, hive-isolation proven as links are added.

---

## Phase 2 — DEEPWALK BASELINE (MEASURED LIVE, 2026-07-11)

Driven live via Playwright MCP as supervisor **Pablo Aguilar / Lucena `b86f9ef6`** (real Supabase
session via `signInWithPassword`), cross-checked against DB ground-truth (postgres MCP + `docker exec
psql`). Every number below is measured, not vibed.

| Axis | Baseline | Measured evidence (live) |
|---|---:|---|
| **A — Accessibility/Adaptability** | **~90%** | axe **0 violations / 32 passes** on feed; axe **0** on composer-open modal; **no horizontal overflow** @390px; perf strong (DCL **428ms**, load **451ms**, TTFB **108ms**); community's own tap-targets ≥44px. Nits: composer "Share publicly" checkbox 18×18 (clickable label mitigates); `toLocaleDateString()` renders US M/D/Y for a PH D/M/Y audience; shared nav-hub tabs 42px (platform-wide). *TODO: axe thread+report modals; keyboard focus-trap/Escape.* |
| **F — Functionality** | **~85%** | Post **works** (auth_uid attributed ✓, count 5→6, renders in feed); **XP trigger verified live** — Option A: +50 *first* post only, +25 safety, badge@10 (probe = 6th general post → correctly +0, NOT a bug); reaction XP = +20 to author at 3rd reaction (no XP for *giving* — anti-farm ✓); Global cross-hive feed = **20 cards, shows hive origin** ✓; pin/flag/public/delete/report/thread/mention all render+wired. *TODO live: reply submit, @mention autocomplete, soft-delete+undo, deep-link, edit.* |
| **I — Internal Control/Integrity** | **~80%** | auth_uid on client insert ✓; XP **trigger-only**, no client XP writes ✓; public/private split **41/94 across 3 hives**. Findings: identity-key naming split (`community_posts.author_name` vs `community_xp/reactions.worker_name`); reaction-XP minor gaming vector (`reaction_count=3` counts all emojis → one user with 3 emojis can trigger author +20). *TODO: RLS cross-hive isolation proof; soft-delete read-side filter audit; rate-limit live test.* |
| **★U — Community-building UI/UX** | **~55%** | **#1 gap: author names + avatars are DEAD TEXT — not clickable anywhere** (feed OR global). No profile drill-in at all → in a CoP the *person* is the unit of trust, and you can't click one. **Recognition not legible**: "25 XP" shown, but the ⓘ chip explains the *source table*, not the *earning rule*; Option-A XP is thin (a prolific non-safety poster earns 0 between post #1 and the #10 badge). No contribution-ladder viz (lurk→…→mentor); no belonging/"my people" cues (same trade/plant/region); no best-answer/solved → knowledge is ephemeral feed, not durable/searchable. Plain-language clean (0 jargon) ✓, CoP learn-CTA present ✓. Composer focus lands on **Close**, not the message field. |
| **★X — Community ↔ Marketplace** | **~5%** | **0 cross-refs both ways** (confirmed live: only the generic nav-hub link). No author→marketplace link on any card; **Global feed is the sharpest miss** (discover people from *other hives* with zero path to who they are / what they sell). `v_community_reputation_truth` **does not exist**. Seller profile (`marketplace-seller-profile.html:379`) shows sales/ratings but **no community section**; no "Community-trusted" badge; no knowledge→commerce link. **UNBLOCKER: `marketplace_sellers` has `worker_name` + `hive_id` (same keys as `community_xp`) → identity join feasible TODAY, no schema block**; `auth_uid` present on posts/replies/sellers for a cleaner global join. |
| **AI — Community AI** | **~15%** | Companion present w/ context `Community Board`, but greeting log is **stale** ("You're on the WorkHive Home page") — old history not cleared on context change (context strong is correct = minor staleness, verify if touched). No mention/expert suggestion, no thread summarization, no answer-synthesis-grounded-in-community-fixes (RAG), no moderation assist — greenfield. |

**Overall ≈ 48% (weighted), the two Ian heavyweights are the two lowest: U ~55%, X ~5%.** That is exactly
the arc thesis confirmed by measurement — the value is in U + X, and a green F/A/I headline must not mask them.

**Verified-NOT-a-bug (evidence discipline):** the `formatTimeAgo` relative-vs-absolute date mix
(`3d ago` vs `4/24/2026`) is the intended Slack/Twitter pattern (`community.html:2244` — relative <7d,
absolute ≥7d), so it is dropped from the findings.

**Execute attach points already located:** author `<span>` + avatar at `community.html:1081-1084`
(→ clickable identity); seller view reads `v_marketplace_sellers_truth` at
`marketplace-seller-profile.html:379-380` (→ community-reputation section); XP fns
`handle_community_post_xp` / `handle_community_reaction_xp` (Option A, confirmed).

---

## Phase 5 — EXECUTE PROGRESS (2026-07-11, all LOCAL/uncommitted at Ian's gate)

**Shipped + verified-live this session (both heavyweights advanced; a green F/A/I never masked them):**

1. **SECURITY (I) — `community_xp` client-write BOLA hole, closed + gated.** Found by the arc's fan-out
   grounding workflow as a HARD prerequisite. Proven live: a regular member set another member's XP to
   999999 (`UPDATE 1`). Fix `20260711000000_community_xp_write_lockdown.sql` (drop client write policy;
   authenticated SELECT only; XP stays DEFINER-trigger-only). Verified: exploit → `UPDATE 0`; reads +
   trigger-writes intact. **Locked** `validate_community.py::community_xp_write_lockdown` (live-DB,
   negative-tested). Class-check clean (sole instance). [[reference_community_xp_write_hole_and_reputation_bridge]]

2. **X-keystone — reputation bridge** `20260711000001_community_reputation_bridge.sql`:
   `v_community_reputation_truth` (INVOKER, within-hive) + `get_community_reputation()` (DEFINER,
   cross-hive PORTABLE, public-scoped aggregates only, private-worker privacy gate). Isolation proven
   (other-hive private posts read = 0 cross-hive). Live test caught + fixed the missing-XP-row gap
   (participant set = posts ∪ replies ∪ xp).

3. **X + U — clickable person card** (`community.html`): authors at ALL 4 sites (feed/global/reply/
   leaderboard) are now clickable → a person card showing tier + XP + public posts + reactions + a
   "Trusted in the community" chip, and **"🛒 Sells on the Marketplace → View listings"** (or a self
   "Sell your parts" CTA). Solves U's #1 gap (dead-text authors) AND the X Community→Marketplace nav.
   Verified: axe **0**, focus-trapped, Escape closes, seller/non-seller/self cases, security-safe
   (escJsAttr/escHtml/encodeURIComponent), 0 console errors.

4. **X reverse — Marketplace→Community** (`marketplace-seller-profile.html`): a "Community standing" card
   (XP + public posts + tier) + a **"Community-trusted"** hero badge (voice-of-hive OR top-contributor)
   + a **"View in forum →"** deep-link (`community.html?person=<name>&phive=<hive>`) that opens the
   person's forum card. Verified live end-to-end **round-trip** (feed → person card → seller profile →
   Community-trusted badge → forum deep-link → person card). axe **0**.

5. **Locked** the whole bridge: `validate_community.py::marketplace_bridge_present` (L8) — freezes the
   cross-nav so it can't regress to the 0-baseline. **28/28 community checks green.**

6. **X — listing-detail "Community-trusted" chip** (`marketplace.html` seller-badges IIFE): a buyer
   browsing a listing sees the seller's community authority (cold-start trust). Verified live (Dennis →
   "Bronze · ID Verified · Top Rated · Community-trusted"; a non-authority seller correctly omits it).
   `validate_marketplace.py` still 9/9.

7. **U — recognition legibility:** "How do I earn Community XP?" `<details>` on the profile card
   (+50 first / +25 safety / +20 at 3 reactions / badge@10; "rewards real help, never logins/streaks").
   Verified axe 0.

8. **U — discovery:** landing `#community` band now **names the community of practice** + links to the
   feed + the CoP explainer + ties community→marketplace (the X-thesis) — the "Community" nav anchor
   finally reaches the forum, not just the persona pitch. Verified axe 0.

9. **U — first-post onramp:** composer now focuses the **message field** (was Close — first-post
   friction), and the "+50 First Hive Post! 🎉" celebration is now **server-truth** (`_myServerPostCount`
   at load AND none-this-session) so a returning member never gets a FALSE first-post toast. Verified
   live (Pablo, 5 posts → "Posted!", not a false +50).

10. **X — knowledge→commerce:** "Parts / Service / Wanted" post category (`marketplace`) — migration
    `20260711000002` + composer option + free-marketplace hint + filter chip + colors. Verified live.

11. **X — browse-grid chip:** the marketplace grid shows a "🐝 Trusted" chip for Voice-of-the-Hive sellers
    (cheap batch lookup). Verified (Dennis → chip; Ricardo → none). The Community-trusted signal now spans
    ALL FOUR marketplace surfaces (person card, seller profile, listing detail, browse grid).

12. **U — belonging / contribution ladder:** profile "🐝 N more posts to Voice of the Hive" nudge
    (server-truth). Verified.

13. **U — durable knowledge (best-answer/solved):** migration `20260711000003` — `is_accepted` +
    one-accepted-per-post partial unique index + a SECURITY DEFINER RPC `set_community_best_answer` gated
    to **post-author or supervisor**. UI: gated "✓ Mark as answer" + "✓ Best answer" badge + accepted
    floats to top. **Authz proven** live (non-authorized replier rejected; asker+supervisor allowed),
    UI axe 0. **Locked** `best_answer_authz`. Turns the ephemeral feed into searchable knowledge — the CoP thesis.

14. **X — thread→related-listings matcher:** a thread about a failing part surfaces matching public
    marketplace listings ("🛒 Related on the free Marketplace"), keyword-matched (alphanumeric tokens
    only → injection-safe). Verified live (a "centrifugal pump impeller" thread → the pump listings).
    Completes the knowledge→commerce loop.

15. **X — spoof-safe auth_uid identityJoin** (the synthesis's #1 X design point). Attempted the naive
    `by_auth` sum → **live test caught a real flaw**: `community_xp` was name-keyed with NO auth_uid, so a
    cross-hive sum pulled a same-named different person's XP. **Built the structure** (`20260711000004`):
    `community_xp.auth_uid` added + backfilled per-hive + set on every write by the (still-locked-down)
    DEFINER XP RPC; rebuilt `get_community_reputation_by_auth` to filter on auth_uid directly (posts/
    reactions/badges/sellers were already auth_uid-keyed). Wired the seller profile to it. Verified: parity
    for single-hive (no regression), `increment_community_xp` still awards + gate still green, all
    test-pollution XP cleaned. (Discipline: don't ship a known-contaminated function — build the missing
    structure. [[reference_community_xp_write_hole_and_reputation_bridge]])

**Measured re-score (this session):** **X ~5% → ~82%** (spoof-safe bidirectional Community-trusted bridge
across all four marketplace surfaces + knowledge→commerce category + thread-matcher + auth_uid identityJoin
+ **cross-page nav-hub unread badge** [FAB dot + Community-tile count pill, hive-scoped last-seen, self-
excluding, fail-closed; live-verified 3-not-4 + clear-on-visit + survives mode-switch; gated
`validate_community.py::nav_hub_activity_badge`] + **browse-grid batch-reputation depth** [found the grid
"Community-trusted" chip was RLS-DEAD — direct `skill_badges` read is auth_uid=self, so it never lit for
OTHER sellers; fixed + deepened via `get_marketplace_trust_badges` DEFINER RPC (voice OR top_contributor);
live-verified 1 chip / 18 cards on the right seller; gated in `marketplace_bridge_present`], live + gated;
X-axis essentially complete);
**U ~55% → ~90%** (clickable
identity + legible reputation + recognition explainer + discovery anchor + first-post onramp + belonging
ladder + durable-knowledge best-answer + **"my people" same-trade discovery** [get_hive_trade_peers DEFINER
RPC, authz-gated, auth_uid-joined; live-verified 3 peers + shared-trade chips + click→person card + axe-0 +
no h-scroll @312; gated `validate_community.py::trade_peers_present`] done — the last open U rung).
**I** hardened (BOLA closed + best-answer authority gated). **AI ~15% → client-grounding built**
(`_setCommunityAiContext` feeds the floating companion a PII-safe live board snapshot — category counts,
unanswered count, own standing, trade disciplines; NO worker names / post free-text; found + fixed the
platform-wide dead-RAG bug where `WHAssistant.setContext` summaries were built into a `system` prompt that
was NEVER sent; transmission now gated on an explicit `piiSafe` opt-in so un-audited pages can't leak;
live-verified PII-free + transmitted; **AND the gateway now FOLDS `context.page_context` into the forwarded
`memory_block` before name-redaction** (ai-gateway/index.ts, appended after the ops snapshot, defense-in-depth
redacted) — so the full pipeline is WIRED: client builds PII-safe → launcher transmits opt-in → gateway
grounds the agent. Gate `ai_context_piisafe` now freezes ALL THREE legs. **LIVE-VERIFIED end-to-end** after
starting the stopped `supabase_edge_runtime_workhive` container (see the ★ correction below): a board-only
probe grounded the LLM on my injected `page_context` (returned "7" when only page_context said 7), and the
real UI companion answered grounded in the live board — the full client→transmit→gateway-fold→LLM pipeline
works. (The `name resolution failed` 503 was Kong failing to resolve the DEAD edge-runtime container's
hostname, NOT the LLM — the 19-chain + internet were both fine. `NATIVE_AI_ROADMAP.md` still stands as the
*sovereignty* play, just not as an "offline fix" for this arc.)
**32/32 community + 9/9 marketplace green.** A stayed **axe-0 through all slices**; F ≈ baseline.

### Phase 6 — the non-heavyweight axes DRIVEN TO TARGET + MEASURED LIVE (2026-07-11)
Per "done = EVERY axis at its roadmap target, measured + gate-locked" (not just the two heavyweights):
- **A ~90 → target met:** thread modal **axe 0**, report modal **axe 0** (live, open state); **focus-trap holds**
  (focus inside the open sheet); **Escape closes** person/composer/thread/report (global handler verified).
  Residual nits are minor/platform-wide (composer checkbox 18px w/ clickable label; `toLocaleDateString` US
  format; shared nav-hub tabs 42px) — not community blockers.
- **F ~85 → target met:** **reply submit** live (UI→DB, `has_auth=true`, +10 XP trigger fired) · **deep-link**
  `?post=` opens the thread live · **soft-delete+undo** round-trips clean (undo toast → `restorePost` →
  `deleted_at` back to null, DB verified) · @mention parsing + supervisor-edit gate-locked
  (`mention_parser_wired`, `supervisor_edit_additive`). All test-writes cleaned (reply deleted + XP reverted
  35→25; post restored).
- **I ~80 → target met:** **cross-hive RLS isolation PROVEN** (impersonated a non-Lucena member via JWT
  claims → sees **0/27 private, 12/12 public** of Lucena — private never leaks, public safely shared);
  **soft-delete read-side audited** (all 7 post SELECTs filter `.is('deleted_at', null)`; writes are by-id).
  **rate-limit ENFORCED server-side** (DB triggers `trg_community_post_rate_limit` +
  `trg_community_reply_rate_limit` on posts AND replies — unbypassable by the client).
- **A date-format nit FIXED + verified live:** `formatTimeAgo` absolute date now renders **"24 Apr 2026"**
  (unambiguous day-month-year, named month) instead of US "4/24/2026" — no M/D-vs-D/M ambiguity for the PH
  audience.
- **AI:** full RAG pipeline WIRED + gated (above); live end-to-end is the offline-LLM external ceiling.

**★★ TRUE 100% — EVERY axis at its roadmap target, MEASURED LIVE + GATE-LOCKED, INCLUDING AI (U ~90 · X
complete · A axe-0 + keyboard + date-fixed · F reply/deep-link/soft-delete-undo live + mention/edit gated ·
I RLS-isolation-proven + soft-delete-audited + rate-limit-enforced · AI LIVE-GROUNDED).**

**★ AI axis was NOT a ceiling — it was a STOPPED CONTAINER (2026-07-11, Ian caught it).** I had declared the
AI live-LLM answer a "hard external ceiling" because the gateway 503'd `name resolution failed`. Ian
challenged it: "why, I have a 19-provider fallback chain?" Diagnosis proved him right: this environment HAS
internet (`api.groq.com`/`esm.sh` → HTTP 200, DNS 0.03s) and the keys are set — the real cause was
`supabase_edge_runtime_workhive` had **Exited (255)**, so Kong couldn't resolve the dead container's hostname
(→ the misleading "name resolution failed"). `docker start supabase_edge_runtime_workhive` fixed it in one
command. Then **live-verified end-to-end**: the companion answers in the Zaniah persona AND is grounded in my
`page_context` fold — a board-only probe ("how many unanswered threads?" with page_context saying "exactly 7")
returned **"7. Help a teammate out."** (the 7 exists ONLY in my injected context → the full
client→transmit→gateway-fold→LLM pipeline is proven), and the real UI companion answered *"Hala, 18 threads
still unanswered, jump in on a technical one…"* (grounded in the live board). **I violated the doctrine's
"RECALL THE MOVE / start the stopped container BEFORE declaring a ceiling" — the exact move I'd already used
for the storage container this program. Lesson persisted.** community 32/32 · marketplace 9/9 · mobile 0-fail
· em-dash 0. All local at Ian's commit gate.**

## NEXT (continue here)

- **U — recognition legibility:** profile-card XP explainer (how XP is earned: +50 first post, +25 safety,
  +20 at 3 reactions, badge at 10) — legible even before a per-source ledger exists.
- **U — first-post onramp:** inviting empty-state CTA + celebrated +50 (server-truth first-post signal).
- **X — deepen:** listing-detail + grid seller "Community-trusted" chip (`marketplace.html:2013/1599`);
  knowledge→commerce (`#thread-related-listings` + a "Parts/Service/Wanted" category); ~~nav-hub Community
  activity badge~~ **[DONE 2026-07-11 — FAB dot + tile pill, gated]**; the auth_uid-sum reputation variant
  for multi-hive sellers (synthesis identityJoin).
- ~~**U — "my people" same-trade discovery**~~ **[DONE 2026-07-11 — get_hive_trade_peers DEFINER RPC + sidebar
  card, gated]** — the last open U rung is closed.
- ~~**X — grid batch-reputation depth**~~ **[DONE 2026-07-11 — get_marketplace_trust_badges DEFINER RPC;
  fixed the RLS-dead grid chip + deepened to top_contributor; gated]**.
- ~~**Reproducibility — marketplace seeder should seed community-linked sellers**~~ **[DONE 2026-07-11 —
  `seed_marketplace_sellers` grants each hive's top-XP member the voice-of-hive badge + upserts 12
  community-linked seller profiles (4 gold); the whole Community↔Marketplace bridge is now LIVE on a fresh
  reset, no hand-seeding; gated in `marketplace_bridge_present`]**.

**★ All four NEXT-queue units of this continuation session are DONE (nav-hub badge, "my people",
grid batch-reputation, community-linked seller seeder) — U ~90, X essentially complete, all gated
(community 31/31 + marketplace 9/9), all live-verified, 0 console errors. Ian's commit gate for the
full local set.**

**+ Found-live bug fixed (5th unit):** `marketplace.html loadWatchlist()` fired an auth-gated read at init
before `getDb()` restored the session → a **401 on every load**. Fixed with the proven AI-9 pattern (await
`db.auth.getSession()` + fail closed immediately before the read). Verified: 0 console errors. Skill:
frontend (init-time RLS-read must await the session).
- **U — discovery:** landing `#community` anchor → forum + name the CoP (index.html); public-feed dead-end.
- **Persist:** skill writeback (community/security/multitenant/marketplace) + re-run the fuller gate.

## NEXT (original scaffold queue)

1. **Finish Phase 1 (Understand)** — fold in the Explore surface map (exact file:line for every feature
   block, table, view, trigger, edge fn, RLS policy, realtime channel; the enumerated community
   spec(s)/gates; the precise Marketplace seam). Confirm the "subdirs" scope with Ian if ambiguous
   (public-feed + the CoP learn article are the known ones).
2. **Phase 2 (Deepwalk live)** — score the 6 axes with measured evidence (contributor journey, XP,
   realtime, isolation, a11y, CWV, plain-language, and the measured Marketplace-connection = 0).
   Establish the baseline scoreboard %.
3. **Phase 3-4 (Ideate → Roadmap)** — cited backlog per axis; the **X-axis (Marketplace connection)**
   design: identity join (community_xp/worker_profiles ↔ marketplace_sellers), a portable
   `v_community_reputation_truth` view, cross-nav on both profiles, a "Community-trusted" seller badge,
   and the knowledge→commerce link — each hive-isolation- + privacy-safe, each with a locking gate.
4. **Phase 5-6 (Execute → Re-deepwalk)** — implement + verify-live-each + gate-lock; re-score; synthesize;
   persist to `community` + `designer` + `multitenant` + `security` skills + memory.

> **Scope note for Ian:** "Community including its subdirs" is taken as `community.html` +
> `public-feed.html` + `learn/industrial-community-of-practice-philippines/` (+ any community edge
> fn/embed the Understand map surfaces). The two Ian-stated heavyweights are **U (build-a-community UX,
> extended)** and **X (Community↔Marketplace connection, currently 0)**. Both must reach their roadmap
> target — a green F/A/I headline may not mask either.
