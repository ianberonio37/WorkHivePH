# WorkHive Public Launch — SEO + AEO + GEO Roadmap

**Created:** 2026-05-16
**Owner:** Ian Beronio
**Status:** ALL 6 PHASES READY. On-page work complete (Phases 0-2b shipped: 24 articles, 48,194 words, 146 FAQs, 0 em-dashes, 23/23 tools covered). Phase 3 off-site authority playbook ready ([SEO_PHASE_3_OFFSITE_AUTHORITY.md](SEO_PHASE_3_OFFSITE_AUTHORITY.md)). Phase 4 AI crawler hygiene shipped in Phase 0. Phase 5 measurement playbook + working prompt_audit.py tool ready ([SEO_PHASE_5_MEASUREMENT.md](SEO_PHASE_5_MEASUREMENT.md)). Phase 6 local PH SEO playbook ready ([SEO_PHASE_6_LOCAL_PH.md](SEO_PHASE_6_LOCAL_PH.md)) covering GBP, LocalBusiness schema, PH directories, association memberships, press, government agency listings. Execution gates: DTI registration unlocks Phase 6; GA4 Measurement ID unlocks Phase 5 wiring across 26 pages.

Synthesized from: current platform state (`index.html`, `sitemap.xml`, `robots.txt`, `manifest.json`), the `seo-content` skill, and reputable 2026 sources on AEO, GEO, Core Web Vitals, llms.txt, brand mentions, and entity SEO.

---

## Baseline (what we have today)

| Layer | Current state | Gap |
|---|---|---|
| **SEO** | Title/description/OG/Twitter present; `SoftwareApplication` JSON-LD; canonical set; google-site-verification | Sitemap has only 1 URL; OG image is a transparent logo (renders badly); no `Organization` schema; no `sameAs` entity links |
| **AEO** | None | No FAQ schema, no HowTo schema, no Q&A pages, no answer-first content blocks |
| **GEO** | None | No public content for AI to cite; no Reddit/LinkedIn/Wikipedia presence; no `knowsAbout`; no llms.txt |
| **Content** | 1 public page (index.html); 17+ app pages all correctly `noindex` | Zero topical content — nothing for ChatGPT/Perplexity/Gemini to reference |
| **Local PH** | "Philippines" in keywords | No `LocalBusiness` schema, no PH-specific signals beyond keyword string |

**Core strategic gap:** an AI engine cannot recommend WorkHive if there is nothing public to read. App pages are (correctly) noindex, so we are competing for AEO/GEO citations with one landing page. Phase 2 fixes this.

---

## Phase 0 — Technical SEO Hardening (Week 1, 1-2 days)

Cheap, fast, blocks nothing. Do before public launch.

| # | Action | File | Why |
|---|---|---|---|
| 0.1 | Replace transparent-logo OG image with 1200x630 social card (logo + tagline + hex pattern) | `brand_assets/og-social.png` | Existing image renders unreadably in WhatsApp/LinkedIn/X previews |
| 0.2 | Expand sitemap to include every public learning-hub page once they exist (Phase 2) | `sitemap.xml` | Today's sitemap has 1 URL, which is fine pre-content but blocks Phase 2 |
| 0.3 | Add `Organization` JSON-LD with `sameAs` array pointing to LinkedIn/Facebook/GitHub/YouTube | `index.html` | Highest-impact entity SEO change per ALM Corp 2026; feeds Google Knowledge Graph |
| 0.4 | Add `knowsAbout` property listing domain topics (maintenance, OEE, MTBF, PM, etc.) | `index.html` | 2nd most impactful entity signal post-March 2026 |
| 0.5 | Add `LocalBusiness` schema (Philippines address, geo-coordinates, openingHours) | `index.html` | Required for PH local Knowledge Panels and AI "best X in Philippines" queries |
| 0.6 | Set up GA4 + Search Console + Bing Webmaster Tools | (external) | Cannot improve what cannot be measured |
| 0.7 | Run Lighthouse / PageSpeed Insights, fix LCP > 2.5s if any | (audit) | CWV is Google's tie-breaker; entry fee, not winner |

