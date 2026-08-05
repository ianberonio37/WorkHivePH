# WorkHive SEO/AEO/GEO — Tactical Playbook V2 (the executable half)

**Companion to** `SEO_AEO_GEO_STRATEGY_V2.md` (the why/what). This is the how: fill-in-the-blank artifacts, named targets, templates, cadences. **[IAN]** marks a step needing your input or an outward action; everything else is local and buildable now.
**Built:** 2026-08-03 · grounded in the same 42 `substrate/external/` chunks.

---

> **Build status — 2026-08-05.** Everything in §1 (query board) and §3 (content architecture) is BUILT and committed locally, awaiting Ian's deploy: 60 calculator pages, 3 cluster pillars, 4 comparison pages, 1 problem guide, 17 cluster back-links, robots.txt AI-bot tokens, llms.txt rebuild. All 18 demand queries now have a page behind them. §2 (per-engine) is on-page work that rides on those pages. §4 (off-site) and §5 (live SOV) are Ian-only by nature — the assets are drafted, the posting is not automatable.


## §1 — Query target board (real demand, priority-scored)

Method: 6 revenue-first BOFU types `[external-saas-keyword-research-revenue-first-process-sql-]`, prompt-intent phrasing `[external-aeo-keyword-research-prompt-intent-guide-b2b-saa]`. Priority Score = `(Volume × CPC) / KD` — **[IAN]** fill Volume/CPC/KD from a keyword tool or GSC once wired; the **rank order below is the qualitative prior** (highest intent + lowest incumbent lock first). All 18 are already live in `prompt_audit_queries.json` as `demand_gap` queries.

| # | Query | BOFU type | Current winner (gap) | WorkHive asset to build |
|---|---|---|---|---|
| 1 | free alternative to UpKeep for a small maintenance team | competitor-alt | UpKeep/listicles | **BUILT** `/learn/workhive-vs-upkeep-free-cmms-comparison/` |
| 2 | MaintainX vs Limble vs Fiix for a small manufacturing plant | product-vs | review sites | **BUILT** `/learn/best-free-cmms-software-philippines/` |
| 3 | best free CMMS software 2026 | best-for-case | Coast/MaintainX freemium | **BUILT** `/learn/best-free-cmms-software-philippines/` |
| 4 | CMMS that works offline on the plant floor | best-for-case | **nobody owns it** | **BUILT** (covered in the comparison set) |
| 5 | cheapest CMMS software for a small factory | competitor-alt | UpKeep/Fiix | **BUILT** `/learn/best-free-cmms-software-philippines/` |
| 6 | best maintenance management software Philippines | best-for-industry | **nobody owns it** | PH-local pillar (first-mover) |
| 7 | CMMS vs Excel spreadsheet for maintenance tracking | how-to-solve | generic blogs | **BUILT** `/learn/cmms-vs-excel-spreadsheet-maintenance/` |
| 8 | how to reduce unplanned equipment downtime | how-to-solve | generic blogs | **BUILT** `/learn/reduce-unplanned-downtime-guide/` |
| 9 | preventive maintenance software for a small factory | best-for-case | incumbents | PM pillar |
| 10 | mobile maintenance app for plant technicians | best-for-case | UpKeep/MaintainX | mobile/PWA differentiator page |
| 11–15 | OEE / MTBF / pump-TDH / duct-sizing / motor-FLC **calculator** | head-term tool | scattered calc sites | **BUILT** — 60 pages incl. `/tools/oee-calculator/`, `/tools/mtbf-calculator/` |
| 16 | CMMS vendor Philippines with local support | best-for-industry | nobody | PH-local page |
| 17 | is there a free CMMS as good as UpKeep or MaintainX | recommendation | incumbents | **BUILT** `/learn/workhive-vs-maintainx-comparison/` + Reddit (§4.2) |

**The wedge terms (own these first — uncontested):** *free-forever · works-offline · Philippines · Taglish/bilingual.* AI citation sets are only 3–6 domains wide `[external-ai-search-citation-analysis-2026-domains-ranked-]`, so a narrow specific win beats a crowded head term.

---

