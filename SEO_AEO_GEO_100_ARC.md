# SEO · AEO · GEO — The Drive-to-Measured-100% Arc

**Created:** 2026-06-29 · **Owner:** Ian Beronio · **Status:** DRAFT laid out for alignment (lay-it-out-first; build not started).
**Method:** WorkHive skills (`seo-content`, `ai-engineer`) + reputable 2026 sources (Google Search Central, Ahrefs 75K-brand & 1.9M-citation studies, Princeton/SIGKDD GEO paper, Search Engine Land/Journal, web.dev CWV) + own synthesis. Builds on `SEO_AEO_GEO_ROADMAP.md` (the 2026-05 launch playbook, Phases 0-2 shipped) and the **content-grounding system** (2026-06, the measurement substrate).

---

## The reframe (why this arc exists)

`SEO_AEO_GEO_ROADMAP.md` was a *launch playbook* ("do these phases"). This arc applies the platform's signature pattern to all three axes: **a measured, gated 100% scoreboard per axis**, the same shape as the UFAI / live-% arcs. The content-grounding gates I just built (`surface_render_drift`, `llms_article_completeness`, `schema_featurelist`, `count_drift`, `capability_drift`) are the **measurement substrate** — they keep the outward facts true; this arc adds the gates that measure *retrievability, extractability, and citation*.