---

## Phase 1 — AEO Foundation (Week 2, 3-4 days)

Make every page answerable. This is where AI engines start citing us.

| # | Action | Detail |
|---|---|---|
| 1.1 | Add real FAQ section to `index.html` with 8-12 questions workers actually ask | Mark up with `FAQPage` schema. Highest citation rate of any schema type in ChatGPT/Perplexity/AI Overviews |
| 1.2 | Rewrite hero + first section in answer-first format (40-60 word direct answer to "What is WorkHive?" placed before any marketing copy) | AI engines reward content that puts the answer first |
| 1.3 | Add `HowTo` schema to any "Getting Started" or "How to log a fault" content | Maps directly to ChatGPT's "how do I X" queries |
| 1.4 | Add author bylines + `Person` schema on any content page | Pages with author E-E-A-T see 22% higher AI visibility |
| 1.5 | Ensure every public page declares publish + last-updated date in visible HTML AND in schema | Perplexity prefers recent content |

---

## Phase 2 — Content Authority Hub (Weeks 3-6, biggest lift)

The unlock. Without this, GEO is impossible. Build a `/learn/` folder of 15-25 public, indexable pages.

### First 15 articles (low competition + high AI-query volume)

1. ✅ What is OEE and how do I calculate it? → analytics.html [2026-05-17]
2. ✅ How to write a maintenance shift handover → shift-brain.html [2026-05-17]
3. ✅ MTBF vs MTTR explained for plant supervisors → analytics.html [2026-05-17]
4. ✅ Free PM checklist templates → pm-scheduler.html [2026-05-17]
5. ✅ How to start a digital logbook → logbook.html [2026-05-16, enriched 2026-05-17]
6. RCM vs FMEA vs PMO → pm-scheduler.html (concept)
7. ✅ Spare parts inventory (ABC, FIFO, reorder) → inventory.html [2026-05-17]
8. ✅ How to build a skill matrix → skillmatrix.html [2026-05-17]
7. Permit to work in the Philippines (DOLE / OSHS requirements)
8. ISO 14224 reliability data: what Filipino plants need to know
9. How to build a skill matrix for maintenance technicians
10. Predictive maintenance on a budget: what actually works
11. CMMS vs free industrial tools: when to pay, when not to
12. Failure mode catalog for [pump / motor / compressor / boiler]
13. Inventory management for spare parts (FIFO, ABC, reorder points)
14. How to read vibration analysis charts (visual guide)
15. Top 10 industrial maintenance KPIs every supervisor should track

### Format rules per article (non-negotiable for AEO/GEO)

- 40-60 word direct answer in first paragraph
- FAQ block at bottom with `FAQPage` schema
- One H1, logical H2/H3 hierarchy
- Author byline + photo + credentials
- Published + updated dates
- Internal links to other `/learn/` articles (topical cluster)
- 1 external citation to an authoritative source (ISO, DOLE, SMRP)
- Schema: `Article` + `FAQPage` + `BreadcrumbList`
- Pipe separator in title (per skill): `WorkHive | What is OEE...`
- Canonical tag, indexable (not noindex like app pages)

Update `sitemap.xml` as each article ships. Update `validate_seo.py` to scan `/learn/` pages too.

---

## Phase 3 — GEO + Off-Site Authority (Weeks 4-12, parallel with Phase 2)

This is where AI engines decide whether to recommend us. Cannot be skipped.

Per Tinuiti Q1 2026 + ALM Corp: Reddit (40%) + Wikipedia (26%) + LinkedIn = roughly 70% of all AI citation weight.

