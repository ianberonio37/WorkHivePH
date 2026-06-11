# Content Grounding Gate — the third sibling of the Unified Mega Gate

**Created:** 2026-06-10
**Owner:** Ian Beronio
**Status:** PLAN AGREED (this doc is the single source of truth — read first on resume). Build not started.
**Decisions locked:** v1 scope = **all outward surfaces in one push**; integration = **sibling front door `tools/content_dev.py` + `phase_content` in `release_gate.py`**.

---

## The ask (verbatim intent)

> "video marketing, SEO, AEO, GEO … especially everything on my landing page, seems static … this should all depend on what's in my platform, which is ever evolving … learning articles and so many more … it becomes outdated. How can we wire this into the unified mega gate, then tailor the same as the unified mega gate, so these won't be left out?"

The platform evolves; every **outward-facing** surface carries a baked-in snapshot of it and silently rots. We already solved this **inward** (`v_*_truth` canonical views stop in-app pages drifting from the DB — see `CANONICAL_SOURCES_AUDIT.md`). This is the **same move pointed outward**: one canonical **Platform Catalog** + a gate that fails on content↔platform drift, built as a self-improving closed loop **the same shape as the Mega Gate**.

## Three sibling gates, one philosophy

| Gate | Subject under test | Source of truth | "Drift" = |
|---|---|---|---|
| Unified Mega Gate (`release_gate.py`) | **code** | codebase + `v_*_truth` | a regression |
| Companion Dev Tool (`companion_dev.py`) | **AI behavior** | locked golden/eval splits | behavior regression |
| **Content Grounding Gate (`content_dev.py`)** ← NEW | **outward content** | the **Platform Catalog** | content ↔ platform drift |

---

## The keystone: the Platform Catalog (auto-derived, never hand-maintained)

One generated file `platform_catalog.json`, built by `tools/platform_catalog.py` from the platform's OWN artifacts (so it cannot drift from reality):

| Catalog section | Derived from (GROUNDED, real files) |
|---|---|
| **features[]** — id, canonical name, route/URL, one-line real capability, status (active/beta/deprecated), `connects_to` | `tools/platform_intel.py` `get_feature_info` + `connects_to`; the **nav registry** (`validate_nav_registry.py` / `nav_registry_report.json`); the actual page routes (`*.html`) |
| **articles[]** — slug, title, topic, features referenced, last-updated | the 36 `learn/<slug>/index.html` + `learn/index.html` hub |
| **public_surface** — index.html claims, sitemap URLs, `llms.txt`, JSON-LD `featureList`/FAQ/HowTo | `index.html`, `sitemap.xml`, `robots.txt`, `llms.txt`, schema blocks (also in project-report.html, plant-connections.html) |
| **counts** — #tools, #articles, #FAQs (the numbers content asserts) | derived from the above |

