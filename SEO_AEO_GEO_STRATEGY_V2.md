# WorkHive SEO / AEO / GEO — Strategy V2 (evidence-grounded)

**Status:** supersedes `SEO_AEO_GEO_MAXIMIZATION_ROADMAP.md` as the strategy doc. It does **not** replace the shipped Layer-A code — that foundation stays and is built upon.
**Built:** 2026-08-03 · **Evidence spine:** 42 `substrate/external/` chunks (24 harvested for this doc, 2026-08-03; freshness validator green).
**Companion:** `seo_assets/TACTICAL_PLAYBOOK_V2.md` (the fill-in-the-blank execution artifacts).

> Every non-obvious claim below cites its durable chunk as `[external-<slug>]`. Chunks live in `substrate/external/`; retrieve any with `python tools/night_crawler.py --query "<topic>"` (0 crawl).

---

## 0. Why a V2 — the one-sentence diagnosis

The V1 roadmap is a **deep, self-graded code half bolted onto an unexecuted earned-authority half — and it graded itself on the half it controls.** Every scoreboard % (SEO ~90 / AEO ~55 / GEO ~32) was a self-estimate of *code state*, not one observed ranking, impression, or citation. The SOV harness had **run zero times**. No competitive analysis had ever been done. The query set was self-confirming (every `expected_cite` already a WorkHive URL). The 58 engineering calculators — the single largest programmatic-SEO surface WorkHive owns — were absent from the plan, locked invisibly in a client-side JS app.

**The evidence says that inverted emphasis is not a stylistic choice — it is where the citations actually come from:**

| Fact | Number | Source |
|---|---|---|
| AI citations that come from **earned media**, not your own domain | **82–96%** | `[external-ahrefs-75000-brand-study]` (96%), `[external-generative-engine-optimization-statistics-2026]` (82% earned / 6% owned, Muck Rack Dec 2025) |
| Brand-mention vs backlink correlation with AI visibility | **0.664 vs 0.218** (~3× stronger) | `[external-ahrefs-75000-brand-study]` |
| Strongest single predictor of AI visibility | **YouTube mentions, r=0.737** | `[external-ahrefs-75000-brand-study]` |
| Cited URLs that sit **outside** the organic top-10 | **76.95%** | `[external-schema-sameas-entity-disambiguation-ai-citations]` |
| Google AI Overviews appearance rate (2026) | **47–64% of all queries** (up from 25–30% in 2024) | `[external-google-ai-overviews-ai-mode-ranking-factors-seo-]` |
| Adding statistics to copy → citation likelihood | **+~41%** | `[external-generative-engine-optimization-statistics-2026]`, `[external-generative-engine-optimization-princeton-playboo]` |

**The re-strategization, in one line:** *stop grading the ~4–18% we control (own-domain, Layer A) green next to a zero-executed ~82–96% (earned, Layer B). Measure reality first (competitors, queries, live SOV), deepen the four pillars into dated/owned tactics, and open the programmatic-calculator surface.*

**What stays (build on, do NOT rebuild):** the 6 green Layer-A gates, M1's answer-first openers + comparison table, GA4 live, IndexNow live (51 URLs submitted), the 45 `/learn` articles, and the two-layer A/B frame. V2 layers the deep competitive / measurement / programmatic / earned-authority work **on top**.

---

## 1. The re-weighted model — Layer A is the ticket, Layer B is the game

The A/B split was right; the **weighting** was inverted.

- **Layer A — On-site (the entry ticket, ~4–18% of citations).** Crawlability, schema, answer-first structure, static HTML, entity markup. This is *necessary but not sufficient*: it makes WorkHive **eligible** to be cited. It cannot, by itself, win citations — 82–96% come from off-site `[external-ahrefs-75000-brand-study]`. **Status: mostly shipped and gated. Keep it green; extend it for the calculator surface + entity layer. Do not keep polishing it as if it were the prize.**
- **Layer B — Off-site earned authority (the game, ~82–96%).** Brand mentions, Reddit/YouTube/community presence, G2/Capterra, PR, and a resolvable brand entity. This is where the score is actually won and where V1 did essentially nothing beyond a taxonomy. **Status: unexecuted. This is the center of V2.**

**Corollary — the entity gate.** *Entity resolution runs BEFORE content retrieval; brands that fail entity resolution are excluded from citation eligibility* `[external-schema-sameas-entity-disambiguation-ai-citations]`. So a resolvable WorkHive entity (Organization schema + `sameAs` to Wikidata/LinkedIn/Crunchbase/GitHub) is a **precondition** for *any* of the other work to pay off. It moves to the front of the queue.