| Channel | Action | Cadence |
|---|---|---|
| Reddit | Personal account (NOT brand). Useful answerer in r/PLC, r/engineering, r/IndustryFour, r/manufacturing, r/Philippines. Mention WorkHive only when genuinely relevant | 3-5 substantive comments/week, 1 self-post/month |
| Wikipedia | Don't try to create a WorkHive page (will be deleted). Become a citing source: improve Philippine industry / maintenance-engineering / OEE / MTBF pages with `/learn/` articles as references | 1-2 edits/month using proper sourcing |
| Wikidata | Create a Wikidata entry for WorkHive. Link `sameAs` in Organization schema | One-time + quarterly refresh |
| LinkedIn | Company page mirroring Organization schema description verbatim. Founder posts 2x/week on maintenance topics with `/learn/` articles linked | 2 posts/week |
| YouTube | Short walkthroughs (3-5 min) get cited by AI engines. Demo: digital logbook, PM checklist, AI assistant | 1 video/month minimum |
| GitHub | Make any open-source helper (calc library, schema templates) public under WorkHive org | One-time + maintenance |
| PH industry forums / FB groups | Same playbook as Reddit: help, don't pitch | Ongoing |

---

## Phase 4 — AI Crawler Hygiene (Week 2, 30 min)

Cheap insurance even though adoption is mixed.

| # | Action |
|---|---|
| 4.1 | Add `llms.txt` to root: markdown map of `/learn/` articles, key tool descriptions, and the entity definition of WorkHive. Production AI bots ignore it today, but developer-tool ecosystems already adopt it. Zero-downside |
| 4.2 | Update `robots.txt` to explicitly Allow known AI crawlers: GPTBot, ClaudeBot, Google-Extended, PerplexityBot, CCBot, OAI-SearchBot |
| 4.3 | Confirm domain returns clean HTML (no JS-rendered hero) so AI crawlers see content |

---

## Phase 5 — Measurement & Iteration (ongoing from Week 4)

| Tool | Tracks | Cost |
|---|---|---|
| Google Search Console | Traditional SEO impressions/clicks/CTR | Free |
| GA4 | Sessions, conversions, source/medium | Free |
| Bing Webmaster Tools | Bing + Copilot visibility (Copilot uses Bing index) | Free |
| Manual ChatGPT/Perplexity/Gemini prompt audits | 20-30 target queries weekly, log if WorkHive is cited | Free, 30 min/week |
| Profound / Otterly / Peec.ai / LLMrefs | Automated AI visibility tracking | $50-200/mo (defer 3 months) |

### Target queries to track weekly (prompt-level KPIs)

- "best free industrial maintenance tools for small factories"
- "digital logbook for maintenance technicians Philippines"
- "free OEE calculator"
- "how to start a CMMS without budget"
- "[competitor name] alternatives"

---

## Phase 6 — Local Philippine SEO (Weeks 2-4, parallel)

| # | Action |
|---|---|
| 6.1 | Google Business Profile: claim WorkHive as "Software company" / "Industrial software" listing with Philippine address |
| 6.2 | List on PH directories: BusinessList.ph, Yellow Pages PH, DTI Negosyo Center directory |
| 6.3 | Reach out to PH industry associations (PSME, IIEE, PIChE, MAP) for member listing or guest article |
| 6.4 | Submit `/learn/` articles to PH industrial publications (Manila Bulletin Business, BusinessWorld tech section) |

---

## 12-week sprint sequencing

| Week | Phase | Headline deliverable |
|---|---|---|
| 1 | Phase 0 + 4 | Tech SEO hardened, OG card live, schemas + llms.txt deployed |
| 2 | Phase 1 | FAQ + answer-first hero + HowTo schema on index.html |
| 3-6 | Phase 2 | 15 `/learn/` articles published with full AEO formatting |
| 4-12 | Phase 3 + 6 | LinkedIn + Reddit + Wikidata + GBP live; weekly Reddit cadence; first Wikipedia citation |
| 5+ | Phase 5 | GSC + GA4 dashboards; weekly prompt audit log started |
| 12 | Review | First measurable AI citation; pick top 5 articles to expand |

---

## Out of scope (and why)

- **Paid ads** — premature; build organic foundation first
- **Backlink outreach campaigns** — let `/learn/` content earn links naturally; cold outreach wastes time at this stage
- **Domain-authority chasing tools (Ahrefs/Semrush subscriptions)** — useful later, not at zero-content baseline
- **AI visibility tracking SaaS** — defer 3 months; manual audits are sufficient until there is content to track