## §2 — Per-engine asset checklists

Each engine is a distinct game (11% domain overlap `[external-ai-citation-11-percent-platform-overlap-per-engi]`). Build the asset each rewards:

**Google AI Overviews** (47–64% of queries `[external-google-ai-overviews-ai-mode-ranking-factors-seo-]`)
- [ ] Answer-first opener + comparison table on every pillar (mirrors traditional SERP)
- [ ] Reddit threads exist for the target queries (§4.2)
- [ ] ≥1 long-form YouTube explainer with chapters (§4.3)
- [ ] **[IAN]** LinkedIn company page active (matters more here)
- [ ] Structured data valid (SoftwareApplication + HowTo + FAQPage)

**ChatGPT** (Wikipedia-led; 67% of top-cited pages off-limits to brand SEO → earned)
- [ ] **[IAN]** Wikidata entity → Wikipedia eligibility (§4.1)
- [ ] Get onto 3rd-party "best free CMMS" listicles (48.7% of its citations are 3rd-party listings) — outreach in §4.5
- [ ] Brand mentions across the web (it mentions brands 3.2× more than it links them)

**Perplexity** (Reddit-led; **82% cites <30-day-fresh content**)
- [ ] Run the refresh cadence (§3.4) so pillars are always <30 days stale
- [ ] Reddit first-hand comparison threads (§4.2)
- [ ] Original data with methodology (academic lean)

**Gemini** (Google-properties bias)
- [ ] YouTube long-form + timestamps
- [ ] **[IAN]** Google Business Profile (minor, optional)
- [ ] Same AI-Overviews on-page work

**Claude** (conservative; reference + structure)
- [ ] Clean answer-first pages + entity resolution + citation-worthy tables

**Cross-engine constants:** lead with a number/definition/named framework; dense consistent-column comparison tables; original research with sample size; first-hand Reddit experience `[external-ai-search-citation-analysis-2026-domains-ranked-]`.

---

## §3 — Content architecture + the 58-calculator programmatic surface

### §3.1 The static-HTML calculator page template

**Non-negotiable:** AI crawlers don't execute JS `[external-ai-crawlers-fetch-but-do-not-execute-javascript-]` — the worked example must be in the HTML, not computed client-side. Use SSG `[external-programmatic-seo-pages-step-by-step-implementati]`.

```
URL:      /tools/<calc>-calculator/            (self-referencing canonical)
<title>   <Calc> Calculator — Free Online + Worked Example | WorkHive
H1        <Calc> Calculator
[answer-first block, in HTML]
   "To calculate <X>, use <formula>. Example: for <realistic PH inputs>,
    <X> = <worked number with units>."   ← the stat AI cites [+41% citation]
[the formula, rendered as text + one worked numeric example — static HTML]
[a short "how to" HowTo schema block: step 1..n]
[3–5 FAQ Q&A — FAQPage schema]
[CTA → the live interactive tool in the app (the JS calculator)]
[internal links: → discipline pillar, → 2–3 sibling calculators, → related /learn article]
JSON-LD:  SoftwareApplication + HowTo + FAQPage, every field real data
```

Deploy all **58 in one batch** (within the 50–200 crawl-budget guidance), in a **dedicated `/tools/` sitemap** referenced from `sitemap.xml`. URL slugs map 1:1 to `python-api/calcs/<module>.py`.

### §3.2 The 58 calculators → URL map (grouped; full list in strategy §4.2)

`/tools/oee-calculator/` and `/tools/mtbf-calculator/` are **highest-priority** (head-term demand, existing `/learn` support to link). Then the discipline batches: Electrical (15), Plumbing (13), Mechanical (11), HVAC (9), Fire (5), Boiler/Utilities (3), Vertical-transport/Pumps (2). *(OEE/MTBF are computed KPIs surfaced in-app, not in `/calcs/` — add them as two hand-authored `/tools/` pages alongside the 58 engine pages.)*

### §3.3 Topic-cluster map (45 articles → 8 clusters) + missing pillars

