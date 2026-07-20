# SEO · AEO · GEO MAXIMIZATION — the post-launch drive-to-100 roadmap

**Created:** 2026-07-19 · **Owner:** Ian Beronio + Claude · **Status: PLANNING — laid out for alignment. Night-Crawler-grounded. Commit/deploy = Ian's gate.**

**Origin (Ian, 2026-07-19):** *"can we use Night Crawler to fully maximize and optimize our SEO AEO GEO, so that we can make a new roadmap for this?"* → scope chosen: **Full (Layer A code + Layer B off-site playbook)**, harvest depth **Comprehensive (~20 sources)**.

**Method (the Grafana-maximization pattern, re-applied):** understand the platform's *current* state via the existing gates → Night-Crawler-distill the reputable 2026 sources into `substrate/external/` (retrieve-forever) → synthesize a measured, gated, per-axis roadmap. All INLINE, retrieve-first, no fan-out (per the WAT token governance).

---

## Why this roadmap exists (and what it supersedes)

We already have two SEO docs and one measured arc:
- `SEO_AEO_GEO_ROADMAP.md` (2026-05-16) — the *launch playbook* (6 phases, 45 articles). **Shipped.**
- `SEO_AEO_GEO_100_ARC.md` (2026-06-29/30) — the *measured Layer-A substrate* (six gates built + green). **Substrate complete; content retrofit + entity + Layer B still open.**