---

## 2. Pillar 1 — Competitive + query intelligence (do FIRST; it grounds everything)

### 2.1 The competitor landscape (the teardown V1 never did)

The maintenance-software market WorkHive competes in for AI citations `[external-cmms-software-competitor-landscape-2026-independ]`, `[external-best-free-cmms-software-2026-free-tier-competito]`:

| Competitor | Positioning | Entry price | Free tier |
|---|---|---|---|
| **MaintainX** | Mobile-first, real-time comms | $20/user/mo | Freemium (limited) |
| **Limble** | Full-lifecycle asset mgmt | Custom | Freemium (basic) |
| **UpKeep** | Manufacturing compliance / audit-readiness | $20/user/mo | Freemium |
| **Coast** | Best value, small teams | $20/user/mo | Freemium |
| **Fiix** | Rockwell/Fluke ecosystems, AI insights | $45/user/mo | Freemium |
| **eMaint** | Fluke condition-monitoring integration | $69/user/mo | No |
| **Tractian** | AI predictive + sensor hardware | $60/user/mo | No |
| Maintenance Care | 3rd-party integrations | — | Freemium |

**The wedge (WorkHive's uncontested angle):** every "free" competitor is **freemium** — a capped free tier that funnels to paid seats. WorkHive is **genuinely free + offline-first + Philippines-local + bilingual (Taglish)**. None of the incumbents own "free forever," "works offline on the plant floor," or "Philippines" — those are **uncontested citation territory**, and AI-citation sets are narrow (3–6 domains per query `[external-ai-search-citation-analysis-2026-domains-ranked-]`), so owning a narrow, specific query beats fighting for a crowded head term.

**Where competitors win today:** the SaaS vertical cites **G2 and Reddit** `[external-ai-search-citation-analysis-2026-domains-ranked-]` — i.e. the incumbents win AI citations through *earned* surfaces (review sites, community threads), not their own marketing pages. That is the exact battlefield, and it is a Layer-B battlefield.

### 2.2 The query taxonomy (real demand, not existing URLs)

V1 built queries from the pages it had written. V2 builds them from **buyer demand**, using the 6 revenue-first BOFU keyword types `[external-saas-keyword-research-revenue-first-process-sql-]`:

1. **Competitor alternatives** — "free alternative to UpKeep," "MaintainX alternative"
2. **Product vs product** — "MaintainX vs Limble vs Fiix for a small plant"
3. **Best-for-use-case** — "best CMMS that works offline," "best free maintenance app for a small factory"
4. **Best-for-industry** — "best maintenance software for food & beverage plants Philippines"
5. **Best-for-customer-type** — "maintenance app for a 5-technician team"
6. **How-to-solve-problem** — "how to reduce unplanned downtime," "how to ditch the maintenance spreadsheet"

Plus the **prompt-intent shift** `[external-aeo-keyword-research-prompt-intent-guide-b2b-saa]`: buyers now type long, context-heavy prompts ("the top free CMMS for a <50-person Philippine factory that works offline and supports Tagalog"), not two-word keywords. Content must answer *granular scenarios*, and AI rewards **consensus + external validation** over raw domain authority — the "Surround Sound" strategy (be present everywhere buyers gather).

The concrete target list — with priority scores `(Volume × CPC)/KD` — lives in the playbook §1.

### 2.3 The de-biased measurement harness (SHIPPED this session)

`prompt_audit_queries.json` went **37 → 55 queries**, adding **18 demand-gap queries** (`demand_gap: true`, with `competitors` listed) whose `expected_cite` is **not** yet a WorkHive URL — competitor-comparison, category, head-term calculator, buyer-intent, and PH-local. `_meta.engines` synced to the harness's real **5** engines `["chatgpt","perplexity","gemini","ai_overviews","claude"]`, and `prompt_audit.py` was aligned to the same 5 (it had silently omitted **AI Overviews**, the single highest-leverage surface). The harness now measures *real demand and the competitive gap*, not "do engines cite the page I already wrote."

---

## 3. Pillar 2 — Per-engine playbooks (each engine is a different game)

Only **11%** of cited domains overlap between ChatGPT and Perplexity (Averi, 680M citations); ~12% across three platforms `[external-ai-citation-11-percent-platform-overlap-per-engi]`, `[external-chatgpt-vs-perplexity-ai-visibility-citations-tr]`. A single "get cited" bucket is malpractice. Per-engine `[external-ai-platform-citation-patterns-per-engine-chatgpt]`, `[external-ai-platform-citation-source-index-2026-the-50-we]`, `[external-google-ai-overviews-ai-mode-ranking-factors-seo-]`:

| Engine | Reach / why it matters | Top source it leans on | The WorkHive move |
|---|---|---|---|
| **Google AI Overviews** | 47–64% of ALL queries; 30–50% CTR drop for #1; verticals hit 70%+ | **Reddit + YouTube + LinkedIn**; mirrors traditional SERP | Win the classic SERP AND be present on Reddit/YouTube; LinkedIn company presence matters more here than elsewhere. Structured data + answer-first + comparison tables. |
| **ChatGPT** | 900M weekly users, 87.4% of AI referral traffic, 15.9% conversion; ads since Feb 2026 | **Wikipedia (47.9% of its top-10)**; 80% `.com`, 48.7% from 3rd-party listings; mentions brands 3.2× more than it links them | Get a Wikipedia/Wikidata entity; get onto 3rd-party listicles ("best free CMMS" roundups); brand mentions matter even without links. 67% of its top-cited pages are off-limits to brand SEO — so **earned, not owned**. |
| **Perplexity** | 21.9 citations/response (vs ChatGPT 10.4); 10.5% conversion; academic lean | **Reddit (46.7% of its top-10)** | **Freshness is the lever: Perplexity cites content updated within 30 days 82% of the time** — feed it the refresh cadence (§4.3) + Reddit presence. |
| **Gemini** | Google ecosystem | **Google properties** (YouTube, Business Profile) | YouTube long-form + Google Business Profile + the same AI-Overviews on-page work. |
| **Claude** | In our own SOV set; conservative citer | reference + primary sources | Clean, well-structured, citation-worthy pages + entity resolution. |

**Cross-engine constants** (do these regardless of engine): lead with a number/definition/named framework; dense comparison tables with consistent columns; original research with stated methodology + sample size; first-hand-experience content on Reddit `[external-ai-search-citation-analysis-2026-domains-ranked-]`. **Linkability beats authority** — quotable data points and extractable tables get cited more than "authoritative" prose.

Per-engine asset checklists (what to build for each) are in the playbook §2.

---

## 4. Pillar 3 — Content architecture + the programmatic calculator surface

### 4.1 The technical crux (why the calculators are currently worth ~0 for AI)

**AI crawlers fetch JavaScript files but do NOT execute them** `[external-ai-crawlers-fetch-but-do-not-execute-javascript-]`. ChatGPT and Claude render nothing; only Googlebot/AppleBot render JS; Common Crawl (CCBot, which feeds many models) does not. The 58 calculators live in `engineering-design.js` — a **client-side, `noindex` JS app**. To an AI crawler they are a blank page. **Every worked example, every result, must exist in static HTML** — computed server-side or pre-rendered, not in JS. This single fact is why the calculator surface is the biggest untapped lever *and* why it needs a specific build, not just a nav link.

### 4.2 The programmatic calculator surface (the biggest new lever)

WorkHive owns **58 calculator engines** (`python-api/calcs/`) across 6 disciplines — a Zapier/Wise-class programmatic surface `[external-programmatic-seo-strategy-calculator-tool-pages-]` (Wise: 54M monthly visits, 90% from currency-conversion calc pages; Zapier: 70k+ programmatic pages). The inventory:

- **Electrical & Power (15):** transformer_sizing, generator_sizing, ups_sizing, power_factor_correction, short_circuit, voltage_drop, wire_sizing, cable_tray_sizing, load_estimation, load_schedule, harmonic_distortion, earthing_grounding, lightning_protection, lighting_design, solar_pv
- **Plumbing & Sanitary (13):** pipe_sizing, water_supply_pipe, domestic_water, hot_water_demand, drainage_pipe_sizing, sewer_drainage, storm_drain, roof_drain, septic_tank, grease_trap, wastewater_stp, water_treatment, water_softener
- **Mechanical & Machine Design (11):** beam_column, bearing_life, bolt_torque, gear_belt_drive, heat_exchanger, hoist_capacity, pressure_vessel, shaft_design, vibration_analysis, fluid_power, noise_acoustics
- **HVAC & Cooling (9):** hvac_cooling_load, duct_sizing, chiller, cooling_tower, ahu_sizing, fcu_selection, ventilation_ach, refrigerant_pipe, expansion_tank
- **Fire Protection (5):** fire_sprinkler, fire_pump, fire_alarm_battery, clean_agent_suppression, stairwell_pressurization
- **Boiler/Steam + Utilities (3):** boiler_steam, boiler_system, compressed_air
- **Vertical transport + pumps (2):** elevator_traffic, pump_tdh

**The spec** (three-part programmatic framework `[external-programmatic-seo-pages-step-by-step-implementati]`): one **static-HTML** landing page per calculator at `/tools/<calc>-calculator/`, each:
- **answer-first** — the formula + a fully worked numeric example in the HTML (not JS-computed);
- **schema'd** — `SoftwareApplication` (+ `HowTo` for the worked steps, `FAQPage` for the Q&A block);
- self-referencing canonical, listed in a **dedicated programmatic sitemap**, linked from the pillar + the live app tool;
- deployed in **stages of 50–200** (we have 58 — one clean batch) to respect crawl budget;
- **genuine utility per page** (Google penalizes thin template-only pages) — real formula, real worked numbers, real PH-context notes.

Full page template + the gate design are in the playbook §3 and Pillar-3 build (§7 of this doc's execution sequence).

### 4.3 Topic-cluster architecture over the 45 existing articles

Content clusters lift organic traffic ~40% via topical authority; pillar pages 3,000–5,000 words, cluster pages 1,500–2,500, every cluster linking back to its pillar with keyword-rich anchor text `[external-topic-cluster-pillar-page-topical-authority-cont]`. The 45 articles map to **~8 clusters** (full map + gaps + the missing pillar pages in playbook §3.3): Reliability & Metrics · Getting-Started/Digital-Logbook · Predictive & Condition-Monitoring · Planning & Scheduling · Skills & Career (OFW) · PH-Compliance · AI-Companion · Platform/Ecosystem — plus **Engineering Calculators**, which today has **one** article for 58 calcs (the gap Pillar 3 fills).

**Refresh cadence** `[external-content-refresh-cadence-topical-authority-freshn]`: prioritize pages at GSC positions **3–20** (a refresh moves them faster than a new URL), update pillars first, add fresh facts/stats/entities, measure at **30/60/90 days**. This directly feeds Perplexity's 30-day freshness bias (§3).

---

## 5. Pillar 4 — Off-site authority execution (the 82–96%, named + dated)

The target list is not a guess — it is the **measured** AI-citation domain ranking `[external-ai-platform-citation-source-index-2026-the-50-we]`: the top 15 domains capture **68%** of consolidated AI citation share; the top 10 are **Reddit, Wikipedia, YouTube, LinkedIn, Forbes, Amazon, Business Insider, TechRadar, Reuters, NYT**, and for **SaaS specifically, G2 + Reddit** `[external-ai-search-citation-analysis-2026-domains-ranked-]`. Priorities, in order of correlation strength:

1. **Brand entity first (precondition).** Organization schema + `sameAs` → **Wikidata → Wikipedia → LinkedIn → Crunchbase → GitHub**, with **identical name, canonical URL, description** across all `[external-schema-sameas-entity-disambiguation-ai-citations]`. Wikidata item is achievable now (needs ≥1 valid sitelink or serious public references `[external-wikidata-notability-criteria-create-item-company]`). *A broken `sameAs` is worse than none.*
2. **Reddit** (single most-cited domain, ~40% of multi-engine aggregate; #1 for Perplexity + AIO). Play the **90/10 rule** — 90% genuine help, ≤10% self-mention, disclose founder affiliation, honest conversational tone, never multi-account `[external-reddit-self-promotion-rules-2026-90-10-avoid-ban]`, `[external-reddit-as-ai-citation-source-seo-how-brands-get-]`. Named subreddits + first-post drafts in playbook §4.
3. **YouTube** (r=0.737, strongest predictor; 2nd-biggest social source). **94% of AI citations go to LONG-FORM, not Shorts**; timestamped chapters get cited repeatedly (78%); views/likes near-zero correlation `[external-youtube-seo-ai-citation-study-2026-description-c]`. So: a few structured, chaptered, long-form explainers > many Shorts.
4. **G2 / Capterra** (the SaaS-vertical citation winners) — claim the category, seed first reviews.
5. **Digital PR / linkable assets** — original research (e.g. "PH plant OEE benchmarks"), whitepapers, the calculator suite itself as a linkable asset; quality > quantity, niche-authoritative, natural anchors `[external-digital-pr-linkable-assets-b2b-saas-earn-backlin]`.
6. **YouTube/LinkedIn presence for AI Overviews + Gemini** (Google properties bias).

Google Business Profile is a **minor** lever for a SaaS (LocalBusiness is optional); the harvested GBP chunk drifted to a cookie-wall and is not cited. Named targets, contacts, and cadences are all in playbook §4.

---

## 6. Measurement — the feedback loop V1 never closed

- **First live SOV baseline** — the 55-query × 5-engine harness. The free-tier LLM chain **cannot** substitute (it has no web-RAG); this is an **Ian-gated manual run** (or the paid tool below). Prep + a priority-subset template are in the playbook §5. This produces the first real GEO/AEO number — everything before it was a self-estimate.
- **Share of Model (SoM)** `[external-ahrefs-75000-brand-study]` + **citation velocity** (how fast we enter new AI surfaces `[external-ai-search-citation-analysis-2026-domains-ranked-]`) become the real KPIs, replacing code-state %.
- **GSC + Bing** feed real impressions/queries into Pillar 1 (project memory notes both live since 2026-05-17; re-confirm sitemap + AI-Overview impression tracking).
- **Tooling path:** the DIY harness is the free substitute; **Frase** ($39/mo, prompt-level SoV vs chosen competitors, MCP/CLI, crawler log) is the paid upgrade if budget appears `[external-ai-visibility-tracking-tools-2026-profound-peec-]`; Profound is the enterprise tier.

---

## 7. The re-defined scoreboard — from code-% to observed-outcome-%

V1 graded code it controlled. V2 grades **observed reality**. Honest starting truth: the earned metrics start at **~0 (never measured)**; that is not failure, it is the baseline the program now moves.

| Axis | V1 (self-graded code) | V2 metric (observed) | Baseline | 90-day target |
|---|---|---|---|---|
| **Layer-A hygiene** | "SEO ~90" | Gates green + calc surface indexable + entity resolvable | 6 gates green; calc surface 0; entity 0 | 8 gates green; 58 calc pages live; entity resolved |
| **AEO (on-page answerability)** | "~55" | Answer-first + stat-rich + schema coverage across pillars | M1 done (5 articles) | all 8 pillars answer-first + stat-rich |
| **GEO (earned citation share)** | "~32" | **Live SOV cited-rate** across 55×5 | **unmeasured → establish** | measurable SoM > 0, rising velocity |
| **Off-site authority** | taxonomy only | brand mentions + Reddit/YouTube/G2 presence + entity | ~0 | entity resolved; Reddit 90/10 active; 3 long-form videos; G2 claimed |

**"Done" is defined by the whole board, not one green axis** — and no axis is "done" until it is *observed*, not *asserted*.

---

## 8. Execution sequence (what happens next, in order)

1. **Entity layer first** (precondition for everything): Organization schema audit + `sameAs` targets + Wikidata draft + LinkedIn/Crunchbase/GitHub consistency. *(playbook §4.1)*
2. **Programmatic calculator surface**: static-HTML `/tools/<calc>-calculator/` generator + template + schema + gate + sitemap; batch all 58. *(playbook §3, this doc §4.2)*
3. **Pillar pages + cluster links**: build the ~8 missing pillar pages, wire cluster back-links, start the 3–20-position refresh queue. *(playbook §3.3)*
4. **Off-site kickoff**: Reddit 90/10 presence, first long-form YouTube explainer, G2/Capterra claim, first linkable asset (PH OEE benchmark study). *(playbook §4)*
5. **First live SOV baseline** (Ian-gated) → first real GEO number → recompute the scoreboard from observation.

**Ian-gated inputs this unlocks** (the plan preps each so they become fill-in-the-blank): profile URLs + bio (`sameAs`/Person), registered address (optional LocalBusiness), GSC/Bing re-confirm, the live SOV run, and the outward off-site posting. Everything else is local and proceeds.

---

_Sources: 42 `substrate/external/` chunks. Regenerate/refresh with `tools/night_crawler.py`; verify freshness with `tools/validate_night_crawler_freshness.py`. This doc is the strategy; `seo_assets/TACTICAL_PLAYBOOK_V2.md` is the execution._
