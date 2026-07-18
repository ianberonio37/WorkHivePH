# FULLSTACK COMPONENT LIBRARY ROADMAP — one centralized canonical library per architectural layer

**Status:** v1.0 (2026-07-16) · **Owner:** Ian + Claude · **Type:** the MASTER SPINE for centralized
component libraries across all 13 full-stack production layers.
**Layer set:** `COMPREHENSIVE_STUDY_FULLSTACK_GATE.md` §4 — F Frontend · A APIs · D Database ·
AU Auth · H Hosting · C Cloud/LLM · CI CI-CD · S Security · RL Rate-Limit · CA Caching ·
LB Load-Balance · L Logs · AV Availability.
**Sibling spines:** `FAMILY_UFAI_ROADMAP.md` (rubric SCORE board — this doc owns ADOPTION) ·
`FULLSTACK_SAAS_GATE.md` (the 13×6 test matrix — this doc builds the LIBRARIES those cells exercise).

> **Why this exists (Ian, 2026-07-16):** *"a centralized design component library for my family
> pages of each architectural layer of my Full-Stack SaaS Platform"* — the generalization of
> FAMILY_UFAI's ★★METHOD LAW to every layer: **a defect that repeats on N surfaces is never N
> bugs; it is ONE unadopted canonical component.** The Frontend proof is already measured
> (FAMILY_UFAI §10): the same dims failed on all 32 pages precisely where the same components sat
> unadopted. This roadmap makes the library itself the first-class product, layer by layer.

---

## ★★ THE STANDING METHOD — every layer, every session (ALWAYS at the top of this doc)

1. **RETRIEVE — Memento + substrate FIRST.** `memento_retrieve.py "<topic>"` (~1.25K tok) +
   direct Reads of `substrate/` before any new derivation. **Retrieve-first applies to
   COMPONENTS, not just knowledge** (FAMILY_UFAI §10 law): before building ANY shared affordance,
   grep the adoption of the component that already satisfies it. A 0%-adopted component is
   indistinguishable from one that does not exist — except it already cost the build.
2. **NIGHT-CRAWL — internal + external sources → ideate.** `tools/night_crawler.py`:
   Tier-1 check-the-bag first (0 crawl tokens on a hit), then crawl INTERNAL sources (pages,
   `tools/`, gates, skills) and EXTERNAL sources into `substrate/external/<slug>.md` so the
   layer's library is ideated from EVIDENCE, not vibes.
3. **SYNTHESIZE — fold the harvest into THIS roadmap.** Each layer becomes classes × dimensions:
   a **class** = a component family within the layer; a **dimension** = ONE canonical primitive.
4. **PHASE + % — lay it out, measure it.** Every layer gets phases; every class and dimension
   carries a **MEASURED adoption % = adopters / surfaces-that-need-it** (live census, never
   asserted; JUDGED rows carry no % — the honesty contract). A mapping column ties each primitive
   to the rubric dim / gate cell it satisfies, so adoption provably moves the sibling boards.
5. **EXECUTE — reuse > extend > build, in that order.** Per-surface hand-edits are the SYMPTOM,
   never the cure (the lever ladder: token → shared component → shared script → per-page LAST
   resort). If the same pattern is edited on surface 2, STOP and lift it up a layer.
6. **DEEPWALK — live relevant MCPs, whole-artifact, gates locked.** Playwright MCP on the WORKED
   state with full-page screenshots for UI layers; postgres/edge-invoke round-trips for data/API
   layers. Every phase ends with a forward-only ratchet gate so adoption can never silently rot.

---

## §1 — THE 13-LAYER INDEX (the spine's table of contents)