### Current MEASURED state (from the 2026-06-29 audit)
| Axis | Now | What's done | What's open |
|---|---|---|---|
| **SEO** | **~90%** | titles/meta/OG/Twitter/canonical on all pages; SoftwareApplication+Organization+WebSite JSON-LD; sitemap 43 URLs; robots allows AI crawlers; 38 articles w/ schema+dateModified; entity (areaServed/knowsAbout/legalName/DTI) | `sameAs` empty; no LocalBusiness; OG image is a bare logo; **Core Web Vitals never measured**; GA4/Bing not wired; backlinks/authority nascent |
| **AEO** | **~75%** | answer-first hero + article TL;DRs; Q&A content on all 38; internal linking via catalog | **0 AI-citation audits ever logged**; FAQ/HowTo *rich results are now dead* (see reframe #2); no Person/author E-E-A-T; no per-page extractability gate |
| **GEO** | **~30%** | llms.txt; AI crawlers allowed; entity signals; every article cites ≥1 standard | **ZERO off-site authority** (no Reddit/YouTube/Wikipedia/Wikidata/LinkedIn/press); no SOV measurement; sameAs empty |

---

## Three 2026 findings that UPDATE the old roadmap (evidence-cited)

1. **llms.txt is NOT a citation lever — demote it to hygiene.** Google's Mueller calls it speculative (≈ the dead keywords meta tag); an Ahrefs scan of 137,000 sites found **97% got zero traffic** (May 2026); OpenAI/Anthropic/Perplexity don't fetch it as a citation signal. → Keep our `llms_article_completeness` gate (it's near-free hygiene) but **stop treating llms.txt as a GEO win**; spend the hours on mentions/content/CWV. (SEJ, Ahrefs, Search Engine Land)

2. **FAQ rich results were DEPRECATED May 7 2026; HowTo went in 2023 — the SCHEMA is no longer the lever.** Ahrefs' controlled test found schema produced **~0 lift**. → Keep the **Q&A CONTENT** (it's what gets extracted) but stop chasing FAQ/HowTo *markup* as the citation driver; keep Organization/Article/SoftwareApplication/Breadcrumb for entity clarity. (Search Engine Journal, Google Search Central)

3. **For AI visibility, brand MENTIONS beat backlinks ~3x, and YouTube+Reddit dominate citations — GEO is ~80% off-site.** Ahrefs 75K-brand study: branded web mentions correlate **0.664** with AI visibility vs **0.218** for backlinks; **YouTube mentions are the single strongest correlate (~0.74)**; **Reddit is the #1 cited domain (~40% of citations)**; ~85% of brand mentions in AI answers come from third-party pages. → The biggest GEO gains are *earned off-site*, not coded. (Ahrefs, TechEdgeAI citation index)

**The one on-page GEO lever we FULLY control + can gate:** the **Princeton/SIGKDD GEO triad** — *add statistics (+~40%), cite authoritative sources (+~40%), add expert quotations (+~28%)* per passage. This is repeatable, evidence-backed, and exactly the kind of thing our content gates already enforce. (arxiv 2311.09735)

**The PH first-mover prize (why this is worth driving):** AI Overviews fire on ~29% of PH keywords; ~30M Filipino ChatGPT users; **near-zero competition for niche industrial terms**; AI-referred visitors convert **10-24x** better than organic. "Free + Taglish + niche industrial maintenance" is uncontested citation territory.

---

## How we define a MEASURED 100% — the two-layer model

Each axis splits into what we can BUILD vs what we must EARN:

- **Layer A — Buildable substrate (code, 100% ours): drive to a gated 100% NOW.** Every code-controllable lever shipped + ratcheted into the gate. This is the half I can take to 100% locally.
- **Layer B — Earned outcome (AI Share-of-Voice on a fixed prompt set): compounds over 2-12 weeks via off-site execution (Ian-gated).** Measured by a harness, not built. "Earned 100%" = #1/tied citation share on the target prompts.

This mirrors the platform's existing `verified-100%` vs `live-100%` distinction. The honest target: **drive Layer A to 100% (code) and stand up the Layer-B scoreboard, so the off-site work has a measured curve to climb.**

---

## The per-axis scoreboard (each cell named with the gate that measures it)

### SEO — 100% = all hard gates green AND weighted ≥95
| Cell (weight) | Measured by | State |
|---|---|---|
| Crawl/index 25% — every canonical 200 + in sitemap + indexed + ≤3 clicks + 0 orphans | existing sitemap validators **+ NEW orphan/click-depth check** | ~90% |
| Core Web Vitals 20% — LCP<2.5s / INP<200ms / CLS<0.1 @75th-pct **mobile** | **NEW `cwv` gate** (Lighthouse budget on public surfaces) | 0% (unmeasured) |
| On-page 20% — unique title/meta, 1 H1, alt text, named author+dates | existing + **NEW alt-text + Person/author check** | ~85% |
| Structured data 10% — valid JSON-LD, 0 Rich-Results errors, retired types pruned | **NEW schema-validity gate** | partial |
| Authority/trust 15% — referring domains + branded mentions + HTTPS + GBP/NAP | **Layer B** (off-site) | low |
| AI/GEO visibility 10% — SOV on prompt set | **Layer B harness** | 0% |

### AEO — 100% = per-page extractability 100% (Layer A) AND ≥70% top-cited/first-mention on the prompt set (Layer B)
| Cell | Measured by | State |
|---|---|---|
| Extractability 40% (ALL ours) — answer-first 40-60w under a question H2/H3; one-idea-per-chunk; ≥1 stat + ≥1 cited source per section; crawlable text; AI crawlers allowed; CWV pass | **NEW `aeo_extractability` gate** (per article) | partial (answer-first exists) |
| AI Share-of-Voice 60% — citation/mention/recommendation/sentiment across 5 engines | **Layer B harness** | 0% (never logged) |

### GEO — 100% = Princeton-triad gate 100% (Layer A) AND #1/tied SOV + ≥70% presence on Perplexity+AI-Overviews (Layer B)
| Cell | Measured by | State |
|---|---|---|
| On-page triad 20% (ours) — stat + quote + cited source + answer-first TL;DR + comparison table per article/calc page | **NEW `geo_extractability` gate** | low |
| Entity 〃 — sameAs + Organization schema + Wikidata item, consistent NAP | code (needs profile URLs) **+ Ian** (create profiles) | partial |
| Off-site authority 80% — Reddit, **YouTube**, Wikipedia, digital-PR mentions, press | **Layer B** (Ian; slow-compounding) | 0% |
| Measurement — SOV harness | **NEW `geo_sov` harness** | 0% |

---

## Phase roadmap — measured % per phase (Ian approved forks 1+2+3, 2026-06-30)

Baseline uses the FULL weighted scorecard (not on-page-only), so CWV + authority + AI-SOV (all ~0 today) count against it — the honest path to 100%.

| Phase | Ships | Layer/Owner | Locks (gate) | SEO | AEO | GEO |
|---|---|---|---|---|---|---|
| Baseline (today) | on-page shipped + content-grounding substrate | — | content gate (12) | 48% | 16% | 6% |
| **P1 — Scoreboard + SEO technical gate** | SOV harness (bilingual 30-50 prompts × 5 engines) + CWV/JSON-LD-validity/orphan-depth/alt/one-H1 gate | A — me | `seo_technical` + `geo_sov` | 72% | 24% | 12% |
| **P2 — On-page extractability** | Princeton triad (answer-first + stat + cited source + comparison table) on 38 articles + calc pages; prune dead FAQ/HowTo schema; Person E-E-A-T; Taglish | A — me | `aeo_extractability` + `geo_extractability` | 84% | 56% | 30% |
| **P3 — CWV green + entity** | LCP<2.5/INP<200/CLS<0.1 mobile; sameAs + Organization wired; Wikidata drafted | A — me | `cwv` green | 95% | 60% | 35% |
| **▶ Layer-A ceiling (all code-controllable done)** | — | — | all A-gates green | **95%** | **60%** | **35%** |
| **P4 — Off-site kickoff** | YouTube how-tos (grounded flagship pipeline) + Reddit + PH digital-PR + GBP | B — Ian | SOV harness tracks | 97% | 80% | 68% |
| **P5 — Compounding loop (8-12 wks)** | weekly SOV audit + ≤90-day refresh + Wikipedia/Wikidata + mentions accrue | B — Ian | SOV ≥ target | 100% | 100% | 100% |

**Layer-A ceiling = SEO 95 / AEO 60 / GEO 35** (what I can drive in code). The rest is earned off-site (P4-P5, Ian) and measured by the SOV harness. Fork 3 approved: the grounded flagship video pipeline is the YouTube engine for P4.

### BUILD STATUS — the measurement substrate is COMPLETE (2026-06-30)
All pure-code, no-Ian-input Layer-A infrastructure is built + verified + registered:
- **`tools/seo_technical_gate.py`** (P1) — one-H1 / img-alt / JSON-LD-validity / no-new-retired-schema; **catalog-derived** surfaces (killed validate_seo.py's stale 28-vs-38 hand-list). Self-test 6/6, registered (`seo-technical`), PASS. Live: 3 checks clean, retired_schema=49 baselined.
- **`tools/geo_sov_audit.py`** (G1) — the AEO/GEO Share-of-Voice board. `prompt_audit_queries.json` expanded to **37 bilingual queries (10 Taglish)** + `--template`/`--score`/`--self-test` + per-engine SOV/citation/recommendation/sentiment + forward-only ratchet. Self-test 7/7. (Measurement runs are Layer B — needs live answer-engines.)
- **`tools/extractability_gate.py`** (P2 gate) — Princeton triad: answer-first opener + ≥1 statistic + ≥1 cited source per article; catalog-derived, ratcheted. Self-test 5/5, registered (`extractability`), PASS. **Live result: all 38 articles already have stats + citations; exactly 6 lack a crisp answer-first opener** (baselined; the precise P2 retrofit list).

**Remaining work needs Ian's input/content (not pure code):**
- **P2 retrofit (content, his voice):** add answer-first openers to the 6 flagged articles + comparison tables (WorkHive-free vs paid CMMS).
- **P3 entity:** `sameAs` URLs (his LinkedIn/Crunchbase/etc.) + Person/author credentials (his name/bio) + a Wikidata item.
- **P3 CWV gate:** needs Lighthouse (npm/env) to measure LCP/INP/CLS on mobile.
- **Layer B (P4/P5):** off-site — YouTube/Reddit/Wikipedia/PR/GBP + the manual SOV runs.

## The arc — phase detail (Layer A = I build now; Layer B = Ian-gated/off-site)

- **G1 — Stand up the scoreboard (build FIRST; it defines 100%).**
  - **SOV harness** (`tools/geo_sov_audit.py`, reuse the AI chain + extend `prompt_audit.py`'s 23 queries → a **bilingual 30-50 prompt set** in English + Taglish): run across ChatGPT/Perplexity/Gemini/AI-Overviews/Claude, log citation+mention+recommendation+sentiment+source-mix to a baseline JSON, gate regressions. → the measured AEO+GEO outcome board.
  - **SEO technical gate** folded into `run_platform_checks` (like the content gate): CWV budget + JSON-LD validity + orphan/click-depth + alt-text + one-H1 on every public surface.
- **A1 — On-page levers we fully control (drive Layer A → 100%, all gated, ratcheted).**
  - **Princeton-triad gate** (`geo/aeo_extractability`): every /learn article + calc page gets an answer-first 40-60w TL;DR under a question heading + ≥1 cited statistic + ≥1 authoritative quote/source + (where apt) a comparison table (WorkHive-free vs paid CMMS). Retrofit the 38 articles.
  - **Prune dead schema reliance** (FAQ/HowTo rich results) — keep Q&A as body content; keep Organization/Article/SoftwareApplication/Breadcrumb.
  - **Person/author E-E-A-T schema** (founder + editorial credentials — needs Ian's name/credentials).
  - **Taglish keyword coverage**: bilingual question headings + local phrasings per tool ("libreng CMMS", "paano mag-compute ng MTBF").
  - **CWV mobile hardening** on index.html + /learn (perf skill) until the `cwv` gate is green.
  - **Entity wiring**: fill `sameAs` + Organization once profile URLs exist; prep the Wikidata item.
- **B1 — Off-site authority (Layer B, Ian-gated, compounds 2-12 weeks).**
  - Reddit authentic participation (r/maintenance, r/PLC, r/Philippines…); **YouTube how-to demos** (strongest correlate — the now-grounded flagship video pipeline feeds this); Wikipedia citations; digital-PR to PH outlets (PSME/IIEE, Rappler/PhilStar Tech); GBP + PH directories (needs DTI address); GA4 + Bing wiring (needs IDs).
  - I PREP the assets (comparison tables, citable stats, video scripts via the grounded pipeline, the press one-pager); Ian executes the outward posting.

---

## Bottom line — what I can drive to 100% vs what compounds

- **Layer A (code, mine → gated 100% now):** the SOV harness + SEO technical gate + the Princeton-triad extractability gate + article retrofit + CWV + schema prune + sameAs/Person wiring. This takes the *buildable substrate* of all three axes to a measured 100% and turns SEO/AEO/GEO from vibes into ratcheted % — exactly like every other platform arc.
- **Layer B (Ian/off-site/time → measured by the harness):** brand mentions, YouTube, Reddit, Wikidata/Wikipedia, GBP, GA4/Bing IDs, press. The research is unambiguous that this is where 2 of the 3 axes are actually *won* — but it's earned, not coded, and it compounds over weeks once the substrate + scoreboard exist.

> Companion docs: `SEO_AEO_GEO_ROADMAP.md` (launch playbook), `SEO_PHASE_3_OFFSITE_AUTHORITY.md`, `SEO_PHASE_5_MEASUREMENT.md`, `SEO_PHASE_6_LOCAL_PH.md`, `CONTENT_GROUNDING_GATE.md` (the substrate).

---

# 2026-06-30 EXTENSION — Layer A was measuring the ARTICLES, not the LANDING PAGE itself

**Why this extension exists (Ian, 2026-06-30):** *"it's a bit shallow — you don't flag any contents and links of my entire landing pages, the inventory of my popout card, all written content on the browser landing page."* He's right. The arc's three gates (`seo_technical`, `extractability`, `geo_sov`) are **catalog-/article-derived** — they trust the canonical catalog says "28 tools exist" and they grade the 38 `/learn` articles. **None of them parse the rendered DOM of `index.html`,** the one page that actually faces search + AI. So the arc had a blind spot exactly where it matters most.

This extension was built skills-first (`seo-content`, `designer`, `frontend`, `ai-engineer`, `community`, `marketplace`, `mobile-maestro`) + reputable 2026 primary sources (Google Search Central, Vercel/MERJ 500M-fetch study, GSQI empirical test, Next.js, MDN, Ahrefs Knowledge-Graph) — full content+link inventory, adversarially-verified research, own synthesis.

## Why the landing page is the WHOLE game for this arc

`index.html` is the **only `index,follow` surface** — every app page is correctly `noindex`, and the sitemap lists only the homepage + the 38 articles. So **the entire crawl path to every tool page, and the single richest product description on the property, lives or dies on `index.html`'s crawlable HTML.** Locking its best content in JavaScript is therefore the *most* expensive place on the whole platform to do it.

## What the landing page actually contains (the inventory)

**Static, crawlable, and already STRONG (don't touch — this is the arc working):**
- Answer-first `<h2>What is WorkHive?</h2>` + a 60-word definition paragraph (AEO gold, in the DOM).
- **15 visible `<details>` FAQ** Q&A, **verbatim-mirrored** by a `FAQPage` JSON-LD block — textbook AEO alignment.
- `@graph` JSON-LD: `Organization` (legalName, DTI 8080496, founder, contactPoint, areaServed=PH, 18-item `knowsAbout`), `WebSite`, `SoftwareApplication` (Offer price 0 PHP), `FAQPage`.
- Problem cards, transformation cards, before/after impact stat tiles, audience cards, 3 learn-teasers with descriptive `/learn/` anchors, footer tool links — all static.
- `<title>`, meta description, canonical, full OG/Twitter, manifest — all present.

**The "popout card" you named = the hero "Find your hive's stage" card.** Its 4 stage cards (`onclick="openStagePopup(n)"`) and **"See All Tools"** (`onclick="openAllToolsPopup()"`) render from a JS `stageData` object (`index.html:2306-2378`) via `grid.innerHTML` (line 2395). The card's *shells* (stage names, taglines, Now/Next criteria) are static; the **deep content is JS-only.**

## The findings — clustered by job-to-be-done, with verdicts

**L1 · THE BIG ONE — the tool catalog (31 popup entries across 27 distinct pages) + its internal tool links are JS-locked, invisible to crawlers AND AI engines.** *(Measured: 31 `stageData` tool entries — I'd earlier said "28"; the gate counted the real 31.)*
Every tool's rich, standards-anchored description (Hive Live Board, Digital Logbook, PM Scheduler … Engineering Design Calculator "51 calc types … PEC + ASHRAE + ISA + NFPA + IEC + PSME", Reliability Workbench "FMEA AIAG-VDA + RCM SAE JA1011 + Weibull MLE + P-F interval", Marketplace) exists ONLY inside `stageData` and is injected via `innerHTML` **on click**. This is the single most detailed, most citable product copy on the property — and it is **absent from the crawlable DOM**.
→ **Evidence is one-directional (see §Evidence): AI crawlers don't run JS at all; Googlebot runs JS but never fires the click — so this content reaches neither.** This is the same WorkHive failure class already solved twice (runtime-wiped `<h1>`; the 24-vs-38 guide-count drift).
→ **VERDICT: render the catalog into static HTML from the canonical source (the fix WorkHive already has a pattern for).** Highest priority in this extension.

**L2 · Most tool pages have NO crawlable link from the landing page; the hero "free tools" pass no equity.** The hero's four "free tools" links (Logbook / PM Scheduler / Eng. Calculators / AI Assistant) are **auth-triggers** — `href="#join"` + `onclick="openSignUp()"` — they pass zero equity to the actual tool pages. **Measured by the new gate (script-stripped DOM): 16 of 25 catalog tool pages have ZERO crawlable `<a href>` from `index.html`** — including marketplace, predictive, asset-hub, project-manager, resume, community, achievements, alert-hub, shift-brain, integrations, ph-intelligence, dayplanner, audit-log, ai-quality, analytics-report, project-report. The 9 that ARE linked (logbook, pm-scheduler, inventory, skillmatrix, engineering-design, assistant, analytics, voice-journal, hive) reach the crawler via the footer + the `display:none` `#ops-home` block.
→ **Measurement correction (why the gate matters):** the inventory pass first flagged analytics/voice-journal/hive as "no crawlable link" — but the research confirms **in-DOM `display:none` content IS crawlable**, so those three *do* have a crawlable anchor via `#ops-home`. The gate measures the truth; the heuristic over-counted. The real zero-link set is the 16 above.
→ **VERDICT: every active catalog tool page must have ≥1 real `<a href>` from `index.html`'s static DOM.** Folds into the L1 catalog render.

**L3 · The `<h1>` is keyword-dead.** The hero `<h1>` is "Access Your Memory" — brand-poetic, zero target keyword. The strong terms ("free industrial tools," "Filipino worker," "maintenance," "Philippines") live in the `<p>` subhead, not the H1.
→ **VERDICT: make the H1 keyword-bearing; demote "Access Your Memory" to an eyebrow/tagline.** (Ian's voice — content edit.)

**L4 · `sameAs: []` is empty.** The `Organization` schema has no social/Wikidata/Crunchbase/LinkedIn links — the exact entity-disambiguation signal Google's Knowledge Graph (which powers AI Overviews / Gemini) leans on. Already flagged in the P3 entity row; restated here because it's a landing-page-DOM fact.
→ **VERDICT: populate `sameAs` (Ian-gated — needs his profile URLs).** Same as P3.

**L5 · The tool list has TWO drifting JS sources of truth.** The catalog lives in both `index.html` `stageData` AND `nav-hub.js` `TOOLS` — both JS arrays, neither static HTML. (Frontend skill: new-page registration already touches 5 points.) A static render must derive from ONE canonical source so it can't drift.
→ **VERDICT: catalog-derive the static render from `platform_catalog`, not from either JS array.**

**L6 · Count-claim drift risk.** "38 guides" is hard-typed in two static spots (teaser + footer), markered but fragile; there is no "N tools" claim yet. Any static catalog render should carry a catalog-derived count + a count-claim guard tolerant of adjectives ("28 **free** tools") — the exact regex hole that let "24 **in-depth** guides" drift.
→ **VERDICT: fold count assertions into the new gate.**

**L7 · Minor: SVG icon a11y.** Decorative inline `<svg>` glyphs (industry chips, gap dots) carry no `aria-label`/`<title>`; meaning is conveyed only by adjacent text. Fine for crawlers, thin for assistive tech. (Low priority; mobile-maestro/QA.)

**Deliberately NOT a finding:** the `display:none` `#ops-home` signed-in dashboard being JS-rendered is **correct** — it's gated app UI, not marketing content, and should stay out of the index.

## The evidence base (primary sources, confidence-tiered)

| Claim | Source | Confidence |
|---|---|---|
| Major AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Meta, Bytespider) **fetch JS but never execute it** — 500M+ GPTBot fetches, zero JS execution | [Vercel/MERJ, *The rise of the AI crawler*, Dec 2024](https://vercel.com/blog/the-rise-of-the-ai-crawler) | **Very High** (primary, network-scale) |
| Empirical: client-rendered pages are unreadable to ChatGPT/Perplexity/Claude; server-rendered read fine | [Glenn Gabe / GSQI, Aug 2025](https://www.gsqi.com/marketing-blog/ai-search-javascript-rendering/) | **High** (named practitioner, multi-engine test) |
| Googlebot executes JS but **renders only initial state — does not click/hover/type**; content behind a click "will not be crawled or indexed" | [Google: lazy-loading "does not interact with your page"](https://developers.google.com/search/docs/crawling-indexing/javascript/lazy-loading) · [Martin Splitt via SEJ](https://www.searchenginejournal.com/googlebot-doesnt-click-on-buttons-what-to-use-instead/400242/) | **Very High** (Google primary + Google rep) |
| Google discovers links **only** from `<a href>`; `onclick`/`span href`/`routerLink` are "not recommended" | [Google: Make your links crawlable](https://developers.google.com/search/docs/crawling-indexing/links-crawlable) | **Very High** (primary) |
| In-DOM `display:none`/accordion content **IS** crawlable; content **injected on click is NOT** — the load-bearing distinction for the fix | [ArcIntermedia](https://www.arcintermedia.com/shoptalk/collapsible-content-best-practices-does-hidden-content-affect-seo-aeo-geo/) corroborating Google's DOM model | **High** |
| For public/marketing pages, deliver content+metadata in initial HTML (SSG/SSR/static); JS only *enhances* (progressive enhancement) | [Next.js: Rendering Strategies](https://nextjs.org/learn/seo/rendering-strategies) · [MDN: Progressive Enhancement](https://developer.mozilla.org/en-US/docs/Glossary/Progressive_Enhancement) | **Very High** |
| `Organization` schema belongs on the homepage; `sameAs` (Wikipedia/Wikidata) + `@id` strengthen the entity in Google's Knowledge Graph (which powers its AI) | [Google: Organization](https://developers.google.com/search/docs/appearance/structured-data/organization) · [Ahrefs: Knowledge Graph](https://ahrefs.com/blog/google-knowledge-graph/) | **High** (entity link); AI-comprehension leap is inferential |
| FAQ rich results dropped **May 7 2026**; HowTo deprecated 2023. FAQPage still valid + Google still parses it | [SEJ](https://www.searchenginejournal.com/google-drops-faq-rich-results-from-search/574429/) · [Google FAQPage doc](https://developers.google.com/search/docs/appearance/structured-data/faqpage) | **High** |

> **Honesty flags (kept per evidence discipline):** the popular GEO multiplier stats — "SSR → 3× more AI citations," "internal linking → 34% more AI-Overview citations," "schema → 2.5× AI-answer odds," "FAQ schema → 3.2× AI-Overview odds" — are **uncited/self-cited marketing figures: direction credible, exact numbers LOW confidence — do NOT present as fact.** Whether in-DOM-but-CSS-hidden content is *weighted equally* to visible content is genuinely contested (Google says yes; some tests hint otherwise) — but it does NOT affect us, because our problem is content *absence from the DOM*, not its visibility.

**Additional primary evidence (strengthens the case, why this is high-leverage for a NEW PH entrant):**
- **Crawlability is a hard *prerequisite* for citation by the live-retrieval engines** (Perplexity, Google AI Overviews/AI Mode, Gemini, ChatGPT-with-search): they fetch live and can only cite what they can retrieve. A non-crawlable catalog is not "ranked lower" — it is *uncitable* by these engines. ([Search Engine Land, Jarboe, Oct 2025](https://searchengineland.com/how-different-ai-engines-generate-and-cite-answers-463234) — **High** on principle.)
- **Google's own May-2026 guide: "AEO/GEO is still SEO"** — AI-feature discoverability rides standard crawlability/indexability + semantic HTML + JS-SEO; Google explicitly says skip llms.txt, AI-special schema, and manual "chunking." ([SEJ on Google's guide](https://www.searchenginejournal.com/googles-new-ai-search-guide-calls-aeo-and-geo-still-seo/575026/) — **High**.) This *corroborates* the arc's llms.txt demotion AND the "just make it crawlable" thesis.
- **The on-page levers help LOW-RANKED sites MOST** — Princeton GEO (KDD 2024, peer-reviewed): for a rank-5 source, *Cite Sources +115%, Quotation +100%, Statistics +98%* visibility (these same tactics *reduce* a rank-1 source); keyword-stuffing scores **below** baseline. ([arXiv 2311.09735](https://arxiv.org/abs/2311.09735) — **High**.) WorkHive is the new-entrant case where these levers pay the most.
- **Front-load the answer:** 44.2% of ChatGPT citations come from the **first 30%** of a page (Kevin Indig, 1.2M responses / 18,012 verified citations). ([Search Engine Land](https://searchengineland.com/chatgpt-citations-content-study-469483) — **High**.) Validates answer-first openers (P2) and a front-loaded static catalog.
- **FAQ — two distinct events, keep the markup:** Aug 8 2023 Google *reduced* FAQ rich results (gov/health only) + limited HowTo to desktop ([Google blog, verbatim](https://developers.google.com/search/blog/2023/08/howto-faq-changes)); May 7 2026 FAQ rich results dropped for everyone (SEJ). Google: *"there's no need to proactively remove it … structured data that's not being used does not cause problems."* → **keep FAQPage as AEO grounding (it's free + may aid extraction), do not chase it as a proven citation lever, skip HowTo.**

## What the skills already say (this isn't a new pattern — it's a known one)

- **seo-content:** *"render the FACTS from the catalog, don't hand-type them"* — counts / list-membership / JSON-LD `featureList` become catalog-derived marker regions rewritten by `tools/render_public_surface.py`, guarded by `surface_render_drift`. **This is the exact fix for the 28-tool catalog.** Also: *"meta/SEO-critical content must be in static HTML"*; index.html is the only indexable surface; **skip HowTo (Google-deprecated), keep FAQPage as AEO grounding.**
- **frontend:** the static-vs-runtime invisibility family — *"a region that `innerHTML`-replaces is invisible to anything reading the static HTML"* (already bit us: 50 `<h1>`s inside template strings → live page had 0). `onclick` navigation is also keyboard-dead; **prefer real `<a href>`.**
- **designer:** the documented landing CTA convention **uses real `<a href>`**; the "tools drawer behind a FAB" is intentional UX but satisfied by **progressive enhancement** — render the links in markup, let JS enhance the drawer. The onclick-only catalog is a *deviation* from the design system, not a requirement of it.
- **mobile-maestro:** *"don't gate content/links behind an interaction (hover/click/JS) — render it inline"*; a static catalog also improves **CLS/LCP** (a P3-CWV win, not just crawlability).

## P2.5 — Landing-page content & link extractability (NEW sub-phase, mostly Layer A)

Slots between P2 (article extractability) and P3 (CWV+entity). **Most of it is pure-code Layer A (mine, no Ian input); two items are Ian-gated content/profile.**

| # | Deliverable | Layer | Status |
|---|---|---|---|
| 2.5a | **Static catalog render** — derive `tool_catalog_mirror` from index.html's `stageData` (+ back-fill catalog routes it omits) via `render_public_surface.py`; sr-only `<section>` mirror with real `<a href>` + rich desc per tool; popup = progressive enhancement. Closes L1+L2+L5. | **A — me** | **✅ DONE 2026-06-30** (31 tools + 1 back-fill rendered; drift-guarded) |
| 2.5b | **≥1 crawlable `<a href>` per tool page** — satisfied by 2.5a (16/25 unlinked → 0). | **A — me** | **✅ DONE** |
| 2.5c | **`featureList` on `SoftwareApplication` JSON-LD** (catalog-derived, drift-guarded by the gate). | **A — me** | **✅ DONE** (31 tools; jsonld still valid) |
| 2.5d | **`landing_extractability` gate** — measures all the above, ratcheted, registered. | **A — me** | **✅ DONE** (self-test 10/10; 63→0; registered) |
| 2.5e | **Keyword-bearing `<h1>`** — Ian chose "keep brand + add keywords." | **Ian voice** | **✅ DONE 2026-06-30** — H1 now carries "Access Your Memory" + a 2nd line "Free Industrial Tools for Every Filipino Worker" (colon-style join, no em dash per house rule); one_h1 still 0 |
| 2.5f | **Populate `sameAs`** (+ optional Person/E-E-A-T). | **Ian-gated** | ⏳ needs Ian's profile URLs (L4) — requested |

### The new gate — `landing_extractability` (catalog-derived, ratcheted)

Same convention as `seo_technical_gate` / `content_grounding_gate` (forward-only baseline, `--self-test`, registered in the default run). Asserts, against the **static** HTML of `index.html` (no JS execution — i.e. it sees exactly what GPTBot/ClaudeBot see):

1. **`catalog_tool_links`** — every tool in `platform_catalog` has a real `<a href="<tool>.html">` present in the static DOM (NOT only inside a JS string / `onclick`). FAIL lists the missing tools.
2. **`catalog_tool_copy`** — each tool's name + a description sentence is present as crawlable text (not only in `stageData`).
3. **`featurelist_jsonld`** — `SoftwareApplication.featureList` exists and matches the catalog count.
4. **`crawlable_link_floor`** — count of real internal `<a href>` to tool/learn pages ≥ a catalog-derived floor (catches a regression that re-buries links in JS).
5. **`count_claim_adjective_safe`** — any "N tools/guides" claim matches the catalog count, with an adjective-tolerant regex ("28 free tools").

This gate is **detection-only** (it reads `index.html`, doesn't modify it), so it's safe to build + run now regardless of when the 2.5a render lands — it produces the **measured baseline** for the cells below.

**BUILT + VERIFIED + REGISTERED (2026-06-30):** `tools/landing_extractability_gate.py` — self-test 10/10, registered in `run_platform_checks` (`landing-extractability`, "AI Validation", `skip_if_fast`), ratcheted forward-only. **Measured FIRST baseline (script-stripped DOM = what GPTBot/ClaudeBot see):** `tool_page_links` 16/25 unlinked · `popup_tool_copy` 26/31 descriptions not in DOM · `popup_tool_links` 20/31 links JS-only · `featurelist_jsonld` missing · `count_claim_match` 0 → **63 issues.**

**BURNED DOWN TO 0 — P2.5a + P2.5c SHIPPED (2026-06-30, Ian approved approach B "in-DOM mirror, popup stays"):**
- **2.5a (mirror):** extended `tools/render_public_surface.py` to derive `tool_catalog_mirror` from index.html's OWN `stageData` (so the static mirror tracks the popup, one source) + back-fill any active catalog tool page stageData omits (e.g. `ai-quality.html`). Added an `sr-only <section>` in index.html (after the hero, high in DOM) with a `<!--CATALOG:tool_catalog_mirror-->` region holding a real `<a href>` + the rich description per tool. `--apply` rendered all 31 tools + 1 back-fill; the JS popup stays the visible UX (progressive enhancement). Guarded by `surface_render_drift` (can't drift from stageData).
- **2.5c (featureList):** added a catalog-derived `featureList` (31 tools) to the `SoftwareApplication` JSON-LD; hardened the gate's `featurelist_jsonld` check to verify the list COVERS every stageData tool (drift-guarded). JSON-LD still parses (`seo_technical.jsonld_valid` = 0).
- **Result: `landing_extractability` 63 → 0, all 5 checks OK, re-baselined to 0** (regression now fails). `render_public_surface --check` CLEAN; self-test 10/10.
- **2.5e SHIPPED (Ian chose "keep brand + add keywords"):** the hero `<h1>` now reads "Access Your Memory" + a smaller second line "Free Industrial Tools for Every Filipino Worker" (the keyword phrase is now IN the H1, where search/AI weight it; one_h1 still 0, no em dash per house rule).
- **Only remaining landing item — 2.5f `sameAs` (needs Ian's profile URLs, requested).** Everything else on the landing page is done + gated.

### Scoreboard impact (measured, not vibe)

The current SEO ~90% / AEO ~75% **overstated landing-page readiness** because no gate measured the homepage's crawlable catalog. This extension added the cells that expose it; the gate produces the number. **First MEASURED baseline (`landing_extractability_gate`, 2026-06-30): 16/25 tool pages unlinked · 26/31 popup descriptions absent from the DOM · 20/31 popup links JS-only · no `featureList` → 63 issues. After 2.5a+2.5c: 63 → 0 (the catalog is now fully crawlable).** Remaining landing-page gap = Ian-gated only (keyword `<h1>` + `sameAs`). New cells:

- **SEO · Crawl/index:** add *"every catalog tool page has ≥1 crawlable `<a href>` from index.html"* → measured by `landing_extractability`.
- **AEO · Extractability (40%):** add the **landing page** to the per-surface extractability denominator (today only the 38 articles count) — the homepage is the #1 "what is WorkHive" target and its catalog is currently non-extractable.
- **GEO · On-page triad / entity:** the static catalog + `featureList` + populated `sameAs` are the homepage's GEO levers.

## Synthesis verdict (fuse-or-keep, per the synthesis-is-the-deliverable rule)

- **FUSE the tool catalog into ONE canonical static render.** Today it lives in three places (JS `stageData`, `nav-hub.js TOOLS`, and the human-only popup) and is crawlable in none. Owner: `render_public_surface.py`, source: `platform_catalog`. What gets deleted: the hand-maintained drift surface; the JS popup *keeps* its UX role as progressive enhancement over the static links. Blast radius: index.html hero/footer + the new gate. **This is the highest-leverage single change in the whole arc for AEO/GEO** because it's the richest content on the only indexable page.
- **KEEP the static answer-first paragraph + 15-Q FAQ + `@graph` schema as-is** — they're the arc already working; don't re-engineer them. Keep FAQPage (AEO grounding) but **do not chase HowTo** (deprecated).
- **KEEP `#ops-home` JS-rendered** — correct; it's gated app UI, not marketing.
- The three Ian-gated items (keyword H1 in his voice, `sameAs` profile URLs, Person E-E-A-T) ride the existing P3-entity gate — no new dependency.

**Bottom line:** the arc was measuring the 38 articles well but flying blind on the one page that faces search + AI. P2.5 closes that with a catalog-derived static render + a detection gate, applying a fix-pattern WorkHive already owns. It's ~80% pure-code Layer A (mine), with H1 wording + `sameAs` the only Ian-gated pieces.
