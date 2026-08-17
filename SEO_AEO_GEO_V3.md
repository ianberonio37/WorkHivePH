# WorkHive Search Optimisation — V3, the five-pillar roadmap

**Status:** supersedes `SEO_AEO_GEO_STRATEGY_V2.md` as the strategy doc. It does **not** replace shipped code; V2's build log stands.
**Built:** 2026-08-05 · **Evidence spine:** 215 `substrate/external/` chunks (freshness gate green).
**Companion:** `seo_assets/TACTICAL_PLAYBOOK_V2.md` §6 (SXO) and §7 (AIO).

> Every non-obvious claim cites its chunk as `[external-<slug>]`. Retrieve any with
> `python tools/night_crawler.py --query "<topic>"` (0 crawl).

---

## 0. Why a V3

V2 was right about *what* was wrong (a self-graded code half bolted to an unexecuted earned half) and it fixed a great deal. But it carried **three** pillars, and the field now runs on **five**. Two consequences followed, and both turned out to be load-bearing rather than semantic:

- **AIO was folded into GEO**, as if "does any model cite us" and "do we appear in Google's AI Overview" were one game. They are not. AI Overviews mirror the classic SERP and appear on **47–64% of queries** `[external-google-ai-overviews-ai-mode-ranking-factors-seo-]`; a chat model's corpus behaves differently. Collapsing them hid the one lever neither shares: **multi-source credibility**, which no amount of our own content can supply.
- **SXO did not exist at all** — no doc, no metric, no gate. Nothing owned what happens *after* the click.

Auditing those two absences against the tree found four defects in code that is committed and deploy-bound. They are the reason V3 exists rather than a V2 edit.

### What the audit found

1. **All 60 calculator pages ship with no CSS, no header, no footer, no fonts.** 9.5KB of bare markup against 27–42KB for a `/learn` page carrying the site template. A visitor from Google lands on unstyled browser-default HTML — no WorkHive branding, no navigation onward. Newest and largest section of the site.
2. **`indexable_pages()` returns 58 surfaces and contains none of the 60 calculator pages.** Three gates derive their surface list from it — `seo_technical_gate`, `cwv_gate`, `orphan_depth_gate`. So "the SEO gates are green" is a statement about **58 of 119 URLs**. The largest new section is unseen by every established SEO instrument; only `calc-pages` (written this session) watches it.
3. **`validate_mobile.py` does not scan `/learn` or `/tools`.** It targets app pages. The entire public content surface has never been checked for mobile UX — for a product whose users are on phones in plants.
4. **No trust-signal or CTA instrument exists** anywhere in the gate set.

Defect 2 is the structural one. A gate that derives its surface from a catalog is only as honest as the catalog, and ours stopped at `/learn`. **V3's rule: a pillar is graded by an instrument whose surface list is derived from `sitemap.xml`, not from a subset that predates the content.**

---

## 1. The five pillars at a glance

| # | Pillar | The question it answers | State | Gate |
|---|---|---|---|---|
| 1 | **SEO** | Do we rank on traditional engines? | Strong; **now gated over 119/119** (was 58) | `seo`, `seo-technical`, `sitemap-sync`, `orphan-depth` |
| 2 | **AEO** | Are we the direct answer? | Present everywhere, **depth uneven** | `extractability` (+ proposed answer-quality) |
| 3 | **GEO** | Do the models reference us? | Built, **unmeasured + entity-blocked** | live SOV (Ian-run) |
| 4 | **AIO** | Do we appear in AI Overviews? | *New pillar* — partial by accident | proposed `aio-readiness` |
| 5 | **SXO** | Is the page good once they arrive? | *New pillar* — **P0 shipped**; CTA still ungated | `page-shell` (built), `cwv` |

---

## 2. SEO — rank on traditional engines

**What it means here.** Crawlability, indexability, canonical hygiene, internal-link structure, sitemap truth. The entry ticket: it makes us *eligible*, it does not win citations.