| Cluster | Existing articles (sample) | Pillar page status |
|---|---|---|
| Reliability & Metrics | mtbf-vs-mttr, what-is-oee, rcm, fmea-worked-example, power-plant-reliability-metrics, predictive-alert-thresholds, four-phases-analytics | **MISSING — build "Maintenance Metrics & Reliability" pillar** |
| Getting-Started / Digital Logbook | start-digital-logbook, building-asset-register, shift-handover-template, free-pm-checklist | **MISSING — build "Start Digital Maintenance" pillar** |
| Predictive & Condition-Monitoring | predictive-maintenance-on-a-budget, vibration-analysis-phone, thermography, sensor-cmms-gateway | partial (pdm-budget can anchor) |
| Planning & Scheduling | dilo-wilo, project-planning-template, autonomous-shift-planning | partial |
| Skills & Career (OFW) | skill-matrix, tesda-nc-mapping, ofw-portable-portfolio, resume-builder, psme-iiee-piche | partial (skill-matrix anchors) |
| PH-Compliance | dole-iso-audit-trail, loto-procedures-dole-oshs, ra-11285-energy | **MISSING — build "PH Plant Compliance" pillar** |
| AI-Companion | ai-work-assistant, ai-companion-personas, companion-capabilities, ai-quality-roi, voice-to-text | partial (capabilities anchors) |
| Platform/Ecosystem | what-is-workhive-guide, marketplace, community, joining-hive, gamifying, alert-inbox | what-is-workhive-guide = pillar |
| **Engineering Calculators** | free-engineering-calculators (ONE article for 58 calcs) | **build pillar → link all 58 `/tools/` pages** |

Every cluster page must link its pillar with keyword-rich anchor text; pillars 3,000–5,000 words, clusters 1,500–2,500 `[external-topic-cluster-pillar-page-topical-authority-cont]`.

### §3.4 Refresh queue (Perplexity's 30-day freshness lever)

`[external-content-refresh-cadence-topical-authority-freshn]` — once GSC is wired: rank all 45 articles by GSC position; **refresh positions 3–20 first** (fastest to page 1), pillars before clusters, add fresh stats/entities each pass, measure at 30/60/90 days. Until GSC data lands, refresh the 8 pillars on a rolling 30-day cycle so Perplexity always sees <30-day content.

---

## §4 — Off-site authority (the 82–96%): named targets + cadence

### §4.1 Brand entity (PRECONDITION — do before everything; entity resolution gates citation eligibility `[external-schema-sameas-entity-disambiguation-ai-citations]`)

**Organization `sameAs` block** (add to homepage JSON-LD; identical name/URL/description everywhere):
```json
"sameAs": [
  "https://www.wikidata.org/wiki/<QID>",        // [IAN] create — §4.1a
  "https://www.linkedin.com/company/workhive-ph/", // [IAN] confirm/claim
  "https://www.crunchbase.com/organization/workhive", // [IAN] create
  "https://github.com/<workhive-org>"            // [IAN] confirm
]
```
- **Priority order:** Wikidata → Wikipedia → LinkedIn → Crunchbase → GitHub. *A broken `sameAs` is worse than none* — only list live, correct URLs.
- **§4.1a Wikidata item** `[external-wikidata-notability-criteria-create-item-company]`: needs ≥1 valid Wikimedia sitelink OR serious public references. **[IAN]** create the item (name "WorkHive", description "free offline-first maintenance management platform for Philippine industrial plants", official website, instance-of: software/company). This is the single highest-leverage precondition.
- Validate with Schema Markup Validator; re-test with direct AI prompts at 30/60/90 days.

### §4.2 Reddit (single most-cited domain; #1 for Perplexity + AIO) — 90/10 rule

Play `[external-reddit-self-promotion-rules-2026-90-10-avoid-ban]`: 90% genuine help, ≤10% self-mention, **disclose founder affiliation**, honest tone, one account. **[IAN]** targets to seed (join, read rules, help for 2–3 weeks before any mention):
- r/maintenance, r/CMMS, r/reliability, r/PLC, r/IndustrialMaintenance, r/manufacturing
- r/Philippines, r/phinvest, r/ProdEng, r/engineering (PH-context answers)
- **First-value posts (drafts to prep, not self-promo):** "How we do shift handover without paid software," "Free OEE calc method (with the formula)," "Offline logbook approach for spotty plant wifi." Mention WorkHive only when directly asked "what tool," and disclose.