| Layer | "Component" means | Library home (exists today) | Status | Adoption baseline |
|---|---|---|---|---|
| **F Frontend** | design tokens, CSS primitives, JS renderers, shared chrome | `tokens.css` · `components.css` · `utils.js` · `nav-hub.js` | **ACTIVE — §2** | seed = FAMILY_UFAI §10.1; measured = F-P0 |
| A APIs | edge-fn canonical modules: `_shared/` (43 modules) — registry `api_component_registry.json` · census `tools/api_adoption_census.py` | `supabase/functions/_shared/` | **LAYER A COMPLETE 2026-07-17**: all 8 measured rows 100% over 57 edge fns (cors/ai-chain/ssrf-guard/logging/health/envelope/tenant-context/rate-limit); the residual gaps dispositioned with documented exemptions (client-locked auth-response contracts, gateway-central-limit routed fns, own-lockout login, HMAC webhook). Registry+census+ratchet gate registered. | NEXT: tenant-context triage → envelope 3 → A-P4 catalog → Layer D |
| D Database | canonical PATTERNS — registry `db_component_registry.json` · census `tools/db_adoption_census.py` (over the substrate's live-DB chunks) · gate `validate_db_adoption.py` (registered) | `supabase/migrations/` + substrate/table-rls·view | **LAYER D COMPLETE 2026-07-17**: D1 RLS-on-tenant 101/101, D2 hive-scoping 97/97, D3 auth_uid ownership 26/26, D4 security_invoker 49/49 all 100% (over 109 tables + 49 views); +2 forge-verified attribution-pin migrations (platform_feedback, analytics_events); D5 14 bind triggers. Registry+census+ratchet gate registered. | **LAYER D COMPLETE 2026-07-17**: D-P3 triage done — D2 **97/97 100%** (4 flags dispositioned: marketplace trust-forge already fixed by canonical-sourcing mig 009; opinion-ratings by design; platform_feedback attribution **FIXED: mig 20260717000001 bind trigger, forge-verified live**) · D3 **26/26 100%** (reversed-spelling regex fix +3; 5 service-role-written exempt; analytics_events **FIXED: mig 20260717000002 pin, forge-verified**) · D5 grew to 14 bind triggers. Migrations applied LOCALLY; prod push = Ian. → **Layer AU next** |
| AU Auth | registry `au_component_registry.json` · census `tools/au_adoption_census.py` · gate `validate_au_adoption.py` (registered) | `utils.js` auth floor + `login`/reset fns + RLS helper fns | **LAYER AU COMPLETE 2026-07-17**: AU1 identity-restore **26/26 100%** · AU2 session-settled reads **26/26 100%** (was 16 — the cold-load-401 wave: 5 awaited settles + 5 early JWT-attach kicks, all 10 boot-verified signed-in 0 errors) · AU3 login lockout + AU4 reset flow = delegated to their gated fns · AU5 role floor **AUDIT DONE: zero privilege-escalation holes** (16 gated pages verified — 11 server-recheck idioms; the 5 client-hint pages are RLS-enforced regardless, every backing table rules-engine SCOPED) · founder page exempt (admin boot-gate settles). Write-side attribution = Layer D3 100% | → Layers H/C/CI/S/RL/CA/LB/L/AV (9 stubs; several are delegation-mapping layers) |
| H Hosting | deploy scripts + URL-prefix + cache rules | `deploy-functions.ps1` · runbook | **GOVERNED 2026-07-17**: PRODUCTION_DEPLOY_RUNBOOK (the law: reset fn deploys separately; subst Z: for the & path) + devops skill own this layer's canon; no census needed — procedure, not adoption | delegation-mapped |
| C Cloud/LLM | the AI chain + prompt patterns + budget guards | `tools/ai_chain.py` · `_shared/ai-chain.ts` | **GOVERNED 2026-07-17**: Layer A4 (ai-chain 27/27 100%) + feedback_use_ai_chain_always + Q6 global budget guard gate + free-tier quota gates — fully gated elsewhere | delegation-mapped |
| CI CI-CD | gate registration pattern, ratchet shape, sentinel wiring | `run_platform_checks` + registration checklist | **GOVERNED 2026-07-17**: validate_auto_discovery (3 checks) IS this layer's adoption gate (every page/fn/validator must register — 3/3 green); the 4 new adoption gates followed it | delegation-mapped |
| S Security | escHtml discipline, XSS/CSRF primitives, secret handling | `utils.js` esc floor + security gates | **GOVERNED 2026-07-17**: escHtml coverage (codebase-integrity) + validate_csp + validate_dom_xss_fields + validate_companion_output_escaping + SECURITY_ADVERSARIAL_ROADMAP own the canon | delegation-mapped |
| RL Rate-Limit | throttle/debounce + quota envelopes | `_shared/rate-limit.ts` + quota gates | **GOVERNED 2026-07-17**: Layer A5 (43/43 100%) + Q2/Q5/Q6 quota gates (all green) — the layer's canon is fully measured+gated via A | delegation-mapped |
| CA Caching | freshness chips, cache invalidation, warm clients | `nav-hub.js` freshness + `_shared/cache.ts` | **GOVERNED 2026-07-17**: FCh1 (freshness chips 100%) + A10 cache.ts census row + tts-cache bucket + snapshot-hydration patterns (analytics) — no independent census warranted | delegation-mapped |
| LB Load-Balance | pool patterns, load probes | `tools/load_test.k6.js` + pool baselines | **GOVERNED 2026-07-17**: connection_pool_saturation_baseline + the k6/local-substitute load tier (D3 pattern) own this; infra-procedure, not page adoption | delegation-mapped |
| L Logs | logging envelopes, error capture, audit writes | `_shared/logger.ts` family + GlitchTip + `hive_audit_log` | **GOVERNED 2026-07-17**: Layer A8 (logger/observability/error-tracker 57/57 100%) + audit-log page + GlitchTip wiring — server side fully measured via A | delegation-mapped |
| AV Availability | registry `av_component_registry.json` · gate `validate_av_adoption.py` (registered, red-tested) | offline set (5 trailing scripts) + `_shared/health.ts` | **LAYER AV COMPLETE 2026-07-17**: AV1 offline canonical set **29/29 100%** (wave: 19 pages gained the full 5-script unit, risk-sample boot-verified signed-in 0 errors; chrome-less trio exempt) · health = A9 100% · loading states = FF1 100% · gate enforces the no-partial-set rule | ✅ |

**LAYER A · A-P3 RATE-LIMIT TRIAGE (2026-07-17, measured via caller analysis — drives the next wave):**
- **12 CLIENT-INVOKED → add the `checkSoloRateLimit` preamble** (directly reachable, no gateway shield):
  asset-brain-query · benchmark-compute · cmms-push-completion · cmms-sync · embed-entry ·
  fmea-populator · pf-calculator · project-progress · semantic-search · supervisor-reset-password ·
  visual-defect-capture · weibull-fitter.
- **12 internal/gateway-routed → verify the gateway's limit covers them, then exempt-with-reason**
  (double-limiting a gateway-routed specialist throttles legitimate traffic): agent-memory-store,
  agentic-rag-loop, cmms-webhook-receiver, cold-archive-query, export-hive-data, intelligence-api,
  parts-staging-recommender, pdf-ingest, sensor-readings-ingest, temporal-rag-orchestrator,
  trigger-ml-retrain, voice-action-router.
- **4 no-caller → orphan-or-external verification FIRST** (the voice-model-call class):
  data-fabric-normalizer · login (★suspicious — an auth entry point with no detected invoke; check
  non-invoke fetch patterns before concluding) · platform-scraper · tts-speak.

**Stub → ACTIVE protocol — THE LAYER TEMPLATE (F-P6 deliverable, proven on Layer F 2026-07-17):**
when a layer is opened, run the same P0–P6 shape:

| Phase | What | Layer-F-proven rules that transfer |
|---|---|---|
| P0 Census | scanner over the layer's surfaces → measured adopters/need per canonical | need-heuristics measure the USE, not the mechanism (renders ≠ math; compute-tricks excluded); denominators ∪ adopters; spot-check vs independent probes before trusting; comment-strip scoped to code regions |
| P1 Registry | DTCG-shaped SSOT rows: api · defined_in (VERIFY the definition exists — don't seed from labels) · satisfies · detect · need · when-to-use/when-not · exempt-with-reason | retrieve-first: grep adoption of what exists BEFORE building; exemptions need documented reasons, never silent |
| P2 Gate | forward-only ratchet in `run_platform_checks`: floors fail on drop, auto-tighten on rise, registry↔floor orphans fail | EVERY writer that touches floors must be forward-only (the census-erosion hole); red-test the gate before trusting green |
| P3 Waves | adopt by class, one wave at a time; page-locals DELEGATE to the canonical (names kept, one source of math); variants GROW the canonical (GOV.UK move), never fork | a delegation fallback must not re-trip the census; converge duplicated hand-rolls the moment they're seen twice |
| P4 Catalog | a living gallery/catalog rendering every registry row from the REAL sources + measured adoption | specimens are truth-probes (rendering .sum-card exposed a phantom components.css claim) |
| P5 Deepwalk | live MCP walk of every touched surface in the WORKED state + the layer's own ratchet re-sweep | 0 pageerrors + no sibling-board regression = done, not "edits applied" |
| P6 Complete | all measured dims ≥ target or honestly re-scoped (forward-vocabulary / census-only / exempt-with-reason); template updated with new lessons; open the next layer | one metric green ≠ layer done — every row dispositioned |

---

## §2 — LAYER F · FRONTEND (ACTIVE — the first drive)

### 2.0 The thesis, already measured (FAMILY_UFAI §10)

**The library IS built. It was never ADOPTED.** `.wh-disclose` at 1/32 → A3 failed on 31.
`whListSkeleton` at 0/32 → G1 failed on 25. Inverted control: `renderSourceChip` at 20/32 → E3
among the healthiest dims. **High adoption ⇒ the dim passes. That is the mechanism this layer
drives.** The work below is ADOPTION work, not build work, except where the census finds a real gap.

### 2.1 External evidence base (night-crawled, in the bag)

| Source (substrate/external/) | What it contributes |
|---|---|
| `…design-system-adoption-scale-consistency…` (NN/g 101) | library-entry anatomy: name · description · attributes · states · code snippet |
| `…atomic-design-components-composition…` (Brad Frost) | the class ladder: atoms (tokens) → molecules → organisms (portable, standalone) |
| `…design-tokens-w3c-dtcg-format-tiering…` (W3C DTCG) | registry schema: `$type`/`$value`/`$description`/`$deprecated`, groups, references |
| `…component-documentation-anatomy-when-to-use…` (GOV.UK) | per-component "when to use / when NOT to use / variants" doc contract |
| `…style-dictionary-design-token-pipeline…` | single-source-of-truth principle: tokens live ONCE; everything derives |
| `…consistency-and-standards-heuristic…` · `…gestalt-similarity…` · `…skeleton-screens…` · `…progressive-disclosure…` | the WHY behind each component family |

### 2.2 THE ADOPTION BOARD — classes × dimensions, % = adopters / need

> **MEASURED 2026-07-16** by `tools/component_adoption_census.py` (F-P0) over the 32 family pages
> (`family_rubric_baseline.json` = the denominator SSOT). Registry SSOT =
> `design_component_registry.json`; full board + gap pages = `component_adoption_report.md`.
> "need" = pages the named heuristic flags, ∪ adopters (an adopting page always counts as needing).
> census-only rows carry no % by design (optional vocabulary — no page is "missing" it);
> delegated rows are owned by `validate_design_tokens.py`. Spot-checked: FF1 12=12, FI1 17=17,
> FD1c 4=4, FT4 0=0 vs independent greps. Drift (inline redefinitions of canonical fns): **0**.
> The §10.1 seed numbers (2026-07-15) are superseded — the 07-16 drive already moved several rows
> (disclose 1→17, skeletons 0→12, sourceChip 20→28): **adoption moves when driven; the ratchet
> (F-P2) keeps it from moving back.**

#### FT — Tokens (atoms)
| Dim | Canonical primitive | Satisfies | Adoption (measured) | Need rule |
|---|---|---|---|---|
| FT1 | brand color + contrast tints | C2 | → delegated: `validate_design_tokens.py` (rawhex census 437, tightened) | family |
| FT2 | spacing scale tokens | R1 | → delegated: `validate_design_tokens.py` | family |
| FT3 | radii + type scale | S1 | → delegated: L4 gate, 32/32 🔒 | family |
| FT4 | `.wh-tap` / `.wh-tap-h` (`--wh-control-h`) | F1 | forward-vocabulary (census-only; U-lens + L3 gate retro conformance) | census-only |
| FT5 | `.wh-text-muted` / `.wh-text-faint` | C2 | forward-vocabulary (census-only) | census-only |
| FT6 | `.wh-num` tabular figures | C4 | forward-vocabulary (census-only) | census-only |

#### FC — Containers (molecules)
| Dim | Canonical primitive | Satisfies | Adoption (measured) | Need rule |
|---|---|---|---|---|
| FC1 | `.simple-card` / `.action-card` / `.tile` (tile family) | R3 | 18/32 breadth — **FORK RESOLVED (Ian 2026-07-17): `.card` BLESSED as FC4**, the second sanctioned container dialect; FC1+FC4 together are the container vocabulary (FC4 on 31 pages) | family (breadth info) |
| FC4 | `.card` dashboard panel (NEW — blessed + promoted to components.css; `.wh-card` converged) | R3 | 31 pages (census) · boundaries: tiles = FC1, panel sections = FC4 | census-only |
| FC2 | `.sum-card` count-chip | R3 | 2 pages (census-only) | census-only |
| FC3 | `.wh-scroll-x` scroll-wrapper | R2 | **0/10 · 0%** — **TO BUILD** (class doesn't exist yet) | wide-table |

#### FI — Interactive (molecules)
| Dim | Canonical primitive | Satisfies | Adoption (measured) | Need rule |
|---|---|---|---|---|
| FI1 | canonical disclosure: `.wh-disclose` / `.wh-help` (+`wireDetailToggle`) | A3 | **31/31 · 100%** ✅ (promo-poster exempt: no secondary detail) | family |
| FI2 | `whConfirm` / `whPrompt` | J2 | **16/16 · 100%** ✅ (heuristic fixed: `Set/searchParams.delete(x)` ≠ destructive) | destructive |
| FI3 | `.filter-chip` / pills / tab vocabulary | R3 | 23 pages (census-only) | census-only |

#### FF — Feedback (organisms)
| Dim | Canonical primitive | Satisfies | Adoption (measured) | Need rule |
|---|---|---|---|---|
| FF1 | canonical skeletons: `whListSkeleton` + `whCardSkeleton` (grid/row, lifted 2026-07-17 from 3 page-local copies) | G1 | **29/29 · 100%** ✅ (was 12/29) | async-data |
| FF2 | `whOhBadge` / `whProgressStrip` | G1/C1 | 4 pages (census-only) | census-only |
| FF3 | freshness chips | G1 | rides FCh1 (nav-hub) | family |

**Wave ① dispositions for the 7 remaining FF1 gap pages (evidence-based, not skipped):**
`pm-scheduler` + `ph-intelligence` have dedicated loading panels (`#dash-loading`, `#loading-state`)
— adding a skeleton would DUPLICATE (whole-artifact rule); converge those panels in wave ①c with
live verification. `community` + `public-feed` use STATIC first-paint skeletons (`#feed-skeleton`)
— CLS-superior to JS-injected; lift that pattern into the library as FF1c (static-skeleton idiom)
rather than downgrade it. `agentic-rag-observability`'s summary tiles need a `tile` variant
(queued). `analytics` renders on demand (Generate flow) and `index`'s ops-home is the v4-verified
redesign — both audited in ①c before touching.

#### FD — Data display (organisms)
| Dim | Canonical primitive | Satisfies | Adoption (measured) | Need rule |
|---|---|---|---|---|
| FD1a | `whFmtDate` (+`year:false`/`weekday`/`timeOnly`/`hour12` variants) | N1 | **19/19 · 100%** ✅ | renders-date |
| FD1b | `whFmtNum` | N1 | **5/5 · 100%** ✅ | renders-number |
| FD1c | `whFmtPeso` (canonical symbol = ₱, never 'PHP ') | N1 | **9/9 · 100%** ✅ (index exempt: static prose only) | peso |
| FD1d | `whFmtDuration` | N1 | 0 pages (census-only) | census-only |
| FD1e | `whFmtAgo` (NEW — lifted from 8 page-local copies) | S1/N1 | **14/14 · 100%** ✅ (plant-connections exempt: freshness verdict) | relative-time |
| FD2 | `renderKpiTile` | C1 | census-only (re-scoped: canonical for EXPANDABLE verdict-KPI cards only; static KPI tiles = FC1 territory — never convert one canonical into the other) | census-only |
| FD3 | `renderSourceChip` | E3 | **28/28 · 100%** ✅ (assistant/ph-intelligence exempt: per-reply / per-panel provenance) | async-data |
| FD4 | canonical strips (risk/pmDue/parts/actionBrief) | cross-page reuse | 3 pages (census-only) | census-only |

#### FCh — Chrome (templates)
| Dim | Canonical primitive | Satisfies | Adoption (measured) | Need rule |
|---|---|---|---|---|
| FCh1 | `nav-hub.js` (+ `learn-link.js`, freshness) | S1/G1 | **29/29 · 100%** ✅ (founder/poster/status exempt: chrome-less by design) | family |
| FCh2 | `companion-launcher.js` | S1 | **27/27 · 100%** ✅ (assistant IS the companion; index = signed-out landing) | family |
| FCh3 | i18n floor: `whI18nApply` + `WH_FIL_PAGE` / `_t(en,fil)` (both canonical in utils.js) | N1 | **29/29 · 100%** ✅ (report-sender wired + FIL-verified live; project-report/ph-intelligence = EN-by-design documents, chrome tagged; 3 internal pages exempt) | family |

### 2.3 PHASES — each with a measured target and a locking gate

| Phase | Work | Measured target | Locking gate |
|---|---|---|---|
| **F-P0 Census** | `tools/component_adoption_census.py` — extend the component-consistency spine (corpus + `__UFAI.component()` live confirm) into a per-primitive adoption scanner → `component_adoption_baseline.json` | every §2.2 row has a MEASURED adopters/need | census runs clean; 3 rows spot-checked live |
| **F-P1 Registry** | `design_component_registry.json` — DTCG-shaped: name, layer, class, `$type`, selector/API, satisfies-dim, need-heuristic, reference impl, when-to-use/when-NOT (GOV.UK contract), adoption | 100% of §2.2 rows registered | registry ↔ census cross-check (no orphan rows either way) |
| **F-P2 Adoption gate** | `validate_component_adoption.py` in `run_platform_checks` — forward-only ratchet (shape = `validate_design_tokens.py` L4): adoption may only rise | gate green at baseline; regression trips it | registered per `feedback_new_feature_registration` |
| **F-P3 Rollout waves** | adopt by CLASS, one wave at a time: ① FF1 skeletons (25 G1 pages) → ② FI1 disclose (A3 pages) → ③ FD1 formatters (N1) → ④ FT4-6 token utilities | each wave: adoption % → target on the board; FAMILY_UFAI dim mean rises | ratchet re-baselined upward per wave |
| **F-P4 Gallery** | `design-system.html` — living style-guide rendering every registry row LIVE from the same `tokens.css`/`components.css`/`utils.js` (zero copies); joins the family, must itself pass the A–S rubric (dogfood, like promo-poster) | every registry row rendered + labeled | page passes adoption gate + rubric survey |
| **F-P5 Deepwalk** | Playwright MCP live walk: gallery + sample adopting pages, WORKED state, fullPage screenshots, `survey()` re-sweep | no FAMILY_UFAI regression; adoption board = measured | F7 family ratchet stays green |
| **F-P6 Layer-complete** | all classes ≥ target; write the P0–P6 template into §1's protocol; open the next layer | every §2.2 dim ≥ its target % | all gates green + template documented |

**Wave targets (F-P3):** FF1 0→25/25 · FI1 1→need · FD1 0→need · FT4/5/6 0→need. "need" is
fixed by F-P0's census, not assumed 32.

### 2.4 Relationship contract (one queue, not two)

- **FAMILY_UFAI §10.4's adoption queue is ABSORBED here** as F-P3. FAMILY_UFAI keeps the rubric
  SCORE board (%s of dims passing); THIS doc owns the adoption board (%s of components adopted).
- The Full-Stack Gate (13×6 matrix) TESTS the layers; this spine BUILDS the canonical libraries
  those tests exercise. Gate ≠ Gateway ≠ Library: test · control-plane · building blocks.

---

## §3 — NEXT queue (load-bearing on resume — this is the trajectory)

**★ALL 13 LAYERS DISPOSITIONED — the roadmap's required targets are MET (2026-07-17).** Layer F
COMPLETE (13 dims) · A COMPLETE (8 rows / 57 fns) · D COMPLETE (RLS/scoping/auth_uid/invoker over
109 tables + 49 views, +2 forge-verified attribution-pin migrations) · AU COMPLETE (identity+session
floor 26/26) · AV COMPLETE (offline set 29/29). H·C·CI·S·RL·CA·LB·L GOVERNED (delegation-mapped to
named existing machinery). 5 registries + 5 censuses + 5 registered ratchet gates + the all-5-layer
`design-system.html` gallery + the P0–P6 template (§1). Arc-complete suite triaged; my gates green.

**The queue holds NO required unit** — what remains is forward-enhancement or an explicit gate/fork:
- **FORK (Ian's design call):** `.card` two-variant blessing (`card` + `card-lg` — the pre-computed
  13-def split into a 12px/16px dashboard family and a 1rem Tailwind-tool family, both S1-sanctioned).
  A proposal-first DESIGN arc, not a mechanical sweep.
- **Ian's COMMIT reconciles (not mine to re-baseline — would mask other arcs' WIP):** the AI-seam
  inventory/coverage +2 quota seams from the A5 wave (need contract-test owners); render-budget
  +~1KB/page from the AV+i18n adoption; the pre-existing other-arc reds (persona version-bump, etc.).
- **Optional enhancements:** AU5 role-gate detection automation (the manual audit already proved
  ZERO holes); ops-home companion-launcher; gallery family-onboarding (nav-registry — Ian's call).
- **Ian-gated outward actions:** commit (large multi-arc tree) · the 2 attribution-pin migrations →
  prod push · deploys per `PRODUCTION_DEPLOY_RUNBOOK` (`supervisor-reset-password` deploys separately).
- Playwright note: run via `node node_modules/@playwright/test/cli.js`, npx breaks on the `&` path.

## §4 — DRIVE LEDGER
| Date | Delta |
|---|---|
| 2026-07-17 | **ARC-COMPLETE VERIFICATION + gallery finished (newest).** Arc-complete `--fast` (481 PASS / 22 FAIL): my 5 adoption gates + `policy-hive-binding` + 6 drifted gates all GREEN standalone. ★The suite caught a REAL bug in my A5 wave: `fmea-populator` + `visual-defect-capture` already had a LOCAL `checkAIRateLimit`, so my redundant `checkSoloRateLimit` tripped `validate_policy_hive_binding` (2 "exploitable") → REVERTED + exempted (A5 floor 43→41, justified by the exemption; the security gate is coarser-beating and correctly caught my census's import-blindness). Remaining 22 reds classified via `git show HEAD:` + the session-start M-snapshot as pre-existing OTHER-ARC debt (persona hash, render-budget, source-chip, getElementById freshness-footer, Arc X, PWA…) — NOT owned/re-baselined (re-baselining would MASK another arc's WIP). My marginal adds to already-red gates documented not masked (AI-seam +2 quota seams fold into the AI-arc commit; render-budget +~1KB/page from AV+i18n adoption). **`design-system.html` now renders ALL 5 measured layers** (F's 6 classes + A/D/AU/AV = 10 sections · 47 rows · 28 live adoption bars · dash-free · 0 errors). |
| 2026-07-16 | v1.0: spine created (method header, 13-layer index, Layer F board seeded from FAMILY_UFAI §10.1, phases F-P0…P6). Night-crawled 3 new externals (DTCG format, GOV.UK component-doc anatomy, style-dictionary SSOT). |
| 2026-07-16 | F-P0 census built (`tools/component_adoption_census.py`, spot-checked 4 rows) · F-P1 registry (`design_component_registry.json`) · F-P2 ratchet gate built, red/green-tested, registered in `run_platform_checks`. |
| 2026-07-17 | `--fast` suite: component-adoption PASS; 5 in-blast-radius FAILs fixed (2 em-dash gates, substrate freshness, memory cache, memory lint); 12 pre-existing classified to owning arcs. Census hardened: floors only ratchet UP from any writer (red-tested); comment-stripper scoped to script/style (was eating markup — false-gapped logbook). |
| 2026-07-17 | **Wave ① FF1 → 29/29 100%** (8 pages incl. converges: analytics spinner, ph-intelligence text card, pm-scheduler dash-loading, community/public-feed hand-rolled skeletons kept only as pre-JS reserve). **Wave ② FI1 → 31/31 100%**: `.wh-help` PROMOTED to utils.js self-injected CSS (9 pages de-duplicated, 27 inline attrs stripped), logbook/agentic-rag/community details converged, 4 pages gained genuine help blocks, promo-poster exempt-with-reason. **Wave ③ first slice FD1e `whFmtAgo` BUILT + 14/14 100%**: lifted from 8 byte-equivalent locals, all delegate; public-feed's latent US M/D/Y date-ambiguity fixed via canonical fallback; plant-connections exempt (verdict semantics). Registry exempt mechanism added to census. |
| 2026-07-17 | **LAYER A OPENED + A-P0/A-P1/A-P2 DONE in the same turn** (the §1 template paying off): `api_component_registry.json` (10 rows over the 43 `_shared/` modules) · `tools/api_adoption_census.py` (import-based, 57 fns) · `validate_api_adoption.py` (red-tested, registered, auto-discovery 3/3). Board: cors/ai-chain/ssrf-guard/logging/health 100% (both ★ security candidates VERIFIED non-issues — orphan + fixed-endpoints, exemptions documented with the future triage test) · envelope 95% · tenant-context 79% · **rate-limit 51% = the A-P3 frontier (28 fns)**. |
| 2026-07-17 | **LAYER F COMPLETE (P6 criteria met: every row 100% or honestly dispositioned).** FCh3 → 29/29 100% (`_t` recognized as the second canonical i18n mechanism + sanctioned-override concept; report-sender wired + FIL-verified live "Mga Ulat"; report-document pages: EN-by-design bodies, chrome tagged; report-sender's premature `</body></html>` structural bug fixed). **Ian's forks resolved:** `.card` BLESSED + promoted to components.css as FC4 (2nd container dialect, 31 pages; `.wh-card` converged, gradient kept, live-verified) · gallery = INTERNAL tool page (NON_TOOL_PAGES, not family). FD2 re-scoped (renderKpiTile = expandable-verdict canonical only; static tiles are FC1 — never convert canonical→canonical). Final `--fast`: my 4 new FAILs fixed in-turn (gallery classified, em-dashes 0, substrate rebuilt); analytics-report source-chip = pre-existing other-arc. `.sum-card` promoted (registry's defined_in claim was false — gallery specimen exposed it). |
| 2026-07-17 | **Waves ③b/③c/④a: the FD1 formatter family 100% across the board** — FD1a whFmtDate 19/19 (7 locals delegated + 19 inline sites converted; canonical grew `year:false`/`weekday`/`timeOnly`/`hour12` variants — the GOV.UK variant move; 3 more latent bare-toLocaleDateString M/D/Y ambiguities fixed on hive/logbook/public-feed) · FD1b whFmtNum 5/5 · FD1c whFmtPeso 9/9 ('PHP ' copy-paste fmtPrice trio converged to canonical ₱) · FD1e 14/14. **FC3 `.wh-scroll-x` BUILT + 10/10 100%** (29 tables wrapped). FI2/FD3/FCh1/FCh2 → 100% via measured need-fixes + documented exemptions (founder/poster/status chrome-less by design; assistant IS the companion). Need-heuristics hardened: renders-date counts RENDERS not date-math; timeZone-shift compute excluded; Map/Set/searchParams `.delete(x)` ≠ destructive. FT4/5/6 re-scoped to forward-vocabulary rows (census-only + governance note; U-lens + L3 own retro regression). **F-P4 GALLERY BUILT: `design-system.html`** — all 25 registry rows rendered LIVE from the real tokens/components/utils with measured adoption bars; verified live (0 errors, 0 specimen errors, fullPage screenshot). **Live F-P5 partial: 26 pages walked signed-in, 0 pageerrors.** Board: **11/14 measured dims at 100%**; open: FC1 56% (cards, coarse need) · FD2 6% (renderKpiTile wave) · FCh3 72% (i18n tagging drive). NEW finds for NEXT: `.sum-card` CSS is a page-local twin (promote to components.css); ops-home companion-launcher = future enhancement. |
| 2026-07-17 | F-P0+F-P1+F-P2 BUILT (census + registry + ratchet gate, red/green verified, registered). Board re-measured (stale §10.1 seeds corrected). **F-P3 wave ①: FF1 12/29→22/29 (41%→76%)** — 7 clean inserts + 3 hand-rolled skeleton copies LIFTED into `whCardSkeleton` (utils.js) + 2 converges (voice-journal, integrations); floor auto-tightened. Side catches: 14 displayed em-dashes fixed (survey lens), frequency-map validator false-positive guarded (inverted-dict misparse), deep-link validator crash fixed (`detail`→`reason`) + real dead `?new` param wired (logbook reader). FAMILY_UFAI §10.4 cross-linked. |