**Measured state.** 119 sitemap URLs, all resolving (`sitemap-page-existence` green). `robots.txt` names 23 user-agent tokens including the three independent Anthropic bots. Self-referencing canonicals throughout; `BreadcrumbList` on 113/114 pages (homepage correctly excluded). 119 markdown twins with an anti-drift gate. 715 internal links, 0 broken.

**Gap.** The scope defect is **fixed** — `indexable_pages()` is sitemap-derived, so all three gates now cover 119/119 (was 58). What remains: nothing is deployed, and GSC/Bing are unwired, so every SEO figure is still *code state* rather than observation. That is V2's original sin surviving in the one pillar we call strong.

**90-day target.** `indexable_pages()` derived from `sitemap.xml` → all three gates cover 119/119. Deployed; GSC + Bing reporting real impressions.

**The gate.** `seo`, `seo-technical`, `sitemap-sync`, `sitemap-page-existence`, `orphan-depth` — all green, **and provably scoped to the full sitemap**.

---

## 3. AEO — be the direct answer

**What it means here.** A question-shaped opener a machine can lift whole, `FAQPage` behind it, and a zero-click posture: assume the answer is read *in the result*, not on our page.

**Measured state.** 113 pages carry an answer-first block; `FAQPage` on all 114 content pages; JSON-LD parses on 114/114. `extractability` enforces the Princeton triad (answer-first + statistic + cited source) and is green. Stat-rich content raises citation likelihood **~41%** `[external-generative-engine-optimization-statistics-2026-a]`.

**Gap.** The gate proves an answer-first block *exists*; it cannot tell a good one from a placeholder. The stat-rich retrofit only ever covered M1's five articles. And the citation-correction round showed the real risk is not absence but **wrong confidence** — a fabricated DOE attribution passed every gate we had.

**90-day target.** Every pillar and comparison opener carries a number, a unit, and a named source. Zero unverifiable quantitative claims.

**The gate.** `extractability`, plus a proposed **answer-quality** check: the opener must contain a digit, a unit, and a proper noun — presence is not quality.

### 3a. Resolved — `FAQPage` / `HowTo` after Google retired the rich results

**The one place where the five-pillar chart and this codebase directly disagreed. Decided 2026-08-05: keep the schema, teach the gate.**

The chart lists "FAQ schema" as an AEO lever. Google **retired FAQ rich results (2026-05-07)** and HowTo rich results (2023) `[external-google-drops-faq-rich-results-structured-data-de]`, and `seo_technical_gate` encodes that as a **ratchet** — `retired_schema`, baseline 58.

Building this session's 8 new `/learn` pages with `FAQPage` pushed that ratchet **58 → 66**, so the gate is red and the regression is ours. The 60 calculator pages emit `FAQPage` *and* `HowTo` as well; they do not appear in the count only because they sit outside `indexable_pages()` (defect 2), so the true figure is higher than 66.

Both positions are defensible, which is why this needs deciding rather than assuming:

- **Retire the markup.** The rich result is gone; the schema now costs bytes and breaks a deliberate ratchet. Keep the Q&A as body content, which is what the gate's own message advises.
- **Keep it.** "No longer produces a rich result" is not "no longer read." The Q&A remains visible content (Google's structured-data policy is satisfied), and the markup is aimed at AI extraction — the AEO/GEO pillars — not at a SERP decoration.

**Decision: keep the markup.** Its audience is AI extraction, not a SERP decoration, and the Q&A is real visible content so Google's structured-data policy is satisfied. The original arc had already recorded the prune as *"optional given mixed evidence"* — this resolves that.

**How it was implemented — the gate was taught, not bent.** `retired_schema` became an **INFO census** in `tools/seo_technical_gate.py`: it still counts every occurrence (so the number is there if the decision is ever reversed) but it can no longer fail the build, and it prints the reason it exists. `jsonld_valid` remains the failing check, because *that* is the one measuring whether the markup actually works.

**It was explicitly not re-baselined.** Accepting the ratchet up to 66 would have silently lowered a floor the project set on purpose — `feedback_a_ratchet_that_turns_both_ways`. Gate now passes with `retired_schema: 66 (census)`; self-test 6/6.

---

## 4. GEO — get referenced by the models

**What it means here.** Being the thing a model reaches for. Overwhelmingly an *earned* game: **82–96% of AI citations come from earned media, not your own domain** `[external-ahrefs-75000-brand-study]`, and brand mentions correlate with AI visibility ~3× more strongly than backlinks (0.664 vs 0.218).

**Measured state.** 4 comparison pages built (vs-pages cite at ~2.4× generic posts). Entity package drafted. SOV harness de-biased to 55 queries × 5 engines with 18 `demand_gap` entries. Off-site assets written.

**Gap.** Three, in dependency order:
- **`sameAs` is `[]`.** Entity resolution runs *before* content retrieval, and a brand that fails it is excluded from citation eligibility outright `[external-schema-sameas-entity-disambiguation-ai-citations]`. Everything downstream is blocked on this.
- SOV has **never run** — GEO has no observation at all.
- Off-site is drafted, unposted. Reddit and G2 punish automation, so it is Ian-only by nature.

**90-day target.** Entity resolvable in direct AI prompt tests; a first real SOV number; Reddit 90/10 active; G2 claimed.

**The gate.** Live SOV baseline (`geo_sov_audit.py --score`) + `night-crawler-freshness`.

---

## 5. AIO — AI Overviews and Copilot *(new pillar)*

**What it means here.** Google's AI Overview and Bing Copilot specifically. Split from GEO because the surface mirrors the classic SERP rather than a chat corpus — which means classic ranking still feeds it, and the levers are different.

**Measured state.** Partial, and partial *by accident* rather than by design — the topical and schema work was done for other pillars and happens to serve this one. Nothing has ever been measured against AI Overviews specifically.

**The four levers, reconciled to our evidence:**

| Lever | State | Note |
|---|---|---|
| Topical authority | **built** | 8 clusters, 3 pillar hubs, 17 bidirectional back-links |
| Semantic relevance | **largely built** | Article/FAQPage/HowTo/BreadcrumbList/ItemList/SoftwareApplication, 114/114 parsing |
| Entity optimisation | **blocked** | same `sameAs` dependency as GEO |
| **Multi-source credibility** | **missing** | the one lever our own pages cannot supply |

**Gap.** Multi-source credibility is the whole point and we have none of it. AI Overviews corroborate across independent sources; a cluster where every citation points back to workhiveph.com reads as a single unverified source. Our pillars cite standards bodies (SMRP, ISO, DOE, NFPA) — which is good — but no *independent third party* discusses WorkHive.

**90-day target.** Every pillar cites ≥2 independent external sources; ≥1 third-party listicle inclusion; the PH-OEE benchmark study published as a citable original asset.

**The gate.** Proposed **`aio-readiness`**: per cluster — pillar exists, schema complete, ≥2 independent external citations, entity resolvable. Fails on the last two today, honestly.

---

## 6. SXO — the experience after the click *(new pillar, largest gap)*

**What it means here.** Everything from the moment the visitor arrives: load speed, mobile fitness, obvious next action, and whether the page *looks* trustworthy. SXO is where the other four pillars are cashed in or thrown away — a citation that lands on a broken-looking page is worse than no citation, because it spends trust we earned elsewhere.

**Measured state.** Nothing owns this. No doc, no metric, no gate — and the audit shows why that mattered:

| Lever | State (P0 shipped 2026-08-05) | Evidence |
|---|---|---|
| Fast loading | **now in scope, being measured** | `indexable_pages()` 58 → 119; `cwv` correctly failed on 69 never-measured surfaces, probe run |
| Mobile-friendly | **viewport gated**; app-checks still app-only | `page-shell` asserts `width=device-width`; `validate_mobile.py` deliberately not extended (its safe-area/overscroll/animation checks false-positive on static content) |
| Clear CTAs | still no instrument | the one lever of the four with no gate |
| UX & trust signals | **FIXED** | 60/60 now carry CSS + header + footer + webfont; 9,594 → 16,858 bytes; locked by `page-shell` |

**Gap (as found).** The 60-page defect was the priority: committed, deploy-bound, and containing the best work of the session — real worked numbers computed at build time, standards citations, valid schema — presented as unstyled text. The content was right; the shell was missing.

**P0 shipped (commits `7ae1bb2c`, `f5d34258`).** The chrome lived inline in `build_pillar_pages._page`, so there was nothing to reuse — extracted to `HEAD_ASSETS` / `SITE_HEADER` / `site_footer()` and imported by both generators (proven a no-op on articles: a pillar page regenerates byte-identical at 27,239). `indexable_pages()` now derives from `sitemap.xml`, lifting `seo_technical`, `cwv` and `orphan_depth` from 58 to 119 surfaces. `page-shell` locks it, with teeth proven both directions.

**Still open:** the CTA instrument, and `cwv` coverage until the probe finishes.

**90-day target.** Every public page renders in the site shell; `cwv` and `mobile` both scoped to 119/119; CWV within 2026 thresholds; every page has one unambiguous next action.

**The gate.** Proposed **`page-shell`** (fails any sitemap page missing site CSS / header / footer), plus `cwv` and `mobile` re-scoped to the sitemap.

---

## 7. The scoreboard — observed, not asserted

The rule V2 established and V3 keeps: **no axis is done until it is observed.** Where a number is unobserved, the cell says so rather than estimating.

| Pillar | Instrument | Observed today | 90-day target |
|---|---|---|---|
| SEO | gate sweep | green over **119/119** URLs (was 58) | deployed, GSC + Bing live |
| AEO | `extractability` | green; answer-first on 113 pages | + answer-quality (digit·unit·source) |
| GEO | live SOV | **never run** | a real SoM number, rising |
| AIO | `aio-readiness` | not built; credibility **0 independent sources** | ≥2 per pillar + 1 listicle |
| SXO | `page-shell`, `cwv` | **60/60 shelled + gated**; cwv measuring 119 | CWV within 2026 thresholds; a CTA instrument |

---

## 8. Execution sequence

One at a time, in this order, for stated reasons.

**P0 · SXO — DONE.** Calculator pages restyled through the shared chrome; `page-shell` added and proven. `indexable_pages()` now sitemap-derived (58 → 119), removing the false green that let this ship unseen. Remaining: CWV measurement of the newly-in-scope surfaces, and a CTA instrument.

**P1 · AIO** — multi-source credibility on the pillars; build `aio-readiness`.

**P2 · AEO** — answer-quality beyond presence.

**P3 · SEO** — hold green at full scope; wire GSC/Bing at deploy.

**P4 · GEO** — Ian-gated by nature.

---

## 9. Ian-gated (unchanged, listed so it is never mistaken for local work)

1. **Create LinkedIn + Crunchbase, send the URLs** — highest leverage remaining; `sameAs` blocks both GEO and AIO entity levers.
2. **Deploy**, then `python tools/indexnow_submit.py --submit` (119 URLs; running it before deploy submits 404s).
3. **Post the off-site assets** — drafted in `seo_assets/offsite_kickoff_assets.md`.
4. **Run the first SOV baseline** — `prompt_audit.py`, 18 demand queries × 5 engines = 90 checks for the fast version.
5. **Decide the publish-ignore** for the 276 internal artifacts currently served (noindex makes them unindexable, not private).

---

_Sources: 215 `substrate/external/` chunks incl. the Princeton GEO paper (arXiv 2311.09735, KDD 2024), Google Search Central AI-features and structured-data policy, RFC 9309, the llms.txt spec, and vendor crawler documentation. V2 remains the record of what was built and why; V3 is the frame going forward._