### §4.3 YouTube (r=0.737, strongest predictor; long-form only)

`[external-youtube-seo-ai-citation-study-2026-description-c]`: **94% of AI citations go to long-form, not Shorts**; timestamped chapters cited repeatedly. **[IAN]** produce **3 structured long-form explainers** (8–15 min, chaptered, transcript-rich):
1. "How to calculate OEE / MTBF / MTTR (with worked examples)" → links the `/tools/` pages
2. "Setting up a free offline maintenance logbook for a small factory"
3. "CMMS vs spreadsheet: what a small plant actually needs"
Each: keyword title, chaptered description with timestamps, full transcript, link to the matching pillar. Views/likes don't matter for citation — structure does.

### §4.4 G2 / Capterra (SaaS-vertical citation winners)

**[IAN]** claim the WorkHive listing in the **CMMS / Maintenance Management** category on G2 + Capterra; seed the first 5–10 genuine reviews from real hive users. This is where SaaS AI-citations concentrate `[external-ai-search-citation-analysis-2026-domains-ranked-]`.

### §4.5 Digital PR / linkable assets

`[external-digital-pr-linkable-assets-b2b-saas-earn-backlin]`: quality > quantity, niche-authoritative, natural anchors. Build once, earn repeatedly:
- **Original research:** "Philippine Plant OEE Benchmarks by Sector" (we have `/learn/ph-industrial-benchmarks`) — turn into a citable data study with methodology + sample size (AI loves stat-rich original research).
- **The calculator suite** itself is a linkable asset once the `/tools/` pages are live.
- **[IAN]** outreach to: PH engineering associations (PSME/IIEE/PIChE), PH manufacturing/industry outlets, "best free CMMS" listicle authors (ask for inclusion).

### §4.6 Cadence summary

| Channel | Owner | Cadence | First action |
|---|---|---|---|
| Entity/`sameAs` | local build + **[IAN]** accounts | one-time + 30/60/90 re-test | Wikidata item |
| Reddit | **[IAN]** | 3×/week genuine, ≤10% mention | join + read rules |
| YouTube | **[IAN]** | 1 long-form/month | OEE/MTBF explainer |
| G2/Capterra | **[IAN]** | one-time claim + review asks | claim CMMS category |
| Refresh queue | local | 30-day rolling on pillars | refresh 8 pillars |
| PR asset | local + **[IAN]** | one study/quarter | PH OEE benchmark study |

---

## §5 — First live SOV baseline (Ian-gated) + measurement wiring

The free-tier chain has no web-RAG, so it cannot self-run the audit `[external-ai-visibility-tracking-tools-2026-profound-peec-]`. **[IAN]** options:
- **Manual:** `python prompt_audit.py` walks all 55 queries × 5 engines (275 checks — heavy). **Recommended first pass: the priority subset** — the 18 `demand_gap` queries × 5 engines (90 checks) to establish the competitive-gap baseline fast, then expand.
- Or generate the structured template: `python tools/geo_sov_audit.py` (writes the results template), fill cited/mentioned/recommended/sentiment per cell, then `--score` it → first SoM/citation-rate numbers + `geo_sov_baseline.json`.
- **Paid path** (if budget appears): **Frase** $39/mo — prompt-level SoV vs chosen competitors, daily monitoring, crawler log.

**GSC + Bing:** project memory notes both live since 2026-05-17. **[IAN]** re-confirm the `sitemap.xml` (now 51 URLs; will grow when the `/tools/` sitemap lands) is submitted in both, and check GSC's AI-Overview impression breakdown.

---

## Definition of done (per the strategy scoreboard §7)

No axis is "done" until **observed**, not asserted. The board moves when: 58 `/tools/` pages live + indexed · entity resolvable in AI prompt tests · Reddit 90/10 active · 3 long-form videos up · G2 claimed · **a real SOV number exists**. That last one converts the whole program from self-estimate to measurement — the entire point of V2.