---

## Sources

**AEO**
- [AEO 101: Definitive Guide 2026 - Cubitrek](https://cubitrek.com/blog/aeo-101-answer-engine-optimization-guide/)
- [Comprehensive AEO Guide 2026 - CXL](https://cxl.com/blog/answer-engine-optimization-aeo-the-comprehensive-guide/)
- [Complete AEO Guide 2026 - Frase](https://www.frase.io/blog/what-is-answer-engine-optimization-the-complete-guide-to-getting-cited-by-ai)
- [Are FAQ Schemas Important for AI Search - Frase](https://www.frase.io/blog/faq-schema-ai-search-geo-aeo)
- [AEO Your 2026 Guide - Surfer SEO](https://surferseo.com/blog/answer-engine-optimization/)
- [AEO Practical Playbook 2026 - ALM Corp](https://almcorp.com/blog/answer-engine-optimization-2026/)

**GEO**
- [GEO 2026 Guide - LLMrefs](https://llmrefs.com/generative-engine-optimization)
- [GEO Complete 2026 Guide - Enrich Labs](https://www.enrichlabs.ai/blog/generative-engine-optimization-geo-complete-guide-2026)
- [How ChatGPT, AI Overviews, Perplexity Source Information 2026 - Leapd](https://www.leapd.ai/blog/ai-visibility/how-chatgpt-google-ai-overviews-and-perplexity-source-information-in-2026)
- [5 GEO Strategies for 2026 - Search Engine Journal](https://www.searchenginejournal.com/geo-strategies-ai-visibility-geoptie-spa/568644/)
- [5W AI Platform Citation Source Index 2026 - PR Newswire](https://www.prnewswire.com/news-releases/5w-releases-ai-platform-citation-source-index-2026-the-50-websites-that-now-decide-what-brands-are-visible-inside-chatgpt-claude-perplexity-gemini-and-google-ai-overviews-302759804.html)

**SEO + Core Web Vitals**
- [Technical SEO Checklist 2026 - DebugBear](https://www.debugbear.com/blog/technical-seo-checklist)
- [Core Web Vitals 2026 - Digivate](https://www.digivate.com/blog/seo/core-web-vitals-in-2026/)
- [Google Ranking Factors 2026 - BitPeppy](https://bitpeppy.com/blogs/the-complete-guide-to-google-ranking-factors-2026-update)

**llms.txt**
- [llms.txt Zero Usage - AEO Engine](https://aeoengine.ai/blog/llms-txt-zero-usage-ai-bots-ignore)
- [What Is llms.txt - Semrush](https://www.semrush.com/blog/llms-txt/)
- [llms.txt 2026 Guide - Bluehost](https://www.bluehost.com/blog/what-is-llms-txt/)

**Brand mentions / Reddit / Wikipedia**
- [Reddit's Rise in AI Citations - CMSWire](https://www.cmswire.com/digital-marketing/reddits-rise-in-ai-citations-what-marketers-must-know-about-aeo-strategy/)
- [Reddit #2 Most Cited Source - ALM Corp](https://almcorp.com/blog/reddit-ai-search-citations-geo-for-brands/)
- [What Actually Drives AI Recommendations - Search Engine Land](https://searchengineland.com/reddit-wikipedia-what-drives-ai-recommendations-472580)
- [What Drives AI Recommendations - ALM Corp](https://almcorp.com/blog/what-drives-ai-recommendations/)

**Entity SEO + Schema**
- [Schema Markup 2026 - ALM Corp](https://almcorp.com/blog/schema-markup-detailed-guide-2026-serp-visibility/)
- [Schema Markup After March 2026 - Digital Applied](https://www.digitalapplied.com/blog/schema-markup-after-march-2026-structured-data-strategies)
- [Organization Schema Complete Guide 2026 - Stackmatix](https://www.stackmatix.com/blog/organization-schema-knowledge-graph)
- [Scalable Enterprise SEO 2026 (Singapore/Philippines) - Sotavento](https://www.sotaventomedios.com/how-can-large-organisations-scale-seo-effectively-in-2026/)