**What changed since the arc — and why a fresh roadmap is warranted:**
1. **Production is now PUBLIC** at workhiveph.com (the arc predated launch — it planned against a stale/unpushed site).
2. **GA4 is wired and LIVE** (`G-ENMGLTFR2J`) — the arc listed "GA4 not wired" as a gap. Closed.
3. **IndexNow is built** (key file + `tools/indexnow_submit.py`) — instant push-indexing to Bing/Copilot/Yandex/DuckDuckGo, an AEO/GEO lever the arc never had. (Deploy = Ian's gate; see `SEO_PHASE_5_MEASUREMENT.md` §2b.)
4. **Sitemap is now 51 URLs** (arc said 43) — home + hub + 45 articles + about/feedback/privacy/terms.
5. The **six Layer-A gates are all green** as of 2026-06-30; the honest remaining work is a small content retrofit, entity wiring (Ian's URLs), and the whole earned-off-site layer.

This roadmap **subsumes** the arc's open items and re-frames them against the live site, adds the fresh 2026 evidence, and lays out the **full Layer-B off-site playbook** that "fully maximize" requires.

---

## Current MEASURED baseline (gates re-run 2026-07-19)

| Lever | Gate / probe | Current | Verdict |
|---|---|---|---|
| Technical SEO (1×H1, alt, JSON-LD validity, no-new-retired-schema) | `seo_technical_gate.py` | PASS (retired_schema baselined at 58) | ✅ |
| Crawl graph (0 orphans, ≤3 clicks) | `orphan_depth_gate.py` | 0 orphans · 0 depth>3 | ✅ |
| Landing catalog crawlability (static mirror, featureList, count-claim) | `landing_extractability_gate.py` | 0 issues | ✅ |
| On-page extractability (Princeton triad) | `extractability_gate.py` | stats 100% · citations 100% · **5 articles miss answer-first opener** | ⚠️ close |
| Core Web Vitals (mobile, warm) | `cwv_gate.py` + `cwv_probe.mjs` | LCP/INP/CLS all GREEN warm; **cold-LCP 3-5s (Tailwind CDN render-block)** | ⚠️ cold |
| AI Share-of-Voice | `geo_sov_audit.py` | 37 bilingual prompts ready · **0 live runs logged** | ⛔ Layer B |
| Entity | `index.html` @graph | Organization+Person+WebSite+SoftwareApplication+knowsAbout present; **`sameAs: []` empty**; no LocalBusiness / aggregateRating | ⚠️ Ian-gated |
| Discoverability | sitemap / GA4 / IndexNow | sitemap 51 URLs ✅ · GA4 live ✅ · IndexNow built (deploy pending) ⚠️ | mostly ✅ |
| Off-site authority | (none) | 0 brand mentions / YouTube / Reddit / Wikidata | ⛔ Layer B |

---

## The two-layer model (unchanged from the arc — it's the right frame)

- **Layer A — Buildable substrate (code, 100% ours):** every code-controllable lever, gated + ratcheted. **This is the half I drive to 100% now.**
- **Layer B — Earned outcome (AI Share-of-Voice + authority):** compounds over 2-12 weeks via off-site execution. Measured by the SOV harness, not built. **Ian executes; I prep every asset.**

**Layer-A ceiling (code-controllable max), per the arc's weighted scorecard: SEO 95 / AEO 60 / GEO 35.** The rest of each axis is *won* off-site. The research (harvest below) is unambiguous that **~80% of GEO and ~40% of AEO are earned off-site, not coded** — so Layer B is where the biggest wins live, and it's why "fully maximize" must include the off-site playbook, not just the gates.

---

## Per-axis scoreboard (each cell named with the gate that measures it)

### SEO — 100% = all hard gates green AND weighted ≥95 (Layer A) + authority (Layer B)
| Cell | Gate | State |
|---|---|---|
| Technical (H1/alt/schema-validity) | `seo_technical` | ✅ green |
| Crawl graph (orphans/depth) | `orphan_depth` | ✅ 0/0 |
| Landing catalog crawlable | `landing_extractability` | ✅ 0 |
| CWV mobile (warm) | `cwv_gate` | ✅ green |
| CWV cold-LCP (Tailwind CDN) | `cwv_gate` `lcp_cold_ms` | ⚠️ P3 lever |
| Discoverability (sitemap/GA4/IndexNow) | manual + `indexnow_submit` | ⚠️ deploy IndexNow |
| Entity `sameAs`/LocalBusiness | `index.html` @graph | ⚠️ Ian URLs |
| Authority (backlinks/mentions) | Layer-B harness | ⛔ earned |

### AEO — 100% = per-page extractability 100% (Layer A) AND ≥70% first-mention on the prompt set (Layer B)
| Cell | Gate | State |
|---|---|---|
| Answer-first opener (all articles) | `extractability` `answer_first` | ✅ 0/0 (M1a done) |
| ≥1 statistic per article | `extractability` `has_statistic` | ✅ 0 gaps |
| ≥1 cited source per article | `extractability` `has_citation` | ✅ 0 gaps |
| Comparison table (free vs paid CMMS) | on what-is-workhive `#free-offline` | ✅ M1b done |
| FAQ/HowTo schema (content-aligned) | `seo_technical` retired_schema | ✅ KEEP (AI-Mode asset, see M1c note) |
| Top-cited/first-mention on prompts | `geo_sov` | ⛔ earned |

### GEO — 100% = Princeton-triad gate 100% (Layer A) AND #1/tied SOV + ≥70% presence on Perplexity+AI-Overviews (Layer B)
| Cell | Gate | State |
|---|---|---|
| Princeton triad on-page (stat+source+quote) | `extractability` | ✅ (bar answer-first) |
| Entity `sameAs` + Wikidata | `index.html` @graph | ⚠️ Ian URLs |
| Person/author E-E-A-T | `index.html` @graph | ⚠️ Ian bio |
| llms.txt (hygiene only — NOT a citation lever) | `llms_article_completeness` | ✅ keep as hygiene |
| SOV #1/tied on prompt set | `geo_sov` | ⛔ earned |
| Off-site citations (Reddit/YouTube/Wikipedia) | Layer-B harness | ⛔ earned |

---

## Phase roadmap — measured % per phase

| Phase | Ships | Layer/Owner | Locks (gate) | SEO | AEO | GEO |
|---|---|---|---|---|---|---|
| **Baseline (2026-07-19)** | substrate green + prod live + GA4 + IndexNow built | — | 6 gates | ~90% | ~55% | ~32% |
| **M1 — Finish Layer-A on-page** ✅ | 5 answer-first openers (DONE, gate 0/0) + comparison table (DONE, on what-is-workhive) + schema decision: KEEP aligned FAQ/HowTo as AI-Mode asset (harvest flip, see note) | A — me | `extractability` answer_first→0 ✅ | 92% | 60% | 33% |
| **M2 — CWV cold + entity prep** | self-host/inline critical CSS to kill Tailwind-CDN cold-LCP; draft Organization/Person/Wikidata (values = Ian) | A — me (values Ian) | `cwv_gate` cold + entity draft | 95% | 60% | 35% |
| **▶ Layer-A ceiling (all code done)** | — | — | all A-gates green | **95%** | **60%** | **35%** |
| **M3 — Entity + measurement go-live** | wire `sameAs`/Person once Ian gives URLs+bio; deploy IndexNow + run `--submit`; register BWT/GSC; **first live `geo_sov` run = the Layer-B baseline** | A+B | `geo_sov` baseline logged | 97% | 68% | 45% |
| **M4 — Off-site kickoff** | YouTube how-tos (grounded pipeline) + Reddit authentic + G2/Capterra listings + PH digital-PR + GBP + Wikidata item | B — Ian (I prep) | SOV harness tracks | 98% | 82% | 70% |
| **M5 — Compounding loop (8-12 wks)** | weekly SOV audit + ≤90-day content refresh + Wikipedia + mentions accrue | B — Ian | SOV ≥ target | 100% | 100% | 100% |

---

## 2026 Evidence base (Night-Crawler harvest → `substrate/external/`)

_Distilled this session: **18 of 20 sources** landed durable chunks in `substrate/external/` (retrievable at 0 future crawl cost via `night_crawler.py --query "<topic>"`). 2 failed to fetch (ALM reddit-brands + SEJ geo-strategies) — both covered by distilled siblings, noted below. Each slug below is the exact on-disk chunk._

### A. Technical / crawlability — the AI-era prerequisite
- **AI crawlers FETCH JavaScript but do NOT execute it** — ChatGPT prioritizes HTML (57.7%), Claude images (35.2%); both run ~34% 404 rates; Googlebot/AppleBot render JS, CCBot does not. → **Server-side / static-render all critical content; client-side only for non-essential.** `external-ai-crawlers-fetch-but-do-not-execute-javascript-` (Vercel/MERJ). *Why our landing catalog mirror mattered; any NEW content must live in the static DOM.*
- **AI-search JS-rendering empirical test** — click-injected / lazy content is invisible to the engines. `external-ai-search-javascript-rendering-empirical-test` (GSQI).
- **Technical-SEO 2026 checklist** — crawlability + indexability remain the floor. `external-technical-seo-checklist-2026-crawlability-indexi` (DebugBear).
- **Core Web Vitals 2026** — LCP <2.5s / INP <200ms / CLS <0.1 at the **75th percentile of CrUX FIELD data** (not lab, not average — your slowest quarter); expect ~28 days for old failing samples to age out. LCP culprits: **synchronous JS + non-critical CSS on the initial view**, no edge cache. Fix: `fetchpriority="high"` on the LCP element, stale-while-revalidate / edge compute, defer non-critical CSS. `external-core-web-vitals-2026-lcp-inp-cls-thresholds` (Digivate). *Our cold-LCP fix (M2): the render-blocking Tailwind CDN IS the "non-critical CSS on initial view" anti-pattern.*

### B. On-page GEO / AEO levers — what we fully control
- **Princeton/SIGKDD GEO triad boosts visibility up to +40%** in generative-engine responses; efficacy is **domain-specific** (WorkHive = the new-entrant case where the levers pay most). `external-princeton-geo-generative-engine-optimization-tri` (arXiv 2311.09735).
- **Front-load the answer in the first 30% of the page**; AI search also revives old content (~29% of ChatGPT citations reference content from 2022 or earlier — so our fresh 2026 articles compete well). `external-chatgpt-citations-content-study-front-load-answe` (SEL / Indig). *Validates the `extractability` answer-first gate — finish the 5 open articles.*
- **How AI engines generate + cite answers** — live-retrieval engines can only cite what they crawl. `external-how-ai-engines-generate-and-cite-answers` (SEL).
- **★ Per-engine mechanics differ — "AI search" is NOT one target** (only **11% of domains are cited by BOTH ChatGPT and Perplexity**): AI Overviews appear in **~50% of searches** and cited pages earn **+35% organic clicks**; Perplexity visitors convert at **~11× organic**; ChatGPT cites brands just **0.59%** of the time (Perplexity **13.05%**); Wikipedia is ChatGPT's #1 source (7.8%), Reddit is #1 for AI Overviews (2.2%) + Perplexity (6.6%); ChatGPT favors **structured H1/H2/H3 + direct-answer + cited claims**. `external-how-chatgpt-google-ai-overviews-perplexity-sourc` (Leapd) *[fresh]*. *Our bilingual `geo_sov` harness already scores per-engine — this says weight ChatGPT-shaped structure + Reddit/Wikipedia presence.*
- **AEO complete guide** — answer-first + Q&A + entity clarity = citation eligibility. `external-answer-engine-optimization-complete-guide-gettin` (Frase).
- **Google's 2026 guide: "AEO/GEO is still SEO"** — AI discoverability rides standard crawlability + semantic HTML; skip llms.txt / AI-special schema / manual chunking. `external-google-ai-search-guide-aeo-geo-is-still-seo-craw` (SEJ). *Corroborates demoting llms.txt to hygiene.*

### C. Schema / entity — Knowledge-Graph grounding
- **★ Schema after March 2026 — AI Mode uses structured data for ENTITY RESOLUTION + CLAIM VERIFICATION during answer synthesis; accurate schema raises AI-citation probability INDEPENDENT of rich-result display.** Rich-result eligibility narrowed to pages whose schema matches primary content; **31 types retain rich results**; **Organization + Person schema with `sameAs` is the single highest-leverage implementation type**; **LocalBusiness is critical for map-pack + local AI answers**. `external-schema-markup-structured-data-strategies-after-m` (DigitalApplied) *[fresh]*. *This directly ranks our fixes: `sameAs` (#1) > LocalBusiness > keep-accurate-schema.*
- **Organization schema + Knowledge Graph** — `sameAs` + consistent NAP + Wikidata is the entity-grounding path. `external-organization-schema-knowledge-graph-entity-seo-s` (Stackmatix) + `external-google-knowledge-graph-entity-building-sameas-wi` (Ahrefs). *Our `sameAs: []` empty = the highest-leverage entity fix — needs Ian's profile URLs.*
- **Google dropped FAQ rich results** (was gov/health-only since Aug 2023) — the visual SERP accordion is dead, but the SCHEMA is not: per section C, AI Mode reads it for claim verification and ChatGPT favors FAQ schema. So keep the FAQPage/HowTo `@type` where it's content-aligned, keep the Q&A/steps as body content, and simply do not expect a rich result. `external-google-drops-faq-rich-results-structured-data-de` (SEJ).

> **★ M1c decision (harvest flip, 2026-07-19):** the pre-harvest plan said "prune dead FAQ/HowTo schema." The 2026 evidence reverses that: **keep it.** WorkHive's 45 FAQPage + 12 HowTo nodes are valid (`jsonld_valid` 0/0) and content-aligned (spot-checked: what-is-oee → "How to calculate OEE" 6-step; spare-parts → "How to build a spare parts inventory" 6-step — both genuine how-tos). Aligned schema is an **AI-Mode entity-resolution + claim-verification asset**, independent of the dead rich result. Blind-pruning it would have *cost* AEO. The `seo_technical` `retired_schema` warning (baselined 58, HELD, non-blocking) is therefore **acknowledged-intentional**, not a backlog. Only genuinely *misaligned* HowTo (a HowTo `@type` on a non-step-by-step article) would be a future prune candidate — none found in the spot-check.

### D. Off-site / earned authority — where GEO is actually won (Layer B)
- **Brand MENTIONS beat backlinks ~3× for AI visibility** (Ahrefs 75K-brand: mentions correlate **0.664** vs backlinks **0.218**; **YouTube ~0.74**, the strongest single correlate; **Reddit the #1 cited domain**; ~85% of AI-answer brand mentions come from third-party pages) → **~80% of GEO is earned off-site.** Reddit/Wikipedia dominance re-confirmed in `external-reddit-wikipedia-what-drives-ai-recommendations` (SEL). *(The 0.664/0.218 correlations are from the 100_ARC's Ahrefs source; the ALM `external-what-drives-ai-recommendations-brand-mentions-vs` chunk distilled thin — a services page — so the durable stat lives in the 100_ARC citation, not that chunk. The failed `reddit-ai-search-citations-geo-for-brands` fetch is covered by the SEL sibling.)*
- **★ G2 / Capterra profiles = ~3× higher AI-citation probability** than sites without them (software-review presence is a citation signal for ChatGPT). `external-how-chatgpt-google-ai-overviews-perplexity-sourc` (Leapd). *NEW Layer-B lever — added to the playbook below.*
- **AI citation source index 2026** — a defined set of ~50 third-party domains (PR/news/media) that decide brand visibility across ChatGPT/Claude/Perplexity/Gemini/AI-Overviews — the Layer-B target list. `external-ai-platform-citation-source-index-2026-top-websi` (5W/PRNewswire) *[fresh]*.
- **GEO complete guide 2026** — end-to-end program view (the SOV discipline our `geo_sov_audit.py` implements; also covers the failed geo-strategies source). `external-generative-engine-optimization-geo-complete-guid` (EnrichLabs) *[fresh]*.

---

## Layer B — the off-site playbook ("fully maximize" = this half)

The research is one-directional: **GEO is ~80% earned off-site; brand mentions beat backlinks ~3x for AI visibility; YouTube + Reddit dominate citations.** Layer A makes us *citable*; Layer B makes us *cited*. I **prep every asset**; Ian executes the outward posting.

| Channel | Why (evidence) | What I prep | Ian executes |
|---|---|---|---|
| **YouTube how-tos** | Single strongest AI-visibility correlate (~0.74) | Grounded flagship video scripts (the built pipeline) + captions/transcripts w/ citable stats | Record + publish + channel |
| **Reddit authentic** | #1 cited domain (~40% of AI citations) | Draft value-first answers + which subreddits (r/maintenance, r/PLC, r/Philippines) + the honest-participation rules | Post from his account |
| **Wikidata + Wikipedia** | Entity grounding → Knowledge Graph → `sameAs` truth | Draft the Wikidata item + citable references | Submit |
| **PH digital-PR** | Local authority + `LocalBusiness` truth | Press one-pager + PSME/IIEE/Rappler/PhilStar-Tech target list | Pitch |
| **GBP + PH directories** | "best X in Philippines" AI answers + local pack | LocalBusiness schema draft + directory list (DTI/PEZA/BusinessList/YellowPages) | Register (needs DTI address) |
| **★ G2 / Capterra listings** | Software-review presence = **~3× higher AI-citation probability** (Leapd) — high-ROI for a SaaS | Draft the product profile, category, feature list, seed-review ask template | Claim the listing + gather reviews |
| **Brand mentions** | 0.664 correlation w/ AI visibility (vs 0.218 backlinks) | Citable stat pack + comparison tables third parties can quote | Seed via the above |
| **SOV measurement** | You can't improve what you don't measure | `geo_sov_audit.py` (37 bilingual prompts, 5 engines) — I run the harness | Review the weekly board |

---

## What I drive NOW vs what's Ian-gated

**I drive now (Layer A, pure code / content I can draft):**
- 5 answer-first openers (loto, RCM, sensor-cmms, skill-matrix, +1) → `extractability` answer_first → 0.
- Comparison tables (WorkHive-free vs paid CMMS) on the flagship articles.
- Prune dead FAQ/HowTo rich-result schema (keep Q&A as body; keep Organization/Article/SoftwareApplication/Breadcrumb).
- Kill cold-LCP: self-host / inline critical CSS instead of the render-blocking Tailwind CDN (perf skill).
- Draft the entity @graph (Organization/Person/Wikidata) with placeholder values; run the SOV harness for the Layer-B baseline.

**Ian-gated (values / accounts / outward):**
- `sameAs` profile URLs + Person/author bio + credentials.
- IndexNow key-file **deploy**, then `--submit` (I run the submit once it's live).
- Bing Webmaster + GSC sitemap submission (logins).
- LocalBusiness (DTI address) + aggregateRating (real reviews).
- All of Layer B's outward posting (YouTube/Reddit/Wikipedia/PR/GBP).

---

## NEXT queue

- **M1 ✅ DONE + VERIFIED (2026-07-19)** — 5 answer-first openers (from the pre-verified P2 drafts) → `extractability` 0/0; comparison table on what-is-workhive; schema-keep decision (harvest flip). All gates green.
- **M2-M5 ✅ SCAFFOLDED (2026-07-19)** — every remaining phase is skeletoned in **`seo_assets/`** (see `seo_assets/README.md`) so execution is fill-in-the-blank:
  1. `entity_schema_scaffold.md` — the #1 lever: drop-in `sameAs` + E-E-A-T Person + LocalBusiness. **Blocks on Ian's profile URLs + bio + address.**
  2. `m2_cold_lcp_fix_plan.md` — kill the Tailwind Play CDN. **Blocks on Ian's approach OK (no-build-step site).**
  3. `layer_b_playbook_assets.md` — G2/Capterra, YouTube, Reddit, digital-PR, Wikidata skeletons. **I prep; Ian executes.**
  4. `m5_weekly_sov_ritual.md` — first live `geo_sov` run = the Layer-B baseline.

Companion docs: `SEO_AEO_GEO_100_ARC.md` (measurement substrate), `SEO_PHASE_3_OFFSITE_AUTHORITY.md`, `SEO_PHASE_5_MEASUREMENT.md` (IndexNow + GA4 + BWT/GSC), `SEO_PHASE_6_LOCAL_PH.md`, `project_seo_indexnow_bing_launch_state` (memory).