Everything downstream **reads the catalog** instead of carrying its own copy. (The video storyboard's hard-coded `FEATURE_KEYWORDS` / `FEATURE_NAME_TO_KEY` / `JOURNEY_URLS` in `tools/storyboard.py` ARE the drift bug — they get replaced by catalog lookups.)

## Surfaces under test (all, one push)

1. **Landing page** — `index.html`: feature claims, tool/article counts, hero answer-first block, JSON-LD.
2. **/learn articles** — 36 pages: features referenced still exist+named correctly; internal links resolve; last-updated freshness; schema valid.
3. **SEO / AEO / GEO** — `sitemap.xml` completeness, `robots.txt`, `llms.txt`, JSON-LD `featureList ⊆ catalog`, `FAQPage`/`HowTo` validity (per `SEO_AEO_GEO_ROADMAP.md`).
4. **Video marketing** — idea/script/storyboard/journey grounded in the catalog (the work already in flight; see `project_video_storyboard_narration_2026_06_10`).

---

## Tailored layer-for-layer to the Mega Gate

| Mega Gate layer | Content Grounding Gate equivalent | Output |
|---|---|---|
| **G-1.5 Substrate** (9 miners→manifest) | derive Platform Catalog + scan every surface | `content_substrate_manifest.json` |
| **G-1 Auto-discovery** (coverage) | map each content artifact ↔ facts it asserts; flag **orphans** (claims with no catalog backing) + **gaps** (catalog features with no content = SEO opportunity + coverage metric) | discover report |
| **G0 Static** (drift validators) | every named feature exists+active; every asserted count == live; every internal link resolves; `featureList ⊆ catalog`; article freshness thresholds. **FAIL on drift**, ratcheted baselines | per-surface validators |
| **G1 Data** | live counts (tools/articles/FAQs) vs filesystem/DB | data checks |
| **G2 Journeys** | crawl public + `/learn` (Playwright / `crawl4ai`): answer-first present, schema validates, 0×404, CWV OK | journey report |
| **G3 Battery / Optimize** | drift → **harvest** a regeneration candidate → human-dispose → **regenerate** via existing generators; forward-only | candidates + regen |
| **Mega** | `content_dev.py mega` + `phase_content` in `release_gate.py`; 4-axis scorecard | `.last-content-gate-pass` |

### Drift taxonomy the gate catches
- **Feature drift** — content names a renamed/removed/rescoped feature.
- **Capability drift** — content claims a capability the feature doesn't have (e.g. the AI-invented "AI Assistant alerts you to skill gaps").
- **Count/stat drift** — "23 tools" / "24 articles" no longer match live.
- **Link/route drift** — internal link points to a moved/404 page.
- **Schema drift** — JSON-LD `featureList`/FAQ out of sync with the product.
- **Freshness drift** — article last-updated older than threshold while its feature changed.

---

## Front door: `tools/content_dev.py` (mirrors `companion_dev.py`)

Subcommands: `status` · `substrate` (build catalog + manifest) · `discover` (coverage/orphans/gaps) · `gate` (run drift validators, n-aware, forward-only) · `harvest` (drift→candidates) · `dispose` (human promote/drop) · `regenerate` (drive `article_generator.py` / storyboard / schema builders) · `mega` (run all, write `.last-content-gate-pass` + scorecard) · `--self-test`.

**Plug into the unified gate:** add `phase_content()` to `release_gate.py` behind `--with-content` (exactly how `phase_battery` was added behind `--with-battery`), and a **Content Gate card** in the tester-panel cockpit (generic `/api/content/<layer>` SSE route, like the companion pane).

**4-axis scorecard:** freshness · coverage · correctness · grounding.

---

## Build sequence (all-surfaces push, but ordered so each phase is verifiable)

- **P0 — Catalog keystone.** `tools/platform_catalog.py` → `platform_catalog.json` (auto-derive from platform_intel + nav registry + routes + learn inventory + public surfaces). `--self-test`. *Done when the catalog enumerates every active feature with route+capability+status and every article/surface, derived (not hand-typed).*
- **P1 — Substrate + discover.** `content_substrate_manifest.json` + the coverage/orphan/gap map across all 4 surfaces.
- **P2 — Drift validators (G0/G1).** One validator per drift type per surface; ratcheted baselines registered in the gate.
- **P3 — Front door + gate phase + cockpit.** `content_dev.py` + `phase_content` (`--with-content`) + tester-panel card (no dead buttons; MCP-verify each streams a real job).
- **P4 — Self-improving loop (G3).** harvest drift → dispose → regenerate via `article_generator.py` / storyboard / schema builders; forward-only, human-on-judgment.
- **P5 — Riders.** Refactor `storyboard.py` to read the catalog (kill the hard-coded maps); add the **opt-in gTTS fallback** (`allow_fallback_voice`, clearly-labelled) so a produce completes during an Edge TTS outage.

## ALREADY BUILT — reuse, do NOT rebuild (discovered 2026-06-10)

A mature SEO/AEO/GEO layer already exists. The Content Grounding Gate **wraps and extends** it; it does not replace it.

| Existing asset | Covers | What it does NOT do (= the gap) |
|---|---|---|
| `validate_seo.py` | noindex on app pages, branded titles, canonical tags, OG/Twitter | doesn't check claims vs the live feature set |
| `validate_meta_description_coverage.py` (L0 ratcheted) | every public page has description/OG/canonical | structural presence only, not grounding |
| `validate_sitemap_sync.py` + `validate_sitemap_page_existence.py` | sitemap ↔ filesystem lockstep, lastmod, every page listed | structural, not "does the page still describe a real feature" |
| `validate_meta_gate.py`, `validate_meta_refresh.py` | meta gating/refresh | — |
| `validate_schema*.py` (`_drift`, `_coverage`, `_phantom`, `validate_schema.py`) | **DATABASE** schema (Supabase tables/columns in `db.from().select()`) — NOTE: these are DB-schema, **NOT** JSON-LD/Schema.org | so **JSON-LD `featureList`/FAQ vs live features is NOT yet checked** |
| `prompt_audit.py` (+ `prompt_audit_queries.json`) | GEO measurement — weekly AI-citation tracking (ChatGPT/Perplexity/Gemini/Claude) | manual/interactive; measures visibility, not content↔platform drift |
| `llms.txt` | rich GEO artifact: every feature + all 36 articles + key terms + audience doctrine | **HAND-MAINTAINED → itself a top drift candidate** (enumerates features/articles that must match live) |
| `SEO_AEO_GEO_ROADMAP.md` + phase docs (3/5/6) | the surface map + schema strategy (6 phases ready) | the roadmap, not a gate |

## What's genuinely NEW (the gap the gate fills)
1. **`platform_catalog.py` → `platform_catalog.json`** — the missing keystone: one auto-derived feature truth (each existing validator derives only its own slice — sitemap from FS, DB schema from migrations; none derives the *feature catalog*).
2. **Grounding-vs-live-platform validators** (the semantic layer the structural ones lack): feature-claim drift (index.html / `llms.txt` / articles / JSON-LD reference features that EXIST + are ACTIVE + correctly named); **JSON-LD `featureList ⊆ catalog`** (currently unchecked); count drift (#tools/#articles/#FAQs == live); article "Maps to WorkHive X" → X exists+active; `llms.txt` feature/article list == live; freshness (article older than its feature's last change).
3. **Unification + loop:** `content_dev.py` front door that RUNS the existing SEO validators **and** the new grounding validators together + `phase_content` in `release_gate.py` + cockpit card + 4-axis scorecard + harvest→dispose→**regenerate** (incl. auto-regenerating `llms.txt` and JSON-LD from the catalog via `article_generator.py`/schema builders).

**Also reuse:** `release_gate.py` + `phase_battery` pattern, substrate-manifest pattern, `ai_eval_gate`/discover, tester cockpit, `platform_intel.get_feature_info` + nav registry (catalog source), the video storyboard/journey.

## Guardrails (same antibodies as the other gates)
- **Auto-derive, never hand-maintain** the catalog (a hand-kept feature list IS the drift bug).
- **Discover/draft by machine; judge by human** — nothing auto-regenerates or auto-publishes without a dispose step.
- **Baselines ratchet down only; forward-only**; n-aware block; free-tier models only (`ai_chain`).
- **Two failure modes to keep distinct:** (1) generation-time grounding (content born wrong), (2) drift-over-time (correct content rots later) — the gate must catch both (the sweep re-checks the existing library, not just new output).

## Definition of done
A platform revamp (rename/add/remove a feature, change a flow, ship/retire an article) makes, **without a human mining or hand-editing**: the catalog update on next derive; every outward surface that referenced the change flagged as drift by the gate; a regeneration candidate queued for human dispose; the 4-axis scorecard reflect the dip — and after regen, the gate goes green again.

---

## Next layer — Capability / claim grounding (the provenance chain)  [added 2026-06-10]

**Status:** P0–P5 shipped + deepwalk-verified (catalog · substrate/discover · drift gate · front door/cockpit · loop · riders). This section specs the **next** layer, from Ian's refinement.

P0–P5 ground feature **identity** — does the feature *exist*, is it *named* right, does the *route* resolve, do the *counts* match (`feature_drift` / `count_drift` / `link_drift`). The deeper drift Ian observed lives one level down: **product claims** — the flow / how-to / capability / interconnection copy ("in WorkHive you tap X and it auto-generates Y") — which must trace to a real platform page **or they invent**. This is the `Capability drift` row already in the taxonomy above, now operationalized.

### The provenance chain (ground flows downward; each layer cites the one below)
```
PLATFORM PAGES  (the only ground truth: real UI, real flows, real interconnections)
   │ evidence extracted from the real DOM
   ▼
PLATFORM CATALOG  + per-feature EVIDENCE block   ← the capability source of truth
   │ grounds the product-claim half
   ▼
LEARN ARTICLES   (general knowledge  +  product how-to)
   │ grounds ideas + scripts
   ▼
VIDEO IDEAS / SCRIPTS
```
Correction to today's wiring: video ideas currently read `platform_intel.loop_role` (hand-written), and the catalog's `capability` field is that same copy — **two independent hand-authored sources that can each drift.** This layer collapses them: the **page is the source**, `loop_role` / landing copy / article how-to become *derived, checked claims* — not sources.

### Two claim classes (classify BEFORE grounding — this prevents false positives)
| Class | Provenance | Grounded vs platform? |
|---|---|---|
| **Domain / general knowledge** (OEE formula, ISO 14224, "PM prevents failures") | external standards | **No** — only checked for correctness; left general |
| **Product claim** (flow / how-to / capability / UI / interconnection) | the actual page | **Yes** — or it's invented |

Drift concentrates in the product-claim class. The classifier is the safety valve: it stops the gate "correcting" your ISO citations.

### New substrate — page evidence (`tools/page_evidence.py`)
Per feature page, extract from the real DOM/HTML the page's *actual affordances*: headings (h1–h3), button/CTA/`data-action` labels, form-field labels, real outbound links (the TRUE `connects_to`), section/output labels. Folded into the catalog as `feature["evidence"]`. Deterministic + offline (parses the `.html`); Playwright augments only for the e2e verification, never as a gate runtime dep.

### New drift check — `capability_drift` (in `content_grounding_gate.py`, ratcheted)
For each article + the landing page:
1. **Classify** each sentence: product-claim vs general-knowledge (heuristic: names a WorkHive feature/affordance + an action/capability verb → product; cites a standard / defines a term → general).
2. **Ground** each product claim against the mapped feature's evidence:
   - **Tier 1 — deterministic:** claimed affordance token ∈ evidence actions/headings; claimed interconnection ∈ evidence links/`connects_to`.
   - **Tier 2 — LLM-judge faithfulness (opt-in, free-tier):** given ONLY the evidence, rule each fuzzy flow claim `supported / unsupported / general` — the `faithfulness_smell` machine from `COMPANION_DEV_TOOL.md` (relevant-but-ungrounded = the invention tell).
3. An unsupported product claim = `capability_drift`. **Conservative:** prefer false-negative over false-positive — never flag general knowledge.

### Both ends of the chain
- **Generation-time** (born grounded): feed the article / idea / script generator the page evidence as the *only* product-claim source; require it to tag general vs product and **cite the page/flow per product claim** ("Grounded in: `/logbook.html`") — the product-half analog of the existing "Sources:" line.
- **Drift-time** (doesn't rot later): the gate re-checks the existing library's product claims against the *current* evidence on every platform change (the two failure modes — born-wrong + rotted-later — both heal here).

### Build sequence (each Playwright-deepwalked) — BUILT 2026-06-10
- **B1 ✅** `tools/page_evidence.py` → `page_evidence.json` (28 pages, 701 real affordances) + `--self-test`. Deepwalk: extracted evidence == rendered DOM (logbook "Log a Repair"/"Register Asset"/links-to voice-journal all real).
- **B2 ✅** `capability_drift` check in `content_grounding_gate.py` (CHECK_ORDER[8]). **Tier-1 deterministic** (conservative: flag a WorkHive-attributed capability claim whose distinctive content exists NOWHERE on the platform — 5 baselined, 0 false-positive on grounded prose). **Tier-2 opt-in LLM judge** (`use_llm=True` / `CONTENT_LLM_JUDGE=1`): pre-filter to ≥2 platform-absent tokens → per-sentence free-tier judge (reliable on focused/claim-dense text; batch index-mapping was not). Self-test teeth + Playwright flag↔absence both verified. **Honest boundary:** terse-UI-vocab vs descriptive-prose mismatch means token rules can't reliably catch a *mixed* real+invented sentence buried in a long article — there, born-grounded generation (B3) + the Tier-1 baseline are the defense; Tier-2 is for focused text.
- **B3 ✅** Grounding wired into the PRODUCTION `tools/article_generator.py`: the page-evidence affordances are injected into the per-section prompt as the only product-claim source, and `verify_grounding()` reports born-wrong claims. A real generated logbook article came out **born grounded (0 ungrounded, 1719 words)**.
- **B4 ✅** Grounding wired into `video_marketing_app/app.py` `_build_script_prompt` (`_evidence_block_for_feature`) + post-gen verify. Live: idea_015 → a **born-grounded script (0 ungrounded UI claims)**.
- **B5/B6 ✅** End-to-end through the LIVE pipeline: real article (born grounded) → gate grounds it → focused negative control (invented capability) flagged by Tier-2 → fresh idea + grounded script via the app → **full `produce-all`** (grounded script → voice → catalog-derived storyboard journey → background → recording → assembled mp4). Playwright confirmed the claimed affordances exist in the live page DOM.

Key files: `tools/page_evidence.py`, `content_grounding_gate.py` (`capability_drift`, `capability_issues_for_text`, Tier-2 judge), `tools/article_generator.py` (section-prompt grounding), `video_marketing_app/app.py` (`_evidence_block_for_feature`).

## Readability drift — padding is a drift class too (BUILT 2026-06-10)

**The lesson (resume article, first AI-scaffolded one):** the generator's old rules — 1500-word FLOOR ("if you hit 1300 you are NOT done"), `<p>`-only sections (`No <ul>, no <ol>, no <strong>`), the same 5 hand-listed PH props in every prompt, and per-section independent calls receiving the same affordance evidence — mathematically produced an overwhelming article: 26 dense paragraphs, the same control ('Auto-fill from my WorkHive data') walked through in 5 of 6 sections, zero tables/callouts/figures, plus topic-irrelevant sources (ISO 14224 on a resume article). Grounded ≠ readable. Research basis: NN/g (users read 20-28% of words; concise+scannable = 124% better usability), Infogram (dwell +62% with a data visualization).

### Two new ratcheted checks (CHECK_ORDER[9..10], same forward-only engine, synthetic teeth)
- **`affordance_repetition`** — an article that mentions the SAME real >=2-word control label in **3+ body sections** is padding, not teaching. Explain once, reference thereafter. (Body region = `prose-wh` → `id="faq"`, all 37 articles carry both markers.)
- **`wall_of_text`** — body **>700 words with ZERO structural elements** (table / ol / ul / figure / h3 / callout). 12 Wave-2 prose-only articles baselined; new articles can't be born as walls.

### Born-concise generation (the other end of the chain, mirrors born-grounded)
`article_generator.py`: word **band** 850–1500 (floor AND ceiling, "trim don't pad"); skeleton assigns each section a `block` hint (steps/table/callout/none, 2-4 per article) + may propose 1-2 **figures**; section calls get a rotating PH-anchor pool + an accumulated **ALREADY EXPLAINED affordance list** (kills cross-section re-explanation); audience exactly 6; sources must be topic-relevant; em-dash scrub in the banned-phrase table.

### Figures — `tools/article_viz.py` (deterministic matplotlib → brand SVG)
WAT split: AI proposes the figure spec, Python draws it. Kinds: `step_flow` (platform flows — steps MUST pass capability grounding), `scan_path` / `bar` (**refuse without a `source` citation** — figures obey the same truth doctrine as prose). Brand palette, transparent bg, text-as-path SVG into `learn/<slug>/fig-*.svg`; scaffold injects `<figure class="article-fig">`. First-ever charts in the learn hub (0 of 37 articles had any).

Reference rewrite: `learn/resume-builder-for-filipino-industrial-workers/` — 858 body words (was 2011), 5-min read, scan-path + flow figures, provenance table, worked-example callout, real sources. Gate: `affordance_repetition` current=0 (the rewrite fixed the only offender before the check landed; it now stands guard).

> Companion-tool analog: `COMPANION_DEV_TOOL.md`. Gate roadmap: `SELF_IMPROVING_GATE_ROADMAP.md`. SEO surfaces: `SEO_AEO_GEO_ROADMAP.md`. Inward canonical pattern: `CANONICAL_SOURCES_AUDIT.md`.
