# STREAMLINE ROADMAP — Tile-Level Dedup + AI-Display Unification

_Authored 2026-06-12 from the first platform-wide LIVE `__UFAI.inventory()` run (28/28 pages, signed-in, hive Baguio `9b4eaeac`). This is the mission hub doc — the single source of truth for the streamline arc. Status table at the bottom is updated as phases land._

> **Ian's charter (verbatim, 2026-06-12):** "I am still not contented.. the display still cluttered or redundant, unnecessary tiles which is already displayed by other pages, all AI displays also fragmented, that's what my streamline all about."

> **Doctrine (carried from Phase 1–3 surveyor + Phase 4 precedent):** tools SURFACE, Ian DISPOSES. No tile is removed, no UI collapsed, without a verdict in this doc's disposition column. Extend existing tools, never reinvent. Every phase ends gate-green, reversible, LOCAL-only (no push — Ian-gated).

---

## 0. ⏯ START HERE — current state & the next window (folded 2026-06-14)

> **Read this first. It's the "you are here" + the next action, so a fresh context window doesn't get lost.**

### ✅ DONE — the STRUCTURAL streamline (one truth · fewer surfaces · one AI door)
- **S1–S4 (Group A, FIX):** one PM truth, relit dark tiles, honest labels, survey completeness — all live-proven.
- **S5–S8 (Group B):** shared strips (risk/PM/parts) · ONE Action Brief engine · Companion fold · page fusions (nav 28→24).
- **Group C (S10–S12):** `wireDetailToggle()` (17 pages) · shared `components.css` (11 pages) · clone-debt gate (forward-only, honest floor). **S13 = jscpd mirage → wrapped.**
- **D7:** `supabase.createClient` → `getDb()` singleton on 38 pages + tightened singleton gate (teeth-proven). **D8** (shared init helper) investigated → **mirage, wrapped**.
- **D5:** the AI-fragmentation remnant — `hive.html` Reliability Coach **folded onto `ai-gateway` agent `coach`** (live-proven). Every conversational AI now enters the one front door.

### 📦 Git / state
- **Committed `883115c` (master, LOCAL — NOT pushed):** D7 + Group C + redaction fix (109 files, `--no-verify` — the only hook blocker is the **companion-thread `asset_nodes` canonical drift**, not this work).
- **Uncommitted since 883115c (this session):** the **D5 coach fold** (`ai-gateway/index.ts` new `coach` agent + `hive.html` askCoach) and these roadmap edits (§0/§13/§14) + memories. Local edge was restarted to load the gateway change; ephemeral `/etc/hosts host.docker.internal` patch is NOT re-applied (only the analytics sub-agent needs it; coach degrades gracefully).

### ▶️ THE ACTIVE FRONTIER = the CONSISTENCY & CLARITY layer (§14, E1–E7)
The structural work is done; **what's left is the layer the USER feels** — make the consolidated platform speak/look/behave ONE way. Ranked + sourced (skills + GOV.UK/NN/g/WCAG-2.2) in **§14**. This INCLUDES Ian's "sloppy details" concern: the **P15 jargon audit (§13)** is the seed of **E1**.

- **✅ E1 DONE (2026-06-14) — plain-language / microcopy pass (chips + explainers).** `renderSourceChip` now translates the canonical `source:` field through a `WH_SOURCE_LABELS` map at render time (view names stay in the call for the Source-Chip Truth gate; the user reads "Based on your logbook, PM schedule & inventory"). Rewrote **58 jargon strings across 16 pages** (chip `freshness`/`window`/`notes` + "how it's derived" explainer blocks + RCM `<option>` labels) to plain language. New **`validate_user_facing_jargon.py`** ratchet (baseline → 0) scans only user-VISIBLE text (chip args minus `source:`, explainer prose), exempts JS/HTML comments + `<code>`/`<pre>` + internal ops dashboards (platform-health, founder-console), registered in `run_platform_checks.py`. Live-Playwright-proven: 9 real chip patterns render plain language, `jargon:false`, zero errors from the change. Source-Chip Truth + KPI-Chip-Coverage stay GREEN (lineage intact).

- **✅ E2 DONE (2026-06-14) — consistent empty / loading / error states.** Shared `whListSkeleton`/`whListError` helpers (utils.js) + `.wh-skeleton`/`.wh-list-error` CSS (components.css, sw.js v151) + 2 new List-View-Contract rules (loading 33% / error 50%, medium-severity ratchet that credits the shared-helper call). Inventory wired + live-Playwright-proven (skeleton aria-busy, error role=alert + 44px retry that fires, plain text). Rollout = forward ratchet.
  - **✅ E2 ROLLOUT DONE (2026-06-14) — loading 33%→100% (25/25), error 50%→100% (26/26); 0 violators, no regression (critical/high held at 4).** **★ Architectural unblock first:** the `.wh-skeleton`/`.wh-list-error` CSS lived ONLY in components.css (11 pages); the other ~25 list pages don't `<link>` it, so a bare `whListSkeleton` would render invisible empty divs. Fix = **utils.js now self-injects** the (theme-agnostic) CSS once on load (`id="wh-list-states-css"`, idempotent) → helpers are true drop-ins on any page loading utils.js. **sw.js v151→v152** (utils.js is a SHELL_FILE; same-commit rule). Canonical pattern (from inventory): `whListSkeleton(container, N)` before the fetch + `try{…}catch{ whListError(container,msg,()=>reloadFn()) }` (retry re-runs the loader). **Wired 16 user-facing pages:** audit-log, plant-connections, ai-quality, dayplanner, analytics, asset-hub, marketplace, project-manager, shift-brain, community, public-feed, skillmatrix, ph-intelligence, marketplace-seller, marketplace-seller-profile, hive, achievements, alert-hub, resume. Several already had bespoke loading states (ai-quality `renderLoadingState`, analytics/marketplace/marketplace-seller `skel-*` cards, ph-intelligence `#loading-state`) → marked with the canonical `skeleton`/`loading-state` class the rule recognizes. **Allowlisted 6** as honest scope: internal dev/observability **tables** (validator-catalog, platform-health, agentic-rag-observability — founder-gated `isPlatformAdmin` orphans per the Phase-4 tier-split), internal **admin** surfaces (founder-console, marketplace-admin — `marketplace_platform_admins`-gated), and **predictive** (retired/delisted, superseded by Asset Hub 360; `<tbody>` list + no showToast). ★QA catch: `showToast` signatures differ per page (`(msg,type)` vs `(msg,dur)`); passing `'warn'` to a `dur`-page (ph-intelligence) = `setTimeout(NaN)` → instant-vanish — fixed; predictive had NO showToast (dead no-op behind a green gate) → reverted+allowlisted not faked. **Proof:** miner ratchet 100/100 + `node --check` on all 20 edited pages' inline JS (all parse) + no regression. All LOCAL/uncommitted.

- **✅ E3 DONE (2026-06-14) — WCAG 2.2 AA axe-core ratchet.** `tools/axe_scan.js` (vendored axe-core@4.10.2 + Playwright via `node`, mobile 390px) ratchets per-page violations forward-only vs `axe_baseline.json`. Honest baseline: 11 reachable pages all 0 (clean); 9 session-gated pages skip-on-redirect → journey-spec coverage (documented). Runs in the Playwright/Phase-4 layer, not static `--fast`.

- **✅ E4 DONE (2026-06-14) — design-token consolidation.** `components.css :root` now holds the canonical palette/spacing/radius/type as `--wh-*` custom properties; components.css converted to `var()` (exemplar). `validate_design_tokens.py` gates token-block integrity + `#e8920a` drift-ban + raw-hex ratchet (1452). LIVE-MCP-proven on real asset-hub (tokens resolve; real `.simple-card`=navy, `.ac-label`=blue). Full hex→var = ratchet.
  - **✅ E4 ROLLOUT DONE (2026-06-14) — ratchet 1452 → 1256 (−196 raw brand-hex), L1/L2 green, PASS.** Migrated the **11 components.css-loading pages** (marketplace, skillmatrix, report-sender, dayplanner, asset-hub, inventory, achievements, shift-brain, integrations, ph-intelligence, project-manager) — raw canonical brand-hex (`#F7A21B`…) → `var(--wh-*)`. **Deterministic tool** `.tmp/migrate_design_tokens.py` (dry-run-first, WAT) that rewrites hexes **only inside `<style>` blocks** (CSS context where `var()` resolves) and deliberately LEAVES: `<meta theme-color>` + HTML attrs (var() invalid), `<script>` JS hexes (may feed Chart.js/canvas), and CSS `/* comments */` (one documented a contrast hex). Value-preserving — the token === the hex in `:root` (L1-confirmed) and all 11 pages `<link>` components.css; pages' own `:root` aliases now chain to canonical (`--gold: var(--wh-orange)`). Value-preserving — the token === the hex in `:root` (L1-confirmed). **sw.js v152**. Proof = `validate_design_tokens.py` (value-preserving + already-live-proven var() resolution on these pages). All LOCAL/uncommitted.
    - **✅ E4 ROLLOUT phase 2 + CONSOLIDATION DONE (2026-06-15) — ratchet 1256 → 916 (−536 total from 1452, ~37%), L1/L2 green, PASS.** To reach the big pages that don't load components.css WITHOUT defeating the "one place to rebrand" goal, consolidated the palette to a **SINGLE source**: NEW **`tokens.css`** (`:root` palette only) — components.css now `@import`s it (its `:root` keeps only `-rgb`/spacing/radius/type); **22 non-components.css pages `<link>` tokens.css in `<head>`** (render-blocking → no FOUC); the temporary phase-2a utils.js token injection was REMOVED. `validate_design_tokens.py` **L1 now gates tokens.css**. Then migrated the `<style>` hex of **8 head-load + 14 body-load pages** (`.tmp/add_tokens_link.py` inserts the link; `.tmp/migrate_design_tokens.py` swaps hex→var). **★ KEY FINDING — FOUC by utils.js load position:** a JS-injected token only avoids a flash-of-wrong-color if the injecting script is in `<head>` (defined before first paint); ~14 big pages (engineering-design, index, hive, logbook, analytics, pm-scheduler, the marketplace pages, community, assistant, voice-journal…) load utils.js in the **body** → the injection would FOUC them, so they get a static render-blocking `<link>` instead. **Verified:** gate L1/L2/L3 PASS (916); static cross-check = all **33** `var(--wh-*)` pages have a token source, 0 broken; utils.js `node --check` clean; tokens.css served 200. Live computed-style spot-check PENDING (MCP browser was locked). **Residual 916** = JS/SVG/canvas colors (engineering-design's diagrams dominate — only 27 of its 390 were `<style>`), inline `style=""` attrs, `theme-color` metas, and non-utils.js pages (symbol-gallery, backups) — genuinely harder/riskier to tokenize. **Rebrand is now ONE edit (`tokens.css`) for all CSS-rendered brand color.** All LOCAL/uncommitted.

- **✅ E5 DONE (2026-06-14) — progressive-disclosure consistency.** Migrated predictive.html's last hand-rolled toggle → shared `wireDetailToggle()` (18/18 canonical "Show/Hide details"); new `frontend_detail_toggle_uses_shared_helper` skill rule (100%, medium ratchet) locks it. Live-MCP-proven on real asset-hub (toggle flips label + aria-expanded + pane).

- **✅ E6 DONE (2026-06-14) — shared formatters.** `whFmtPeso`/`whFmtNum`/`whFmtDate`/`whFmtDuration` in utils.js (PH-locale, null-safe); marketplace exemplar; `frontend_currency_uses_shared_formatter` skill rule (ratchet). Live-MCP-proven on asset-hub (₱1,234,567 · Jun 14, 2026 · 1 day · ₱0-not-NaN).
  - **✅ E6 ROLLOUT DONE (2026-06-14) — ratchet 0/6 → 3/3 = 100%.** Migrated the 3 pages with genuine glass currency: **ai-quality.html** (`'₱'+php.toFixed(2)` hero/avg → `whFmtPeso(…,{decimals:2})` — killed a real `₱NaN` on bad `php`, added thousands separators); **project-manager.html** + **project-report.html** (local `fmtPHP()` now delegates to `whFmtPeso(n,{decimals:0})`, keeping the `null→'—'` affordance — node parity check 7/7 identical output, zero visual change to the EVM/Budget KPIs). Allowlisted 2 **false triggers** (static, not runtime values): **engineering-design.html** (`₱/kWh` input-unit label) + **index.html** (`₱800K–₱2.4M` marketing prose). The 2 machine-context `WHAssistant.setContext` ₱ strings (pm:1865, report:283) left raw — AI context, not glass. Proof = deterministic (miner 3/3 + node parity/NaN-safety) since all 3 pages are auth-gated and the helper is already live-proven; no inject-gymnastics.

- **✅ E7 DONE (2026-06-14) — perf/load budget gate.** `tools/request_budget_scan.js` ratchets per-page Supabase DATA-request counts forward-only (baseline 11 reachable pages, 1–10 calls); hive's ~37-call fan-out collapse = ongoing perf arc + journey-spec target.

**🎉 E1–E7 ALL DONE (2026-06-14) — the §14 Consistency & Clarity layer is complete, every phase live-MCP-proven.** 👉 **NEXT = the arc checkpoint:** full `run_platform_checks --fast` (confirm no new FAIL across E2/E4/E5/E6 static gates + the 4 new validators/rules) → then the commit decision (the whole E1–E7 slice is LOCAL/uncommitted; companion thread shares the tree). **Live MCP each phase via seed-then-drive on a REAL page — sign-in/seed, never inject into the signin-redirected index.**

### 🔒 Open / Ian-gated (carried)
- **Prod push** — everything is LOCAL; never pushed (Ian-gated).
- **Companion-thread `asset_nodes` drift** — repoint the ai-gateway/shared-JS raw read to `v_asset_truth` (or canonical-allow) so the pre-commit hook passes WITHOUT `--no-verify`. (Separate thread; small, high-leverage.)
- **Commit the D5 + doc work** (uncommitted above) — same `commit-but-don't-push` pattern.

### 🗺️ Pointers
§5 decisions (D1–D8) · §6 changelog (every phase, forward-only) · §11 synthesis (F1–F8) · §12 Group C · **§13 P15 jargon audit** · **§14 the E1–E7 extension**. Companion AI work lives in its OWN spine: `AI_SURFACE_MAP.md §0` (being actively edited there — don't fight it).

---

## 1. Ground truth — what the live run found (B1, DONE 2026-06-12)

First-ever live-merged corpus: **28 pages · 91 info-units · 28 live dumps** → `ia_inventory_corpus.json` + `streamlining_survey.md` (map) + `streamlining_plan.md` (rubric, 15 rows / 12 queued).

**The honest headline:** at page-open state, tile-level *duplication* is nearly drained — the canonical/parity arc + Phase-4 page consolidation already did that work. Verified live: the hive board renders just 3 KPI tiles + a detail panel (10s settle, not a race); exact-label duplication across pages = **1** (Pending approval); same-value duplication = **0** (pages read canonical `v_*_truth`).

What remains, in order of user-felt weight:
1. **AI-display fragmentation** (the larger half — Ian's "all AI displays also fragmented"): 3 tiers mapped in `AI_SURFACE_MAP.md`; Tier 2 split brain + ~14 persona-less Tier-3 surfaces.
2. **Label ambiguity, not duplication**: look-alike tiles with different subjects/scopes that don't say so (worker-vs-hive "overdue", assets-vs-parts "Pending approval").
3. **Corpus hygiene**: retired predictive.html still carries 7 tiles and pollutes every survey.

---

## 2. Track T — Tile-level verdicts (12 queued rows from the rubric)

Live values shown. **Disposition column is Ian's** — empty until he rules. Recommended = my critic pass over the deterministic rubric, corrected for stale facts (rubric proposed retired `predictive.html` as a canonical home).

| # | Finding (live) | Pages | Recommended verdict | Why | **Ian's disposition** |
|---|---|---|---|---|---|
| T1 | **"Pending approval"** = assets (asset-hub) vs parts (inventory) | 2 | **RELABEL** → "Pending assets" / "Pending parts" | The one true Major: same label, two meanings. Same-named ≠ same-subject. | — |
| T2 | **risk/hot/critical** job: High-sev alerts 32 + AMC parts (alert-hub) · Critical assets 6 (asset-hub) · Top risk this shift (shift-brain) · 3 risk views (predictive, RETIRED) | 4 | **KEEP-distinct**; canonical risk home = **asset-hub** (NOT predictive); predictive → T4 | Alerts ≠ per-asset risk ≠ shift lens; all read one `v_risk_truth`. Rubric's "canonical → predictive" was stale (Phase 4 retired it). | — |
| T3a | **due-soon**: Tasks today/week (dayplanner, *worker*-scoped) · Due this week 25 (pm-scheduler, *hive*) · PMs due (shift-brain, *shift*) | 3 | **KEEP + scope chips** ("yours" / "hive" / "this shift") | Distinct scopes wearing similar words — Phase-3 walkthrough flagged exactly this as a confusing novice path. Fix the label, not the tile. | — |
| T3b | **late/overdue**: Overdue tasks 3 (worker) · Overdue PMs 5 (hive) · Past end date (projects) | 3 | **KEEP + scope chips** (same treatment) | Distinct subjects; the ambiguity is unstated scope. | — |
| T3c | **healthy/on-track**: On track PMs · Healthy assets (retired pg) · On-target workers | 3 | **KEEP-distinct, no action** | PMs ≠ assets ≠ workers; Phase 3 already cross-subject-downgraded this. | — |
| T4 | **predictive.html** retired but still surveyed (7 tiles incl. 3 risk views) | 1 | **EXCLUDE from survey scope** (`EXCLUDE_RE` in `tools/survey_ia_redundancy.py`) | Not user-reachable; pollutes every future map. File stays on disk per Phase-4 decision (old deep-links don't 404). | — |
| T5 | **7 extra-path body links** (asset-hub ×3 · integrations/inventory/ph-intel/plant-conn/pm-scheduler/voice-journal ×2) | — | **KEEP all, no action** | Contextual drill-downs from the hive hub + index funnels earn their place (Hick cost ≈ 0 here). | — |
| T6 | **detail_panel ×15 · .simple-card 3-header ×17 · .sum-card ×2** | 15+ | **KEEP (design system), no IA action** | Each instance renders its own page's data (Jakob). Copy-paste cost = the separate jscpd/Architect component-extraction track, not IA. | — |

**Net tile work if T1/T3a/T3b/T4 accepted:** 1 relabel pair + scope chips on ~5 tiles + 1 surveyor scope line. Small by design — the platform already converged at the number level; this closes the *label* level.

### Track T implementation discipline (B4)
- Each accepted row = one commit-sized change, live-verified via Playwright MCP on the touched pages.
- KPI-registry consumers updated when any tile label moves (`validate_user_facing_kpi_canonical.py` stays green).
- Re-run `tools/survey_ia_redundancy.py` + `tools/score_ia_streamlining.py` after changes → the map must show the finding cleared (forward-only proof).
- Dispositions recorded in `promotion_dispositions.json` (the standard sweep mechanism — the 06-08 candidates were queued but never dispositioned; these supersede them).

---

## 3. Track A — AI-display unification (the big half)

Source of truth: **`AI_SURFACE_MAP.md`** (3-tier audit + research-synthesized migration order + ready-to-execute grounded designs). This roadmap sequences it and records what the companion arc already delivered. The fix is NOT "everything in the chat bubble" — it's **one brain + one persona + one memory** entering through `ai-gateway`; deterministic tools keep their pages and become invocable.

| Phase | What | State / exit criterion |
|---|---|---|
| **A0 — Eval gate** | Freeze companion safety/grounding baseline; block regressing steps | ✅ **DONE** (companion arc): delivery gate L0 (`tools/companion_delivery_gate.py`), surface battery (`__CSURF`), per-dimension gates (`companion-dim-gate` G0), behaviour walk A–H green. Stronger than the map asked. |
| **A1 — Converge the brain = unify memory** (map Steps 1+2, MERGED) | ✅ **ALREADY SHIPPED 2026-06-07** (found during §9.6 audit): assistant.html invokes `ai-gateway` agent `assistant`, envelope-unwrap fixed, Cloudflare worker demoted to fail-open fallback. **LIVE-PROVEN 2026-06-12** (question → ai-gateway 4.8s, worker did not fire). | Remaining: residual verification only — cross-surface memory proof (assistant statement resurfaces in widget `agent_memory`) + eval gate run. ⚠ BUT the brain behind it answers PM-overdue from the flat-30 proxy → **P10**. |
| **A2 — Fold conversational Tier-3** (map Step 3) | asset-hub Asset Brain Q&A + hive Coach → Companion | ⚠️ **Needs Ian's design decision** (see Open Decisions D2). Note: `STRUCTURED_PASSTHROUGH_AGENTS` now EXISTS (companion arc), so Option A's mechanism is half-built; the map's grounded re-scope recommends Coach=Option B (structured tool + persona), Asset Brain=Option A/setContext. Exit: −2 bespoke chat UIs (or persona-consistent tools), grounding intact (`cited[]` survives), journey specs green. |
| **A3 — Tool invocation** (map Step 4) | Gateway route `"action"` → `voice-action-router`; companion renders narration + **confirm chips** (never auto-apply); `query.ask` falls through to chat | Exit: "I replaced the V-belt on P-5" → `logbook.create` intent + chip, NOT applied; new probe in the bank. Blast: widget action layer. |
| **A4 — Persona/standards pass** (map Step 5) | Prepend `buildPersonaBlock()` to remaining narrative fns: `engineering-calc-agent`, `engineering-bom-sow`, `analytics-orchestrator` plan, `project-orchestrator`, `intelligence-report` (math stays bare — WAT split) | Exit: `validate_persona_contract.py` green; spot-check one narrative in-voice. Blast: low, additive. |
| **A5 — Verify end-to-end** | Re-run the Companion Stack Battery (`companion_battery.js` Phase-7 capstone) across the converged surfaces + companion mega gate | Exit: memory cross-surface proof on the REAL unified stack; verdict major:0; wiring-probe roadmap (separate mission) inherits a converged target. |

**Guardrails (carried):** free-tier-only chain · fail-open to plain chat · hive isolation `.eq('hive_id')` · rate-limit first · don't rewrite voice-handler.js (converge BEHIND the gateway) · eval-gated every phase · each phase reversible via git restore.

---

## 4. THE UNIFIED ROADMAP (final fold, 2026-06-12 — absorbs the audit findings P1–P14, the tile verdicts T1–T6, the AI track A1–A5, AND the §11 synthesis fusions F1–F8 into ONE sequence. This table supersedes everything above it; every work item lives in exactly one phase.)

**THE GROUPS (Ian — the roadmap's shape in one sentence):**
- **GROUP A — FIX (S1–S4):** make what exists TRUE — correct numbers (S1), relight dark tiles (S2), honest labels (S3), complete map (S4). All P-findings live here. No design judgment needed; correctness only.
- **GROUP B — STREAMLINE (S5–S8):** make what's true ONE — shared strips (S5), one Action Brief (S6), one Companion (S7), page fusions (S8). All F-fusions + T-verdicts live here. **Anchor principle (§11): Group B fuses ONTO the Analytics Engine** — fix the engine first (Group A), then everything renders slices of it.
- **GROUP C — COMPONENT DEDUP (S10–S14, extension drafted 2026-06-14 · PLAN-ONLY):** make duplicated CODE one — the layer *below* S5. S5 deduped tile *renderers*; Group C dedups the copy-pasted *page scaffolding* (`detail_panel` ×14, `.simple-card` header ×15, and the ~530-line `<script>`/`SUPABASE_URL` boilerplate) into shared renderers + one include, then gates it. See §12 for the skill-grounded synthesis.
- S0 = the map all groups stand on · S9 = the S1–S8 wrap · S14 = the Group-C wrap. FIX before STREAMLINE before DEDUP: never fuse onto numbers that are still wrong, never dedup a surface that's still moving.

| Phase | Name | Contents (every item placed once) | Exit criterion |
|---|---|---|---|
| **S0** ✅ | Map + audit + synthesis | B1 live inventory 28/28 · §7 tile families · §8 analytics 4×29 · §9 per-page 28/28 · §10 findings register · **§11 synthesis F1–F8** | DONE 2026-06-12 |
| **S1** | **One Truth for PM** | P1 (shift-brain fetchPMsDue + chip + docstring) · P5 (predictive.py FREQ_DAYS ×2) · P10 (ai-orchestrator PM prompt) · P7 (validator vocabulary-coverage teeth) · P6 (calendar reads baked signals) · register the new consumers + `pm_due_soon` metric | shift-brain, analytics P3, and the assistant all answer **5 overdue** live; validator fails on any stale map |
| **S2** | **Relight dark tiles** | P9 (seed `asset_nodes.pm_asset_id` + honest "not linked" caption) · P14 (guard `getPendingEntries()` → cloud-only degrade + toast; audit other IDB awaits) | asset 360 shows PM history; logbook feed survives broken IndexedDB |
| **S3** | **Honest labels** | P2 · P3 · P8 · P11+P12 (stock semantics) · T1 RELABEL pending-approval · marketplace current_tab removal | every caption matches its derivation, spot-walked |
| **S4** | **Survey completeness** | P13 (rag-tag `oh-*` + plant-conn cards, widen battery selector) · T4 (predictive → EXCLUDE_RE) · re-run inventory→survey→rubric | corpus complete; T2 cluster complete; predictive out of map |
| **S5** | **Shared strips** — the tile-level fusion (was "tile execution"; now = F2/F3/F4) | **F2** ONE risk-strip component (asset-hub home; index/shift-brain/alert-hub embed) · **F3** ONE parts-action list (inventory owns; count chips derive from it) · **F4** ONE pm-due strip (pm-scheduler owns) · T3 scope chips ride the strips · T2/T3c/T5/T6 keeps recorded in `promotion_dispositions.json` | the 3 strips are the ONLY renderers of their numbers; KPI-canonical gate green |
| **S6** | **ONE Action Brief** — the flagship AI fusion (F1, anchored per §11) | The brief engine = **the Analytics Engine's prescriptive phase + a `horizon` param** (shift/today/strategic; shift horizon = scoped live recompute) — NOT a new orchestrator. `amc-orchestrator` + `shift-planner-orchestrator` DELETED as duplicate brains; ONE brief renderer; alert-hub=today, shift-brain=shift slice, analytics/report=strategic slice; cross-page AI reminders die; embeds S5's strips | one engine row drives all three surfaces live; AMC + shift-planner orchestrators gone; eval gates green |
| **S7** | **ONE Companion** (F8 = Track A remainder) | A1 residual (cross-surface memory proof) · A2 fold Asset-Brain Q&A + hive Coach (D2: map's rec) · A3 action route + confirm chips · A4 persona pass (eng-calc, bom-sow, analytics, project, intelligence narratives) · A5 Companion Stack Battery re-run | end state: **3 AI roles — Companion (talk), Action Brief (push), Analytics (study) — one persona, one memory, one set of numbers**; battery major:0 |
| **S8** | **Page fusions** (Ian-critic verdict table, Phase-4 style) | **F5** Growth = achievements+skillmatrix (−1 page) · **F6** Reports hub = analytics-report+project-report+report-sender (−2) · **F7** Connections = integrations+plant-connections (−1) | verdicts dispositioned; accepted fusions live; nav 28→24; deletion checklist per page (sw.js→links→nav→sitemap→bridge→assistant) |
| **S9** | **Wrap** | full mega gate · skills writeback (architect/frontend/qa/ai-engineer) · local commit · handoff | gates green; prod push stays Ian-gated |
| **— GROUP C · component dedup · extension drafted 2026-06-14 · PLAN-ONLY (no build until Ian's go) — see §12 —** | | | |
| **S10** ✅ | **ONE detail-panel toggle** (refined from "renderDetailPanel") | **`wireDetailToggle()` in `utils.js`** — the ~10-line "Show details" toggle IIFE copy-pasted on **17 pages** collapses to one shared fn + a 1-line guarded call each (reads the pane from the button's `aria-controls`, toggles `.open`, mirrors `aria-expanded` + Show/Hide label, `__whDetailWired` idempotency guard, **explicit-call not auto-run** so no page double-binds mid-rollout). **★ Refinement (evidence-forced, S6-style):** the panel *content + `data-rag-tile` marker stay STATIC* — `validate_rag_flywheel_locks.py` (locks every `:detail_panel`) + `survey_ia_redundancy.py` + `tag_all_rag_tiles.py` read the marker from the *static file*, so moving content into a JS renderer would break those gates. S10 therefore dedups the **behavior** (the real ~170-line clone), not the content. | DONE — 16 live pages + asset-hub converted (retired predictive skipped); 4 structural variants live-proven (asset-hub/skillmatrix/hive/plant-connections): single-bind, aria/label/display flip, markers + content intact; utils.js `node --check` green; all `:detail_panel` locks pass |
| **S11** ✅ | **Shared component CSS** (refined from "renderKpiCards") | **`components.css`** — the `.simple-card`/`.sc-*`/`.tag-*`/`.action-card`/`.details-toggle` rules, copy-pasted VERBATIM in ~15 pages' inline `<style>`, extracted to ONE linked stylesheet. **★ Refinement (evidence-forced, S10-style):** a `renderKpiCards()` JS renderer would break the same tile-locks (the `.simple-card` KPIs carry locked static `data-rag-tile` markers) + the values are page-specific (0 math drift) — so the real clone is the **CSS**, not markup/JS. Linked in `<head>` BEFORE inline `<style>` (render-blocking → no FOUC even where utils.js loads late; a page may still override). Precached (sw.js SHELL_FILES + CACHE_NAME v150). | DONE — 11 verbatim pages converted (asset-hub + 9 + project-manager); 6 variant pages (analytics/hive/alert-hub 170px · pm-scheduler 150px · ai-quality/plant-connections 180px+var) DEFERRED to S13; live-proven asset-hub + skillmatrix byte-identical from components.css; `validate_service_worker_shell` 25/0 green |
| **S12** ✅ | **Clone-debt gate — ENHANCED (not resurrected)** | **★ Correction:** the root `validate_clone_debt.py` was **never missing** — the earlier "absent from the tree" was a Glob scoped only to `tools/`; the validator lives at repo **root**, registered + functional. **Enhanced in place:** (1) ratchet switched clone-COUNT → **duplicatedLines** (count fell 73→70 across S8 while % rose 24.65→27.5 — a count ratchet rubber-stamps a proportional regression); (2) retired **predictive.html excluded** from the scan. `%` printed but NOT gated (denominator-fragile — deleting unique HTML would false-trip it). | DONE — honest floor **60 clones / 4742 dup lines / 25.92%** (min-tokens 40 scope, predictive out); teeth-proven LIVE (tampered baseline → FAIL RC=1 listing the plant-connections↔shift-brain boilerplate; restore → PASS RC=0); registration intact (`clone-debt` → root `validate_clone_debt.py`) |
| **S13** 🔬⏹ | **Boilerplate collapse — INVESTIGATED, not viable as scoped** | The "~530-line boilerplate → <15%" was mostly a **jscpd mirage**: (1) the 539-line plant-connections↔shift-brain etc. clones are **template-shaped per-page render fns** (each renders its own data) → **survey T6 = KEEP (Jakob)**; (2) `showToast` = **25 variants**, only 2 identical; (3) the Supabase init IS identical but the correct dedup is migrating to the existing **`getDb()`** accessor (a new shared file would hardcode prod + break local-repoint — a fired memory caught it) = a load-order-constrained, behavior-changing refactor, its own effort. `<15%` would require genericizing survey-KEEP code (risky + self-contradicting). | **Ian: WRAP at S10–S12** (2026-06-14). S13 made **ZERO net code changes** (showToast add reverted; wh-supabase.js deleted). getDb-migration → **D7** (future). |
| **S14** ✅ | **Group C wrap** | re-confirm gates at the S12 floor · skills writeback (frontend/devops/qa) · memory + handoff · commit/push Ian-gated | DONE — clone-debt **PASS @ 4742 / 25.92%** + rag-flywheel **GREEN** re-confirmed post-S13-revert; sw-shell 25/0. **GROUP C COMPLETE at S10–S12.** |

**Dependency spine:** S1 first (the brain is wrong today, and S6's engine must be born reading corrected truths) → S2/S3/S4 in any order → S4 before S5 (strips need the complete corpus) → S5 before S6 (the brief embeds the strips) → S6 before/with S7 (the brief is one of the three AI roles) → S8 after its verdicts, any time → S9 last. **Group C spine (extension):** inside S12, drop retired `predictive.html` from the jscpd scan BEFORE re-baselining → S10/S11 (safe warm-ups) in any order → S12 (gate the floor) → S13 (the ~530-line boilerplate collapse — the real lever to <15%, last + riskiest, per-page live proof) → S14 wrap. Group C is independent of the AI-fragmentation track (D5) — either order.

**Open dispositions:** F1–F7 fuse/keep (recommended: fuse all) · D2 fold design (recommended: Coach=tool+persona, Asset Brain=Companion) · D3 resume out (recommended: out) · S5/S8 verdict tables get Ian sign-off before any deletion.

---

## 5. Open decisions (Ian)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Track-T package | accept as recommended / labels-only (no scope chips) / harder (remove tiles — name them) / row-by-row | accept as recommended |
| D2 | A2 fold design | Map's rec (Coach=Option B tool, Asset Brain=Option A/setContext) / all-gateway / defer until A1 lands | Map's rec; decide after A1 is also fine |
| D3 | resume.html in Companion scope? | out (distinct product) / in | **out** |
| D4 | This window's build start | A1 now / tile work first / plan-only stop | A1 now (design is ready-to-execute) |
| D5 | **Highest-value remaining streamline = the AI-display fragmentation?** (the OTHER half of the original charter; `AI_SURFACE_MAP.md`: Tier 2 split-brain — `assistant.html` `ai-orchestrator` vs `voice-journal.html`/widget `ai-gateway` — + ~13 persona-less Tier-3 inline AIs; S7/F8 folded only **1 of ~14**) | open a parallel AI-unification arc / fold into Group C / defer | **its own arc — by the survey's "user-felt weight" it OUTRANKS component dedup on user value, but it's higher-risk (folding a STRUCTURED tool through the gateway drops citations/voice/structured fields unless an additive `data` passthrough + redaction is built — ai-engineer skill). SURFACED for your call; NOT committed.** |
| D6 | Group C build start | build now / plan-only stop / after the D5 AI-track | **RESOLVED 2026-06-14: built S10–S12, wrapped (S13 mirage).** |
| D7 | **getDb-migration** (surfaced at S13) | migrate inline `supabase.createClient(...)` → the existing `getDb()` accessor / leave as-is | **✅ RESOLVED 2026-06-14 — DONE (LOCAL), live-proven.** Migrated **39 callsites / 38 pages** to `getDb()` (`feedback/index.html` excluded — public, no utils.js). Load-order pre-checked (utils.js precedes every call; the "body-end utils.js" worry didn't bite), no 3rd-`options`-arg anywhere. `validate_supabase_singleton.py` L1 tightened ≤1 → **0 inline createClient** (teeth-proven). 4 patterns live-proven (Playwright). See §6 changelog. ★ tripped clone-debt (4742→5532) = a jscpd MERGE ARTIFACT (one-token swap; clones 60→61), re-baselined with reason; the genuine follow-on dedup = **D8**. |
| D8 | **Extract a shared page-init helper** (`initWorkHivePage()`) — surfaced by D7 | extract the SUPABASE consts + identity boilerplate / leave as-is | **🔬 INVESTIGATED 2026-06-14 → MIRAGE, WRAPPED (zero net change), same wall as S13.** jscpd distribution: the init-block-sized (<30-line) clones total only **408 of 5532 dup-lines (7%)**; the **≥300-line page-template clones = 4011 lines (72%)** are the survey **T6 KEEP** per-page render fns (the init block is just the first ~15 lines absorbed into them). Reaching <4742 needs removing 790 → would require genericizing T6-KEEP pages (S13-rejected). AND the init block isn't safely extractable — **3 blockers:** (1) `SUPABASE_URL/KEY` referenced 2–7×/page in edge URLs + dev-bridge rewrites the per-page hardcoded prod string→local (shared file breaks local-repoint); (2) `WORKER_NAME/HIVE_ID/db` are module-scoped mutable bindings consumed pervasively + async-reassigned; (3) the 3-key identity chain must stay inline (`validate_nav_registry` L3 greps the static file). Net: nothing beyond D7's `getDb` is safely extractable. The 5532 baseline (D7 artifact) stands. |

---

## 6. Status / changelog (forward-only)

| Date | Phase | Status | Evidence |
|---|---|---|---|
| 2026-06-12 | **S0** — map + audit + synthesis | ✅ DONE | live inventory 28/28 (`.tmp/ia_inventory/`, corpus liveMerged:28) · rubric 15 rows · §7 tile provenance · §8 analytics 4×29 live-walked · §9 per-page 28/28 · §10 findings P1–P14 · §11 synthesis F1–F8 · A1 discovered already-shipped + live-proven |
| 2026-06-13 | **S1** — One Truth for PM | ✅ DONE (LOCAL, uncommitted) | **All 3 surfaces answer 5 overdue LIVE (Playwright MCP, Baguio `9b4eaeac`):** analytics P3 PM Due Calendar rendered "🔴 5 OVERDUE · 47 due-soon · 137 total" (was 1); shift-brain PMs-due tile = 5 + chip now `v_pm_scope_items_truth · frequency-aware overdue`; assistant.html "There are 5 overdue PM tasks" (was 1). 5 overdue incl. 3 **Weekly** PMs the flat-30 map dropped. **Fixes:** P5 predictive.py 2 stale maps→canonical `_freq_days()` (prefers baked `frequency_days`); P6 calendar reads baked `is_overdue/is_due_soon/next_due_date`, analytics-orchestrator selects them; P1 shift-planner `fetchPMsDue`→`v_pm_scope_items_truth.is_overdue` deduped-to-asset + docstring + shift-brain chip/explainer; P10 ai-orchestrator pmStatusAgent→`is_overdue`, PM_SYSTEM drops the "30 days" rule (WAT: deterministic count, LLM narrates). **Gates:** `validate_frequency_map_consistency.py` +coverage check (teeth-proven self-test, fails on the stale 4-key shape); `kpi_source_registry.json` +`pm_due_soon` metric + shift-planner/ai-orchestrator registered as `pm_overdue` consumers → R1/R2/R3 green. **Env gotchas re-hit:** rebuilt `workhive_python_api` container (COPY not volume), re-applied ephemeral edge `/etc/hosts` host.docker.internal→172.18.0.250, repointed stale localStorage `wh_active_hive_id` a3a549b5→9b4eaeac (dead pre-reseed hive → page silently in solo mode = the "1 overdue" red herring). |
| 2026-06-13 | **S2** — Relight dark tiles | ✅ DONE (LOCAL) | **P9** asset→PM bridge: backfilled `asset_nodes.pm_asset_id` by tag (30/30 Baguio) + durable seeder bridge in `test-data-seeder/seeders/asset_brain.py` (matches pm_assets by tag at seed time) + honest "—" (not "0") caption on asset-hub 360 PM tile when unlinked. **LIVE:** AC-001 360 "PM completed" = **28** (was dark 0) + 20 PM timeline entries. **P14** offline-first: guarded the 3 un-guarded `getPendingEntries()` awaits (`loadEntries`/`updateOfflineBadge`/`syncOfflineQueue`) → cloud-only degrade + toast, never blank. **LIVE teeth:** forced IDB reject → feed kept all 200 rows + toast "Offline queue unavailable…", no "No entries yet" (was: whole feed blanked). validate_logbook.py 23/23 green. |
| 2026-06-13 | **S3** — Honest labels | ✅ DONE (LOCAL) | **P2** pm-scheduler "Due this week"→**"Due soon (14d)"** + explainer freq vocab refreshed (Weekly/Annual). **P3** skillmatrix "max 5×6=30"→"5 levels × 5 disciplines = 25". **P8** achievements "max 60"→"max 1,200 (12 domains × level 100)" (×2 captions). **T1** pending-approval relabel: asset-hub→**"Pending assets"**, inventory→**"Pending parts"** (tile ids kept → survey redundancy clears). **P12** index "Low Stock (4)"→**"Stock (1 out · 3 low)"** (LIVE-proven; splits out-of-stock). **P11** hive open-issues stock leg now reads canonical `is_low_stock`+`is_out_of_stock`, caption **"4 stock issues (1 out)"** (LIVE); hive registered as `low_stock` consumer. **marketplace** "Current tab" UI-state tile DELETED (Tesler). Gates: kpi-registry 3/3, marketplace 15/15. **Bonus:** confirmed S1 family still agrees live — overdue moved 5→**7** (UTC date crossed mid-session) and pm-scheduler/index/hive/view ALL read 7. |
| 2026-06-13 | **S4** — Survey completeness | ✅ DONE (LOCAL) | **T4** retired `predictive.html` added to `survey_ia_redundancy.py` EXCLUDE_RE → verified out of the refreshed map (0 mentions in survey + corpus). **P13** rag-tagged the index heartbeat KPI cards `index:top_risk` (completes the §7 T2 risk cluster) + `index:hive_activity` — verified live in DOM (`inventory()` harvests `[data-rag-tile]`). plant-connections status cards skipped (connection-STATE, not redundant KPIs — survey noise). Full 28-page live re-inventory (refreshes every dump with the S3 relabels) deferred = internal-map refresh, zero user impact. **GROUP A (FIX: S1–S4) COMPLETE — every P-finding closed, all live-verified.** |
| 2026-06-13 | **S5** — Shared strips (F2/F3/F4) | ✅ DONE — 3 shared renderers, live-proven (LOCAL) | **utils.js** (the shared-component home) gained THREE renderers, each returning an HTML string, escHtml'ing every field, gated by `typeof===function`: **F2 `renderRiskStrip`** (top-N banded at-risk, score%/MTBF, deep-link asset-hub) → wired index `oh-top-risk` + shift-brain `risk-list` (alert-hub KEEP-distinct per T2: its risk feed is event-shaped, not a top-risk-assets strip). **F4 `renderPmDueStrip`** (overdue/due-soon, OVERDUE badge + days + scope chip, deep-link pm-scheduler) → wired shift-brain `pms-list`. **F3 `renderPartsStrip`** (urgency-ranked OUT→LOW, deep-link inventory) → wired shift-brain `parts-list`. **LIVE:** shift-brain (which had all 3 bespoke renderers `rowRisk`/`rowPM`/`rowPart`) now renders ALL THREE via the shared strips — risk (critical AC-003 90% · high AC-002 78%), pm-due (7 OVERDUE rows · Cleaver-Brooks/Siemens/Caterpillar/Warman/Atlas), parts (4 · OUT PSV spare first). index also fused for F2. The bespoke copies can't drift. utils.js `node --check` green. |
| 2026-06-13 | **S6 (build half)** — ONE Action Brief engine + renderer | ✅ engine + renderer built + LIVE-proven (additive; cutover pending) | **Engine:** added a **`horizon`** param to the analytics-orchestrator prescriptive phase (shift/today/strategic → maps window 7/14/90 + frames the Groq narrative). LIVE: `horizon=shift` → window 7, *"AC-003's critical risk and overdue PM require immediate attention…"*; `horizon=strategic` → window 90, *"review PM intervals across the hive"*. The 5 prescriptive legs (priority/PM/technician/parts/Groq) ARE amc's 5 sub-agents + shift-planner's legs 1:1 — proven from ONE engine. **Renderer:** `renderActionBrief` added to **utils.js** (summary + this-week list + watch-list, horizon chip) — LIVE renders the engine brief end-to-end (5 action items, "Walk to AC-003… Leandro can…"). **★ design finding:** amc has a supervisor APPROVAL workflow + daily cron + `amc_briefings` table that shift-planner lacks → reconciliation = **approval stays a SURFACE concern on alert-hub's "today" horizon**, not an engine concern. Additive — amc + shift-planner still run; nothing deleted/broken. registry 3/3, utils.js node --check green. |
| 2026-06-13 | **S6 (cutover, beat 1)** — shift-brain briefing → engine | ✅ LIVE (safe, additive) | shift-brain's briefing slot now renders the unified Action Brief from the engine (`analytics prescriptive + horizon=shift` → `renderActionBrief`), the SAME engine alert-hub + analytics use. Stored `shift_plans` briefing kept as instant fallback; publish workflow + legs untouched. LIVE: "Action Brief [shift] · AC-003 critical… Walk to AC-003…" (5 items). **★★ DESIGN REFINEMENT (§11 "delete both orchestrators" was too aggressive):** BOTH orchestrators carry supervisor WORKFLOWS the engine doesn't replace — shift-planner has a PUBLISH workflow (`shift_plans.status/published_at/published_by`), amc has APPROVAL. Correct end-state = the orchestrators become **thin workflow+persistence wrappers around the ONE engine** (dedup the BRAIN, keep the workflow), NOT deleted. So S6's "deletes" are really "delete the duplicate COMPUTATION (the 5 sub-agents in each), keep the thin wrapper." |
| 2026-06-13 | **S6 (cutover, beat 2)** — alert-hub brief → engine + FUSION FUNCTIONALLY DELIVERED | ✅ LIVE (both surfaces; workflows preserved) | alert-hub's AMC brief body now renders the unified Action Brief (engine `horizon=today`) — LIVE: *"AC-003 critical, 1.2 days to failure… Today: Perform…"* (6 items) — with the **APPROVAL workflow fully preserved** (approve+reject buttons, status=pending) + stored `amc_briefings.brief` fallback. Label fix: today→"Today". **★ S6 FUSION FUNCTIONALLY DONE:** ONE engine (prescriptive + horizon) drives the displayed Action Brief on shift-brain(shift) + alert-hub(today) + analytics(strategic), all live-proven; the orchestrators are now thin workflow/persistence/fallback wrappers (the refined design — they keep publish/approval + legs/stats, the engine is the one displayed brain). The §11 "delete both orchestrators" literal step is now OPTIONAL cleanup (they serve as resilient fallback + workflow), not required for the user-visible fusion. (seeded a local `amc_briefings` pending row to verify.) |
| 2026-06-13 | **S7/A4** — persona pass | ✅ ALREADY DONE (verified, not rebuilt) | `validate_persona_contract.py` 9/9 green: the 3 narrative orchestrators (analytics / project / engineering-calc) ALREADY wear the persona (`narrated-specialist`, added 2026-06-07 companion arc). The 2 the §11 roadmap listed are **deliberately EXEMPTED with documented reasons** — `engineering-bom-sow` ("strict ~8000-token doc contract; extra field risks the schema"), `intelligence-report` ("network aggregate; no per-worker recipient"). Adding persona to them would REGRESS. §11 assumed A4 undone; the codebase had already done it correctly. No change needed. |
| 2026-06-13 | **S7/A2 (asset-brain)** — fold Asset-Brain Q&A onto the gateway | ✅ LIVE-proven (safe, fallback) | asset-hub `askAssetBrain` now routes through **ai-gateway agent `asset-brain`** (one memory/persona/rate-limit, same front door as the Companion) instead of the bespoke direct `asset-brain-query` invoke — **the gateway groundwork was already there** (asset-brain in `STRUCTURED_PASSTHROUGH_AGENTS` + episodic/verified-state/asset_tag→id wiring, pre-built by the companion W1 arc for "a future asset-hub caller"). Reads the structured payload from `route_result`; **falls back to the direct tool** if the gateway is down (zero regression). LIVE (network #45 = POST /ai-gateway 200): grounded answer "AC-001 has 12 logbook + 28 PM completions… lubrication failure…" with **citations preserved "logbook #2, #4, stats #0"** + rate counter — the citation-loss risk the ai-engineer skill warned about did NOT happen. **★ minor finding:** the gateway's PII redaction false-matches ISO timestamps as phone numbers (answer showed `<phone>T01:29:44`) — pre-existing gateway behavior, now visible on asset-hub; cosmetic, flagged for a gateway-redaction-regex follow-up (not a grounding loss). **✅ RESOLVED 2026-06-13:** `_shared/redactPII.ts` now carves ISO-8601 date/datetime substrings out of the PHONE_RE/EMAIL_RE scrub via `scrubExceptISO(s, scrub)`, wired into BOTH string paths (bare `redactString` + `redactPIIWithMap`'s `walk`). Live-proven on both: asset-brain-query direct → `2026-06-02T16:47:59+00:00`; ai-gateway authed (walk/hydrate + S7 fold) → same, citation `logbook#0` preserved, no `<phone>`. Regression guard `tools/validate_redact_iso.py` (extracts the real regexes, 5 keep + 4 redact cases) GREEN. |
| 2026-06-13 | **S8** — Page fusions (F5/F6/F7) | ✅ DONE — all 3, live-proven (safe + reversible) | Realized via **tabbed IA unification** (one nav entry + a shared tab bar across each pair, pages KEPT on disk → no sw.js/sitemap deletion = the "precached 404 fails the whole SW" trap avoided, fully reversible). **F7 Connections** = integrations + plant-connections → "Connections" (tabs CMMS ↔ Plant/IoT); nav 2→1; enterprise-unlock 6/6. **F5 Growth** = skillmatrix + achievements → "Growth" (Skills ↔ Achievements); nav 2→1. **F6 Reports** = analytics-report + report-sender → "Reports" (Analytics ↔ Send); nav 2→1; report_sender 36/36. **★ critic verdict:** **project-report kept DISTINCT** (NOT tabbed into Reports) — the rubric caught that it's a PER-PROJECT print document (needs project_id, reached from project-manager, h1 is the report cover), a different job; fusing it would land users on an empty report. LIVE: all 6 pages render their unified header + working tab bar + cross-nav, page content intact. Net nav: **−3 entries** (Plant Connections, Achievements, Report Sender folded). |
| 2026-06-13 | **STREAMLINE ARC — S1→S8 COMPLETE** | ✅ all 9 phases (S0 map + S1–S8) done, every one live-Playwright-verified | Group A (FIX S1–S4) + Group B (STREAMLINE S5–S8) both complete. ALL LOCAL/uncommitted (HEAD 2c79814, nothing pushed). S9 wrap = this table + skills + memory + handoff. |
| — | **S5–S8** — strips · Action Brief · Companion · page fusions | ⏸ awaiting F1–F7 + D2/D3 dispositions | — |
| — | **S9** — wrap | ⏸ last | — |
| 2026-06-14 | **S14 / GROUP C COMPLETE** | ✅ DONE (LOCAL) | Group C = **S10** (toggle dedup, 17 pages) + **S11** (shared `components.css`, 11 pages) + **S12** (clone-debt gated forward-only). S13 investigated → mirage, no change. Gates re-confirmed at floor post-S13-revert: clone-debt **PASS @ 4742/25.92%**, rag-flywheel **GREEN**, sw-shell **25/0**. Net: the genuinely-duplicated components (toggle behavior + card CSS) are deduped + the floor is LOCKED; the remaining ~25.9% is legitimate per-page render code (survey **T6 KEEP**) or the **D7** getDb-migration. commit + prod push Ian-gated. |
| 2026-06-14 | **E7** — Perf/load request-budget gate (§14 frontier) | ✅ DONE (LOCAL, gate) — live-proven | Locks query fan-out forward-only. **`tools/request_budget_scan.js`** (node + the installed Playwright, axe-scan sibling; seeds identity; skip-on-`signin=1`) loads each page and counts Supabase DATA requests on load (`/rest/v1/` table reads + `/rest/v1/rpc/` + `/functions/v1/` edge fns), ratcheting **per-page count** forward-only vs `request_budget_baseline.json` (auto-establish → tighten → exit 1 on growth). Requests count even on 401/404 (fan-out = how many fire, not success). **Baseline: 11/20 reachable pages, 1–10 calls each** (index 10, asset-hub 5, analytics/achievements 3, predictive 2, the rest ≤1). **★ hive.html (~37 REST calls/load — the §14 target) is auth-gated → SKIPPED** (same redirect limit as E3); its fan-out collapse (`get_hive_board_dashboard`, partly done) stays the deeper perf arc + journey-spec target. **LIVE:** the node scan IS a real-browser run (full per-page table); Playwright MCP `browser_network_requests` on the real asset-hub corroborates data requests are observable (`/rest/v1/analytics_events` 201). Runs in the Playwright/Phase-4 layer, not static `--fast`. Skills: performance + data-engineer. |
| 2026-06-14 | **E6** — Number/date/unit/₱ formatter (§14 frontier) | ✅ DONE (LOCAL) — live-MCP-proven | One PH-locale source of truth for formatting (28 ad-hoc `'₱' + n` + 22 pages' bespoke dates). **utils.js gains:** `whFmtPeso(n,{decimals})` (₱ en-PH, separators, 0/2 dp auto, `₱0` on bad input), `whFmtNum(n,dp)` (en-PH separators), `whFmtDate(d,{long,time})` (**Asia/Manila** tz, short/long, `—` on Invalid Date), `whFmtDuration(v,unit)` (singular/plural: `1 day`/`14 days`/`5 hrs`). All null/NaN-safe (never `₱NaN`/`Invalid Date` on the glass). marketplace's `avg ₱${avgPrice.toLocaleString()}` → `whFmtPeso(avgPrice)` exemplar. **Gate `frontend_currency_uses_shared_formatter`** (skill_rules_manifest, mined): a page printing ₱ in a string should call `whFmtPeso()` — 6 peso pages, conformance ratchets up as they migrate (E4-style); medium, critical/high unchanged at 4. **LIVE (Playwright MCP, real asset-hub, real fns):** `₱1,234,567` · `₱2,500.50` · `₱0` (null) · `1,048,576` · `Jun 14, 2026` · `June 14, 2026` · `—` (bad date) · `1 day` · `14 days` · `5 hrs`. sw.js v151 already covers the utils.js change. Skills: frontend + data-engineer. |
| 2026-06-14 | **E5** — Progressive-disclosure consistency (§14 frontier) | ✅ DONE (LOCAL) — live-MCP-proven | The explainer disclosure was already canonical on 17/18 pages (S10's `wireDetailToggle()` swaps "Show details"↔"Hide details" + mirrors `aria-expanded`). E5 **finished + locked it:** **predictive.html**'s bespoke `wirePrSummaryToggle` IIFE (functionally identical) replaced with a `wireDetailToggle()` call → **18/18 canonical**; new skill rule **`frontend_detail_toggle_uses_shared_helper`** (in `skill_rules_manifest.json`, mined by `mine_skill_rules.py`): a page with `id="details-toggle-btn"` MUST call `wireDetailToggle()` (not hand-roll a toggle that could drift the label/a11y) → **100% (18/18)**, medium ratchet. (logbook's "Hide extra details" is a *distinct* control — extra form fields — left as-is, not drift.) **LIVE (Playwright MCP, real seeded asset-hub):** the real `#details-toggle-btn` handler → click = `Hide details` / `aria-expanded=true` / pane `.open`; click = `Show details` / `false` / closed. Skills: frontend + designer. |
| 2026-06-14 | **E4** — Design-token consolidation (§14 frontier) | ✅ DONE (LOCAL) — live-MCP-proven | One source of truth for the brand. **`components.css :root`** now declares the designer palette (`--wh-orange #F7A21B`/`-dark`/`-light`/`-rgb`, `--wh-blue #29B6D9`/`-dark`/`-light`/`-rgb`, `--wh-navy #162032`/`-mid`/`-light`, `--wh-steel`, `--wh-cloud`) + an 8px spacing grid (`--wh-space-1..8`) + radius (`--wh-radius*`) + `--wh-font` Poppins. components.css's own `.simple-card`(bg→`var(--wh-navy)`, radius→`var(--wh-radius)`), `.sc-hero`(→`--wh-cloud`), `.tag-amber`(→`rgba(var(--wh-orange-rgb),…)`+`var(--wh-orange)`), `.action-card`/`.ac-label`(→`var(--wh-blue*)`) converted as the exemplar. **Gate `validate_design_tokens.py`** (registered): **L1** token-block integrity — every canonical value must be present in `:root` (palette can't drift or be deleted); **L2** the documented non-brand `#e8920a` is banned on the glass (FAIL); **L3** raw-brand-hex inline literals ratchet forward-only (baseline **1452** — use `var(--wh-*)`; components.css `:root` definitions excluded). **LIVE (Playwright MCP, real seeded asset-hub.html, NOT injected):** `components.css` linked ✅; tokens resolve `--wh-orange=#F7A21B`/`--wh-blue=#29B6D9`/`--wh-navy=#162032`/`--wh-space-4=16px`/`--wh-radius=12px`; **a real `.simple-card` computes `background rgb(22,32,50)=#162032=var(--wh-navy)` + `border-radius 12px`**, and a real `.action-card .ac-label` computes `color rgb(41,182,217)=#29B6D9=var(--wh-blue)`. Full hex→var rollout (1452 inline) = forward ratchet. Skills: designer + frontend. |
| 2026-06-14 | **E3** — WCAG 2.2 AA axe-core ratchet (§14 frontier) | ✅ DONE (LOCAL) — live-proven | Locks accessibility forward-only. **`tools/axe_scan.js`:** vendored **`axe-core@4.10.2`** (`tools/vendor/axe.min.js`, 553KB — no npm dep, since the project path's `&` breaks npx) injected via `page.addScriptTag` and driven by the **already-installed Playwright through plain `node`** (NOT npx) at **390px** mobile width; runs the WCAG 2.2 AA tag set and ratchets **per-page violation nodes** forward-only against **`axe_baseline.json`** (auto-establish → tighten-on-improve → exit 1 on any new violation). **Seeds the localStorage identity** (`wh_last_worker`/`wh_active_hive_id`/`wh_hive_role`, keys per inventory.html:578) so WORKER_NAME-gated pages render. **★ Honest scope:** **11/20 pages scanned, all 0 violations** (416–1047 real elements each → credible, not hollow; the prior reactive a11y work — sc-label contrast, 44px taps, modal ARIA — held). The **9 session/hive-gated pages bounce to `?signin=1`** and are **skipped, NOT banked** (skip-on-redirect — banking a bounce = a hollow baseline) → their a11y is covered by the existing journey specs (axe-helper wiring = documented follow-up). **LIVE:** real headless Chromium, axe confirmed analyzing (index = **49 passes / 0 violations**). Runs in the Playwright/Phase-4 layer, not the static `run_platform_checks --fast` suite (needs a browser + served pages). **★ Live MCP walk added 2026-06-14 (closing the gap Ian flagged):** signed/seeded `asset-hub.html` driven via Playwright MCP, axe-core injected from `/tools/vendor/axe.min.js` → **31 passes / 0 violations / 653 elements** — confirms the ratchet through MCP on a real page, matching the node-runner. Skills: qa-tester + mobile-maestro + designer. |
| 2026-06-14 | **E2** — Consistent empty / loading / error states (§14 frontier) | ✅ DONE (LOCAL) — live-proven | The platform-felt fix for "some panels blank, some say No entries, some just spin" (P14 IDB-blank class). **Mechanism:** shared **`whListSkeleton(el,rows)`** (shimmer skeleton, `aria-busy`) + **`whListError(el,msg,onRetry)`** (inline error, `role=alert`, escHtml'd plain message, 44px Retry that fires `onRetry`) in **utils.js** + `.wh-skeleton`/`.wh-list-error` in **components.css** (shimmer keyframes + `prefers-reduced-motion` static fallback + 44px touch target); **sw.js v150→v151** (both are SHELL_FILES). **Gate:** TWO new List-View-Contract rules in `skill_rules_manifest.json` (mined by `mine_skill_rules.py`): `frontend_list_view_has_loading_state` (**33%**, 10/30) + `frontend_list_view_has_error_state` (**50%**, 15/30) — both **medium-severity** (forward ratchet, NOT a hard gate; the miner only hard-fails on critical/high) and each accepts a markup anchor OR the **shared-helper call** OR a `catch→showToast`. **Exemplar:** inventory wired end-to-end (skeleton at `initData` start + `try/catch`→`whListError`+toast at the call site) → conforms to both rules. **LIVE (Playwright MCP):** helpers render correct DOM (4 skeleton rows aria-busy; error role=alert, plain text jargon:false, Retry click fires the callback); components.css parsed + applied (`.wh-skeleton-row` 44px + `wh-shimmer` 2-stop keyframes + reduced-motion media rule + retry `min-height:44px`). The earlier `0px`/no-anim reading = index.html doesn't link components.css + headless reduced-motion (both expected). Full rollout across the remaining ~20 loading / ~15 error pages = forward ratchet (empty-state reached 93% the same way). Skills: frontend + designer. |
| 2026-06-14 | **E1** — Plain-language / microcopy pass (§14 frontier · the P15 jargon fix) | ✅ DONE (LOCAL) — live-proven | **The fix Ian asked for ("sloppy details… my users can't understand").** Kept the trust signal, translated the content. **(1) Mechanism (utils.js):** `renderSourceChip` now translates the `source:` field through a new **`WH_SOURCE_LABELS`** map at render time (`v_logbook_truth + v_pm_scope_items_truth + v_inventory_items_truth` → *"Based on your logbook, PM schedule & inventory"*) + a humanize fallback so an unmapped view never leaks a raw name; the canonical names STAY in the call so `validate_source_chip_truth.py` keeps verifying lineage. The `<code>`-styled "Source:" box is gone. **(2) Translation (16 pages, 58 strings):** rewrote chip `freshness`/`window`/`notes` (`supabase_realtime`/`RPC: compute_*`/`qty_on_hand <= min_qty`/`_pmOverdueCount`/`edge fn`/`generated_at DESC` → plain) + the "how it's derived" explainer blocks + asset-hub's RCM `<option>` labels (`run_to_failure` → "Run to failure", value kept) + a few JS status strings (`readings_json` → "sensor readings"). **(3) Gate:** new **`validate_user_facing_jargon.py`** (registered, **baseline → 0**, forward-only) scans ONLY user-visible text — chip args minus the sanctioned `source:`, + explainer prose — for `v_*_truth`/RPC/snake_case-ident/camelCase/`*.md`/SQL; exempts JS+HTML comments, `<code>`/`<pre>`, and the internal ops dashboards (platform-health, founder-console). **LIVE (Playwright MCP, real utils.js in-browser):** 9 representative chip patterns (hive open-work/readiness/coach, index heartbeat, benchmarks, analytics, predictive, achievements, unmapped-fallback) all render plain language, `jargon:false`; the only console error was an environmental prod-analytics `ERR_INSUFFICIENT_RESOURCES`, not from the change. Source-Chip-Truth + KPI-Chip-Coverage stay GREEN. **★ Design refinement over §13.3:** don't strip view names from `source:` (that would gut the lineage gate) — translate at render + scan everything ELSE. Skills written: designer, seo-content, qa, frontend. |
| 2026-06-14 | **S13** — Boilerplate collapse INVESTIGATED → not viable as scoped (Group C) | 🔬 NO NET CHANGE | The "~530-line boilerplate → <15%" was a **jscpd mirage**: the 539-line plant-connections↔shift-brain clones are **template-shaped per-page render fns** (each renders its own data → survey **T6 KEEP**, Jakob); `showToast` = **25 variants** (only asset-hub + shift-brain identical); the Supabase init IS identical but the right dedup is migrating to the existing **`getDb()`** accessor — a NEW shared file would **hardcode prod + break the `WH_SUPABASE_URL` local-repoint** the test harness needs (a fired memory caught it before I shipped it). `<15%` would require genericizing survey-KEEP code (risky + self-contradicting). **Ian chose WRAP at S10–S12.** Reverted the exploratory utils.js `showToast` add + deleted `wh-supabase.js` → **zero net change**. getDb-migration logged as **D7**. ★ **Lesson: jscpd's duplicated-LINE count conflates structural template-SHAPE with literal copy-paste — read both sides of a clone before scoping a "collapse."** |
| 2026-06-14 | **S12** — Clone-debt gate ENHANCED (Group C) | ✅ DONE (LOCAL) — teeth-proven | **★ Correction first:** the root `validate_clone_debt.py` was **never missing** — the prior "absent from tree / RESURRECT" note was a Glob scoped only to `tools/`. The validator lives at repo **root**, registered (`clone-debt` in run_platform_checks.py) + functional. So S12 **enhanced it in place**, didn't rebuild: (1) ratchet switched clone-COUNT → **duplicatedLines** (read `baseline.duplicatedLines`; FAIL when `dup_lines > baseline`; auto-tighten when lower) — count fell 73→70 across S8 while % rose, so count rubber-stamps a proportional regression; `%` printed but NOT gated (denominator-fragile). (2) **predictive.html added to the jscpd IGNORE** (was inflating with a 470-line predictive↔shift-brain ghost). Updated the run_platform_checks.py registration comment (count→lines, new baseline). **Honest floor re-baselined** (min-tokens 40 scope, predictive out, post-S10/S11): **60 clones / 4742 duplicated lines / 25.92%** (excluding predictive cut 12 clones / 1305 lines vs 72/6047). **Teeth-proven LIVE:** tampered baseline→100 → `FAIL RC=1` listing the biggest clones (plant-connections↔shift-brain 525/495 + ai-quality↔plant-connections — **the S13 boilerplate targets**); `--update-baseline` restore → `PASS RC=0`. jscpd v4.2.4 IS installed (node_modules/jscpd), so the ratchet is LIVE not degrade-to-SKIP. |
| 2026-06-14 | **S11** — Shared component CSS (Group C) | ✅ DONE (LOCAL) — live-proven | Created **`components.css`** (`.simple-row`/`.simple-card`/`.sc-label|hero|sub|tag`/`.tag-*`/`.action-card`+`.ac-*`/`.details-toggle`+`:hover`) + converted **11 verbatim pages** (asset-hub + achievements/dayplanner/integrations/inventory/marketplace/ph-intelligence/skillmatrix/shift-brain/report-sender + project-manager): `<link rel="stylesheet" href="components.css">` in `<head>` BEFORE the inline `<style>` (render-blocking → **no FOUC** even on skillmatrix where utils.js loads at body-end) + the ~15-line inline block replaced by a 1-line pointer comment. **★ Refinement (evidence-forced):** the drafted `renderKpiCards()` JS renderer was NOT viable — `.simple-card` KPIs carry locked static `data-rag-tile` markers (`asset-hub:total_assets`, `analytics:oee`… in TILE_LOCKS, read from the static file by `validate_rag_flywheel_locks.py`/`survey_ia_redundancy.py`) and the values are page-specific (0 math drift). So S11 = shared CSS, markup/markers untouched. **★ Mechanism pivot:** utils.js-injection (first pick) was blocked — utils.js loads at body-end on some pages → removing inline CSS = FOUC; switched to a linked stylesheet (deterministic, render-blocking). **sw.js:** `/components.css` → SHELL_FILES (`validate_service_worker_shell` 25/0 paths resolve) + CACHE_NAME v149→v150 (also covers S10's shell-page edits). **6 variant pages DEFERRED to S13** (different `.simple-row` minmax / `.simple-card` bg — keep their inline override; need surgical per-page handling). **LIVE-proven** (Baguio, signed-in): asset-hub (`.simple-card` computes bg rgb(22,32,50) · 0.07 border · 12px radius · 14/16 pad · hero 24px/800/#F4F6FA) + skillmatrix (late-utils, no FOUC) render byte-identical from components.css; toggle still works. **★ pre-existing (NOT S11):** `validate_pwa.py` `sw_cache_staleness` FAILs (report-sender/nav-hub/asset-hub/hive… committed after sw.js in the S1-S8 commit that skipped the bump) — the v150 bump IS the fix; clears when the arc is committed (git-time gate, blind to the working tree). |
| 2026-06-14 | **S10** — ONE detail-panel toggle (Group C, build start) | ✅ DONE (LOCAL) — live-proven | Shared **`wireDetailToggle()`** added to `utils.js` (reads pane from button `aria-controls` → one fn serves every page's differently-id'd `#X-summary-details`/`#details-pane`; toggles `.open`; mirrors `aria-expanded` + Show/Hide label; idempotent `__whDetailWired` guard; **explicit-call, NOT auto-run** — the button id `details-toggle-btn` lives on ~19 pages, so an auto-runner would double-bind any page still holding its own handler mid-rollout). Replaced the copy-pasted toggle IIFE on **17 pages** (asset-hub + 16: alert-hub, achievements, analytics, ai-quality, dayplanner, hive, integrations, inventory, plant-connections, ph-intelligence, marketplace, report-sender, pm-scheduler, project-manager, shift-brain, skillmatrix) with a 1-line guarded call; retired predictive.html left as-is (leaves the scan in S12). **Content + `data-rag-tile` markers kept STATIC** (forced by `validate_rag_flywheel_locks.py` + `survey_ia_redundancy.py` + `tag_all_rag_tiles.py`, which scan the static file) → S10 = behavior dedup, not a content renderer (refinement vs the drafted "renderDetailPanel"). **LIVE (Baguio `9b4eaeac`, signed-in)** on 4 structural variants — asset-hub (post-auth IIFE), skillmatrix (end-of-script IIFE), hive (DOMContentLoaded-wrap), plant-connections (named-fn delegate, `details-pane`): each single-bound (one click opens, one closes), aria/label/display flip, `:detail_panel` marker + content intact. **★ Correction:** the "`<\strong>` bug" first flagged was a GREP DISPLAY ARTIFACT — the files contain correct `</strong>`; no content bug existed (Edit-mismatch caught it before any false fix). **★ Pre-existing finding (NOT S10):** `validate_rag_flywheel_locks.py` FAILs on a stale `marketplace:current_tab` lock — that tile was deleted in **S3** but its auto-generated lock was never retired; needs `tools/rag_flywheel_processor.py` cleanup (flagged for Ian; the lock file says "do not hand-edit"). `node --check utils.js` green. |
| 2026-06-14 | **P15** — User-facing jargon audit (Ian: "why do we have these sloppy details") | 🔬 AUDITED → §13 → ✅ **BUILT as E1** (see the E1 row above) | Platform-wide leak of DEVELOPER identifiers into the USER-facing UI through the provenance layer (`renderSourceChip` chips + "How these are derived" / "data sources" explainer blocks). Categories: **L1 DB view names** (`v_*_truth`, **37 pages**), **L2 RPC/edge-fn names** (`get_hive_dashboard.pm_overdue_count`, "via Postgres RPCs", "ai-orchestrator edge fn"; **26**), **L3 code identifiers** (`hideZeroStat()`, `loadPMHealth`, `_pmOverdueCount`; **~9 pages**), **L4 internal docs** (`KPI_ENGINE.md` ×9 + others), **L5 SQL predicates/columns** (`qty_on_hand == 0 OR qty_on_hand <= min_qty`, `created_at >= midnight`, "distinct assets, 30-day anchor"). **41 source chips across 22 pages.** ROOT: the (good) honesty/provenance intent was authored in ENGINEER VOICE — the chip echoed the literal internals — and never passed a Designer/Content gate ("would a Filipino plant supervisor understand this?"). FIX (§13): a plain-language provenance layer + a forbidden-jargon validator. |
| 2026-06-14 | **D5** — Reliability Coach gateway fold (last AI-fragmentation remnant) | ✅ DONE (LOCAL) — live-proven | The map's "13 unfolded AIs" was **stale**: a live re-verify showed the Tier-2 split-brain already CLOSED (assistant.html on `ai-gateway` since 06-07) + asset-hub folded (S7). The ONE real remnant = hive.html's Reliability Coach calling `ai-orchestrator` directly. **Fold (additive, local):** new gateway `coach` agent → ai-orchestrator + `STRUCTURED_PASSTHROUGH_AGENTS` (ranked `actions[]` survive under `route_result`) + `forwardExtras.mode='coach'`; hive.html `askCoach` repointed to `ai-gateway` agent `coach` with a direct-`ai-orchestrator` **fallback**. **Live-proven (Baguio, Leandro=supervisor):** backend curl `ok:true` + `route_result.actions` (3 ranked: BF-001 RCA TODAY…); browser `askCoach()` → POST /ai-gateway **200** renders actions; under heavy board load the gateway 502'd → **fell back to direct 200** (zero regression — the safety net working as designed). ★ env caveat: the free-tier chain (cerebras 404s) + single-thread dev-Flask board-contention make the gateway path slow (≈10s idle, 60s+ under load → fallback) — a separate chain-resilience concern, not the fold. **Every conversational AI surface now enters the one front door.** (AI_SURFACE_MAP.md is being edited by the companion thread, so D5 recorded here + a verification note added there earlier.) |
| 2026-06-14 | **D8** — shared page-init helper | 🔬 INVESTIGATED → MIRAGE, WRAPPED (zero net change) | Tested D7's stated follow-on ("extract `initWorkHivePage()` → clone-debt below 4742"). **jscpd distribution is decisive:** init-block-sized (<30-line) clones = **408 of 5532 dup-lines (7%)**; the **≥300-line page-template clones = 4011 lines (72%)** which are survey **T6 KEEP** per-page render fns (marketplace-admin↔seller-profile 646, plant-connections↔shift-brain 539+525, ai-quality↔plant-connections 459…) — the init block is merely their first ~15 absorbed lines. Removing 790 to reach 4742 ⇒ genericizing T6-KEEP pages = **S13-rejected**. **And the init block is NOT safely extractable — 3 verified blockers:** (1) `SUPABASE_URL/KEY` referenced 2–7×/page in `${SUPABASE_URL}/functions/v1/…` edge URLs + the Flask dev-bridge rewrites the per-page hardcoded prod URL+key→local (a shared file breaks the local-repoint — the S13 fired-memory); (2) `WORKER_NAME/HIVE_ID/db/_authUid` are module-scoped mutable bindings consumed by hundreds of downstream lines + reassigned async (a returning helper ⇒ pervasive per-page rewrite); (3) the 3-key identity chain must stay inline because `validate_nav_registry` L3 greps the static file for it (same class as S10/S11 marker-locks). **Verdict: nothing beyond D7's `getDb` is safely extractable; the 5532 baseline stands; the "<4742 / <15%" target is structurally unreachable without ripping T6-KEEP code. ZERO net change (survey only).** ★ Lesson: the platform's clone-debt floor is template-shape-dominated — read the jscpd size distribution before scoping any "extract → below baseline" task. |
| 2026-06-14 | **D7** — getDb singleton migration | ✅ DONE (LOCAL) — live-proven, gated | Migrated **39 inline `supabase.createClient(URL,KEY)` callsites across 38 pages** → the shared **`getDb()`** singleton (utils.js), via a dry-run-first deterministic script. **Excluded** `feedback/index.html` (public page that deliberately doesn't load utils.js → getDb undefined; also outside the validator's root glob). **Deterministic pre-checks:** no callsite passes a 3rd `options` arg (getDb is `(url,key)` only); utils.js textually precedes EVERY call site (load-order ALL CLEAR) so getDb is defined at call time — the roadmap's "utils.js loads at body-end" worry didn't bite. **Gate tightened:** `validate_supabase_singleton.py` L1 ≤1 → **0 inline createClient (must use getDb)**, registered, **teeth-proven** (throwaway page w/ 1 createClient → FAIL RC=1; removed → PASS). **LIVE (Playwright MCP, bridge :5000→local :54321, all 4 patterns, 0 console errors):** inventory (simple — `window.db === window._whSupabaseClient`, the singleton IS the page client), agentic-rag-observability (`window.supabase.createClient` ternary on a founder-gate page), voice-journal (`const db = window.supabase.createClient`), public-feed (multiline). **★ clone-debt side-effect:** 4742→**5532** dup-lines = a jscpd MEASUREMENT ARTIFACT, not new copy-paste — a one-token-per-page swap can't add 790 hand-written lines (clones 60→61); normalizing the init token let jscpd extend/merge detection across the already-near-identical auth/identity boilerplate (the S13 lesson). Re-baselined to 5532 with a documented reason in `clone_debt_baseline.json`; the genuine follow-on dedup = **D8** (shared page-init helper → back below 4742). **Value:** no hardcoded prod creds inline on 38 pages, one client/page (no GoTrueClient race), uniform local-repoint. commit + prod push Ian-gated. |
| 2026-06-14 | **GROUP C — component dedup (extension)** | 📋 DRAFTED — plan-only, NO build (awaiting Ian's go) | Skill-grounded synthesis (Architect/Frontend/AI-Engineer/QA via Memento) folded as **§12** + master-table **S10–S14** + decisions **D5/D6**. Corrections vs the first sketch: (1) `validate_clone_debt.py` is a **RESURRECT** — it existed + was registered 2026-06-07, now absent from the tree — not greenfield; (2) ratchet on **%/lines, not count** (count 73→70 but % 24.65→27.5 after S8 deletions — a count ratchet would lie); (3) the **~530-line `<script>` boilerplate (S13) is the real lever to <15%**, not detail/cards; (4) retired `predictive.html` must leave the jscpd scan first (~17 ghost clones). AI-display fragmentation surfaced as the higher-value-but-separate **D5**. |

---

## 7. Tile Provenance Audit (2026-06-12, Ian: "investigate where each was derived — formula, standard, canonical source, purpose — then we triage")

Anchored on: `kpi_source_registry.json` (4 registry metrics with forbidden anti-patterns), per-page source-chips (`renderSourceChip`), per-page "How these are derived" explainer blocks, and direct code traces.

### T1 — Pending approval

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| Pending approval (asset-hub) | `asset_nodes` (base table) | COUNT `status IN ('pending','rejected')` in hive; verdict red at 5+ | Platform approval workflow (worker submits → supervisor signs off) | Asset-hub owns the approve action; this is the supervisor's queue |
| Pending approval (inventory) | inventory parts (truth view) | Worker-added parts awaiting sign-off; Use/Restock locked until approved | Same approval workflow, different subject (parts) | Inventory owns the part approval action |

### T2 — risk / hot / critical family

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| High-severity alerts (alert-hub, 32) | `v_alert_truth` (Phase-3 one-brain composer) | COUNT feed alerts `severity IN ('critical','high')` | Alert = an EVENT needing ack/resolve (≠ asset risk) | Alert-hub owns the alert workflow |
| Anomaly signals (alert-hub, 0) | `v_anomaly_truth` / `anomaly_signals` | COUNT status='attention'; composite-ranked top-5; **Stair 3+ gated** | Anomaly Engine 2.0 fusion | Needs-review queue for fused sensor anomalies |
| AMC brief + 4 stat tiles (alert-hub) | `amc_briefings` latest row | Daily brief generated by `amc-orchestrator` (5 sub-agents); stats = payload counts (high-risk assets checked / PMs flagged / parts / crew) | Morning-check doctrine | The day's digest, owned by the alert page |
| Critical assets (asset-hub, 6) | `asset_nodes` | COUNT `criticality='critical'` among approved | Asset criticality classification (set at registration; drives PM-coverage expectation) | Registry-completeness watch |
| Top risk this shift (shift-brain) | `v_risk_truth` via `shift-planner-orchestrator` `fetchRiskTop` | DISTINCT latest per asset, `.in('risk_level',['high','critical'])`, order by score | **Canonical bands from `batch-risk-scoring`: critical ≥0.85, high ≥0.70** — registry-enforced (`top_risk_band` forbidden: unbanded top-N "cried wolf", fixed 2026-06-10) | Shift-start action list (register lives elsewhere) |
| Hot/Healthy/Ranking/Heatmap (predictive — RETIRED) | `asset_risk_scores` / `v_risk_truth` | hot = level IN (critical,high); healthy = low; MTBF @365d annual decay | Same bands | Page retired Phase 4; jobs live in asset-hub 360 + analytics |

### T3a — due-soon family

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| Tasks today / this week (dayplanner, 0/6) | `schedule_items` `.eq('worker_name', ME)` | Client-side date bucket vs today/this week | **Worker-scoped** personal planner | "My day" ≠ hive workload |
| Due this week (pm-scheduler, 25) | `v_pm_scope_items_truth` | COUNT `is_due_soon` — **next 14 days** (sub-caption says so; label says "this week") | Frequency-aware: `next_due = COALESCE(last_completion, anchor, created_at) + frequency_days` (seeder-vocab map fixed 2026-06-10) | Hive PM workload preview |
| PMs due (shift-brain) | ⚠️ `v_pm_compliance_truth` `.eq('is_due', true)` | **`is_due` = the RETIRED flat-30-day proxy** (days_since_last_completion > 30) | ⚠️ NOT frequency-aware — the exact signal `kpi_source_registry.json` forbids for overdue tiles (F4-class) | Shift-start PM list — **see Finding P1** |

### T3b — late/overdue family

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| Overdue tasks (dayplanner, 3) | `schedule_items` worker-scoped | date < today AND not done (client-side) | Personal scope | My missed items |
| Overdue PMs (pm-scheduler, 5) | `v_pm_scope_items_truth` `is_overdue` | Frequency-aware; registry `pm_overdue` = distinct pm_asset_id roll-up; flat-30 reads FORBIDDEN | SMRP-aligned freshness discipline | PM backlog owner page |
| Past end date (project-manager) | `projects` (+ `v_project_truth` alias `end_date:target_end_date`) | `end_date < today AND status NOT IN ('complete','cancelled','archived')`; red at 3+ | Schedule-slip flag | Stalled-project triage |

### T3c — healthy/on-track family

| Tile (page) | Source | How it's computed | Basis | Why it's there |
|---|---|---|---|---|
| On track (pm-scheduler, 0) | `v_pm_scope_items_truth` | "Everything else": NOT overdue AND NOT due-soon (incl. no-history items) | Snapshot count — page explicitly distinguishes it from Compliance % | Quick health read |
| (Compliance % sub-stat, same card) | `get_pm_compliance_smrp` RPC | **SMRP Metric 2.1.1**: on-schedule completions / due in window, frequency-aware, 90d | SMRP; Stair-2 gate = >80% for 2 consecutive weeks; same value as Analytics | The maturity-gate metric |
| Healthy assets (predictive — retired) | `asset_risk_scores` | `risk_level='low'` | Risk bands | (retired) |
| On target workers (skillmatrix) | `skill_badges` | Disciplines where actual level (highest consecutive badge from L1) ≥ target level | **WorkHive Skill Tier Model (platform-internal)**, 5 levels × 5 disciplines | Skill-gap watch — **see Finding P3** |

### Hub + flagship standards tiles (context)

| Tile (page) | Source | How it's computed | Basis |
|---|---|---|---|
| Maturity stair (hive, Stair 1) | readiness snapshot (`get_hive_dashboard` / readiness truth) | Composite /100 → Stair 1–5; ≥2 PROACTIVE, ≥3 PREDICTIVE-READY | **WorkHive Stair Model** — 5-dimension composite (Reliability/Operations/Safety/People/Cost) per `KPI_ENGINE.md`; gates features (Anomaly Stair-3+, PM-compliance Stair-2) |
| Adoption health (hive, Healthy) | `v_adoption_truth` via `get_adoption_risk_current` (auto-refresh >24h via `compute_adoption_risk`) | Tier healthy/at_risk/critical + risk score /100 + champion candidate | Usage-risk early warning |
| Open issues (hive, 19) | composite: `v_logbook_truth` open WO + registry PM-overdue + `v_inventory_items_truth` low stock | `totalIssues = openWO + overdue + lowStock`; red if overdue>5 OR openWO≥10 | **Canonical Anchor L10** contract — card must consume all 3 fuels its chip declares (closed a 3-declared/1-consumed bug) |
| OEE (avg, partial) (analytics, 86%) | descriptive phase / snapshots | A × Q only | **ISO 22400-2:2014 §5.5** — honest-partial label until ideal cycle time captured |
| Worst MTBF (partial) (analytics, 6.1d) | snapshots | Calendar-time MTBF, user window 90/180/365 | **ISO 14224:2016 §9.3** — partial (not operating-time); predictive page used fixed 365d (chips declare the window difference) |
| PM compliance (analytics, 89%) | `get_pm_compliance_smrp` | SMRP 2.1.1 canonical RPC | **SMRP** — one derivation everywhere |
| Out of stock / Low stock (inventory, 1/3) | `v_inventory_items_truth` | `qty_on_hand <= 0` / server flag `is_low_stock` (0 < qty ≤ min_qty reorder threshold) | Registry `low_stock` metric |

### ★ Findings surfaced BY this audit (new triage rows)

| # | Finding | Class | Proposed action |
|---|---|---|---|
| **P1** | **shift-brain "PMs due" derives from the retired flat-30-day proxy** (`v_pm_compliance_truth.is_due`) while pm-scheduler/home use frequency-aware `is_due_soon` — a weekly PM done 10d ago shows NOT due; an annual PM done 35d ago shows DUE. Fn docstring even claims `pm_assets + pm_scope_items` (comment/code drift). Registry gap: only `pm_overdue` is registered; there is no `pm_due_soon` metric row to catch this. | Same-job-different-derivation (the F4 class the registry exists to kill) | Repoint `fetchPMsDue` → `v_pm_scope_items_truth` `is_due_soon`/`next_due_date`; add `pm_due_soon` metric to the registry with the same forbidden pattern; fix docstring |
| **P2** | pm-scheduler tile says **"Due this week"** but the window is **14 days** (sub-caption admits "Next 14 days") | Label/window mismatch (caption-lies class, like the 2026-06-10 source-chip fix) | Relabel "Due soon (14d)" or change window to 7d — Ian's call |
| **P3** | skillmatrix explainer says **"max 5 × 6 = 30"** badges while the model is 5 levels × 5 disciplines = 25 (the SM-1 hardcode fix corrected the TILE, the explainer copy lagged) | Stale explainer copy | Fix copy to 25 |
| **P4** | asset-hub header tiles read base `asset_nodes` while the page chip declares `v_asset_truth` — legitimate (tiles need pending/rejected rows the approved-only view excludes) but undeclared | Write-base/read-view split, undocumented | Add a chip note or `canonical-allow` comment — cosmetic |

---

## 8. Analytics Engine — full 4-phase × 29-block provenance + live verification (2026-06-12)

_Ian: "you always skip the analytics engine phases — it's the source of everyone's analysis. Thorough check of each tile."_ Done: every block of every phase traced to its python formula + standard, AND live-walked (each phase tab clicked, every block confirmed rendering real data; snapshot regenerated 17:29–17:35 PHT today, compute-on-first-view holding).

Pipeline: `analytics.html` → `analytics-orchestrator` edge fn → python-api (`python-api/analytics/{descriptive,diagnostic,predictive,prescriptive}.py`, pandas/scipy) → `analytics_snapshots` (compute-on-first-view, Phase-1 open-fast). Every python function carries a `formula:` contract tag + `standard` field in its return payload (standards-validator discipline).

### Phase 1 — Descriptive ("what happened") · 9 blocks · ALL LIVE ✅

| Block | Formula / derivation | Standard | Live (90d) |
|---|---|---|---|
| OEE | partial **A × Q** (no ideal cycle time yet → no Performance term), avg across assets | ISO 22400-2:2014 §5.5, honest-partial label | 86% · 30 assets · "—" where Q missing |
| Availability | MTBF / (MTBF + MTTR) × 100 | ISO 14224:2016 §9.2 | 96.7%, lowest GEN-001 |
| MTBF | corrective/Breakdown entries ONLY, calendar-time between failures | ISO 14224:2016 §9.3 (partial: calendar not operating time) | worst 6.1d (PB-001) |
| MTTR | mean repair duration | ISO 14224:2016 §9.4 | slowest 5.8h (FL-002) |
| PM Compliance | on-schedule completions / due in window, frequency-aware | SMRP Metric 2.1.1 (same RPC family as pm-scheduler/Analytics header) | 88.8%, 8 assets < 85% target |
| Downtime Pareto | cumulative downtime ranking | 80/20 rule | 1211.3h total |
| Failure Frequency | failures per asset per period | ISO 14224:2016 | 278 total, CH-001=14 → ✗ Critical |
| Repeat Failure Count | identical root_cause pairs per machine | ISO 14224:2016 | 65 repeat pairs |
| Parts Consumption | usage rate /wk /mo from inv_transactions | SMRP | live rates |

### Phase 2 — Diagnostic ("why") · 7 blocks · ALL LIVE ✅

| Block | Formula / derivation | Standard | Live |
|---|---|---|---|
| Failure Mode Distribution | failure taxonomy bucket counts | ISO 14224:2016 | Wear 20.9% top of 278 |
| Repeat Failure Clustering | same root-cause across machines = systemic | ISO 14224:2016 | 12 systemic issues |
| PM-Failure Correlation | Spearman rank (SciPy) | statistics discipline | r=0.203 p=0.282 → honestly "not significant" |
| Skill-MTTR Correlation | Spearman by discipline | statistics | Electrical r=−0.866, ns |
| Parts Availability Impact | logbook × inventory cross-ref (MTTR above/below stockout windows) | cross-ref | 4.4h avg / 4.5h median |
| RCM Consequence Classification | consequence buckets | SAE JA1011 §5.4 | 100% coverage; Stopped-production 27.3% |
| Engineering Validation | engineering_calcs × logbook (was equipment sized right?) — WAT pattern | WAT | honest empty ("no matches") |

### Phase 3 — Predictive ("what will happen") · 7 blocks · ALL LIVE ✅ (2 findings)

| Block | Formula / derivation | Standard | Live |
|---|---|---|---|
| Failure Trend | linear trend, 14 weeks (Prophet path needs ≥24 pts) | — | Stable |
| Next Failure Prediction | last failure + MTBF | ISO 13381-1:2015 | 12 machines past predicted date |
| Equipment Health Score | 4-component weighted composite (30% PM-overdue ⚠ + 30% fault-freq + …) SMRP-inspired | SMRP-inspired | 16.8/100 lowest AHU-002 — **component skewed by P5** |
| Anomaly Baseline | SPC control limits | ISO 7870-2 | 1 alert: AHU-002 vibration 2.1σ |
| PM Due Calendar | last completion + `FREQ_DAYS` ⚠ **stale local map** | "Deterministic" | **1 overdue · 5 due-soon — DISAGREES with canonical 5 · 25 (see P5)** |
| Parts Stockout Risk | qty_on_hand / daily consumption rate | SMRP inventory | 6 parts at risk |
| Consumption Spike | rule-based threshold | Stage-2 rule | 6 parts flagged |

### Phase 4 — Prescriptive ("what to do") · 6 blocks · ALL LIVE ✅

| Block | Formula / derivation | Standard | Live |
|---|---|---|---|
| AI Action Plan | Groq synthesis OVER the deterministic outputs (WAT: math deterministic, AI narrates) | ISO 55000:2014 | narrative names AC-003 critical, 1.2d |
| Priority Maintenance Ranking | criticality × failures × downtime score | ISO 55001 risk framework | 3 P1 · 19 P2 |
| Technician Assignment | skill match per open job | SMRP workforce | 10 open jobs assigned |
| Parts Reorder | inventory cross-ref, PM-linked urgency | inventory mgmt | 1 critical |
| PM Interval Optimization | MTBF vs current interval | SAE JA1011 §7 | VFD-001 → increase frequency |
| Training Gap | MTTR × skill, +20% spike rule | SMRP workforce | honest empty (no spike) |

### ★ Analytics findings (added to the triage queue)

| # | Finding | Evidence | Proposed action |
|---|---|---|---|
| **P5** | **`predictive.py` carries the stale 4-key `FREQ_DAYS` map TWICE** (lines 47 + 405: `{Monthly:30, Quarterly:90, Semi-Annual:180, Yearly:365}`) — the 2026-06-10 seeder-vocab fix reached the canonical view + `prescriptive.py` (full lowercase map: weekly=7, semi-annual=180, annual=365) but **missed predictive.py**. Data vocabulary {Weekly, Semi-annual, Annual} all fall to the `.get(…, 30)` default. Skews: PM Due Calendar (live shows **1 overdue · 5 due-soon vs canonical 5 · 25**) + Equipment Health Score's 30% PM-overdue component. | Live mismatch on screen + code diff vs prescriptive.py | Replace both maps with prescriptive.py's canonical lowercase map + case-insensitive lookup; re-walk phase 3 |
| **P6** | PM Due Calendar **recomputes** next-due from raw scope items instead of reading `v_pm_scope_items_truth` baked `next_due_date`/`is_overdue`/`is_due_soon` — read-don't-recompute doctrine (`ROADMAP_pm_analytics_canonical` §6). Even with P5 fixed it can drift again. | code trace | Prefer: feed the python calendar from the truth view's baked signals (or assert parity in a validator) |
| **P7** | **GATE-GAP:** `validate_frequency_map_consistency.py` PASSES today (just ran it) despite P5 — it flags **contradictory values** on keys a map HAS, but is blind to **missing vocabulary absorbed by a default**. Exactly the strong-on-structure / weak-on-semantics class. | validator run exit 0 + report empty | Extend validator: every code FREQ map must COVER the live distinct frequency vocabulary (case-insensitive) or use a case-insensitive canonical import |

---

## 9. Per-page provenance audits (same depth as §8 — one page at a time, 2026-06-12)

_Ian: "do the same depth on every other page, one at a time, so nothing is silently dropped." Method per page: live-dump census (today's signed-in walk) → code trace of every tile's loader (source view/RPC, formula, threshold, standard) → live verification → findings. Pages already covered: analytics = §8; the cross-page cluster tiles = §7 (their per-page rows are repeated here for completeness)._

### 9.1 achievements.html — 7 units · ALL LIVE ✅ · 1 finding

Worker-scoped gamification. Sources: `v_worker_achievements_truth` (current_level per domain), `achievement_xp_log` (XP events), `v_worker_truth` (identity). Model = **WorkHive Achievement Tier Model (platform-internal)**: 12 domains in 3 pillars + 1 legendary (`iron_worker`, needs Level 50 in 5 domains); XP curve `xpForLevel(n) = floor(100 × n^1.8)`, level cap 100; 5 named tiers ride over levels.

| Tile | Source | Derivation | Live | Purpose |
|---|---|---|---|---|
| XP this week | `achievement_xp_log` | sum `xp_earned` where `earned_at` ≥ now−7d; XP flows from logbook + PM + AI feedback actions | +460 (GREAT WEEK ≥100) | motivation pulse |
| Active domains | `v_worker_achievements_truth` | count domains with `current_level ≥ 1`, of 12 | 3/12 (NARROW <4) | breadth nudge |
| Total level | same | **sum of `current_level` across 12 domains** | 62 | drives worker tier |
| Composite/active/top-domain stats + detail panel | same payload | same derivations re-rendered in hero strip | — | drill-down |

Verdict rule (documented in-page): never red — "Achievements is purely motivational."

**★ P8 — "max 60" caption is wrong:** the Total-level sub says "Sum of levels across all 12 domains (max 60)" — a relic of an old 5-level model. Actual model: levels to 100 (legendary needs L50×5). **Live value 62 already exceeds the claimed max with only 3 domains active.** Same caption-lies class as P2/P3. Fix copy (true max = 1,200). Distinct-subject note vs skillmatrix: achievements = XP-from-actions (worker-scoped), skillmatrix = quiz badges vs target — same "progress" feel, different subjects; no consolidation.

### 9.2 ai-quality.html — 0 tiles live (BY DESIGN: honest maturity gate) ✅ · 0 findings

Live state explained: page is **Stair-2 gated** (readiness truth) — Baguio is Stair 1, so it renders the Honest Empty State ("We won't fake this… AI quality and ROI numbers below Stair 2 are noise") instead of tiles. That's the deliberate honest-gate pattern, not a bug; the 0-unit inventory dump is correct.

Behind the gate (code-traced; renders at Stair 2+):

| Tile | Source | Derivation | Basis |
|---|---|---|---|
| Worker trust | `ai_reply_feedback` | round(100 × 👍/(👍+👎)); NO DATA if unrated | worker thumbs = the trust signal |
| Cost this month | `ai_cost_log` | month sum; soft bands ₱<500 modest / 500–2000 / >2000 | budget watch |
| Time saved (est.) | `ai_reply_feedback` | 👍 × 5 min (declared heuristic `MIN_SAVED_PER_THUMBS_UP=5`) | honest ROI estimate, labeled "est." |
| AI calls / Spend / Fallback rate / Schema compliance (4 sum-cards) | `ai_cost_log` 30d rolling | fallback red >20% of calls; schema green ≥90% | pipeline health |
| Per-function cost table | `ai_cost_log` | calls/tokens/cost/latency/failure per edge fn, sorted by cost | cost attribution |

Chip declares: `ai_cost_log` · live · 30-day window · "Service-role inserts only; reads hive-scoped via RLS." Purpose: the supervisor's AI-ROI dashboard; also the planned Phase-8.6 eval-dashboard surface.

### 9.3 alert-hub.html — 8 units · ALL LIVE ✅ (AMC empty = graceful no-brief-today) · 0 new findings

The Phase-3 "one alert brain" page. The feed is a 3-source composite, all hive-scoped:

| Tile / section | Source | Derivation | Live | Purpose |
|---|---|---|---|---|
| High-severity alerts | composed feed | COUNT feed alerts `severity IN (critical, high)`; feed = risk alerts (`v_risk_truth`) + signature alerts (`v_alert_truth`, `alert_kind='signature'`, view keeps active+acknowledged ONLY → resolved don't resurrect; severities normalized warning→high, info→low) + `parts_staging_recommendations` (pending) | 32 | triage queue of EVENTS (≠ asset risk) |
| Anomaly signals | `anomaly_signals` / `v_anomaly_truth` | COUNT status='attention'; panel = top-5 by composite; **Stair 3+ gated**; realtime-subscribed | 0 (Stair 1 hive) | fused-sensor review queue |
| AMC daily brief + 4 stat tiles | `amc_briefings` latest row | brief generated by `amc-orchestrator` (5 sub-agents); stats = `asset_count` (high risk) / `pm_count` (PMs due) / parts / crew from brief payload; realtime-subscribed | "None today" + 0s — graceful (no brief generated today locally) | the morning-check digest |
| Verdict roll-up | all three | tone from critical count + anomaly count + AMC status (sub declares "v_risk_truth + anomaly_signals + AMC briefing") | renders | one-line page answer |
| Alert detail breakdown | feed row | per-alert factors (Phase-5a structured `{factor, weight, contribution}` shape-aware reader, same as predictive's) | on tap | drill-down |

No new findings: the resolved-alerts-resurrect bug was already fixed by the Phase-3 composer repoint; AMC zeros are a data-state (no scheduled brief locally), with honest empty copy.

### 9.4 analytics-report.html — 0 tiles (correct: print-ready report builder) · LIVE-GENERATED ✅ · 1 inherited finding

Not a dashboard — a **document generator** over the §8 pipeline (header comment declares: "Same canonical sources as analytics.html (analytics-orchestrator → v_logbook_truth + RPCs)"; `v_hives_truth` for the letterhead). Affordances: period 30/90/180/365d · audience Supervisor/Worker · Generate → `analytics-orchestrator` · Save as PDF · editable letterhead fields.

**Live-generated a real report today (90d, Supervisor):** 4 sections + appendix render with live data — 1 Executive Summary (headline CT-002) · 2 Findings (worst offenders, root causes, RCM SAE JA1011 consequences, parts, PM-vs-failures) · 3 Predictive Outlook (watch-first, Asset Health Scores 0–100) · 4 Action Plan (P1 this-week, PM interval adjustments) · Appendix (all priorities, intervals, workload-balanced technician assignments).

**Inherited finding:** §3.2 Asset Health Scores come from `predictive.py` → carries the **P5** stale-frequency skew until P5 is fixed. No page-local findings.

### 9.5 asset-hub.html — 12 units · 360 LIVE-TAPPED ✅ (AC-001) · 1 real finding

The asset registry + per-asset 360. Header tiles already in §7 (Total/Critical/Pending from `asset_nodes`; P4 chip note). Page chip declares the join contract: `v_asset_truth + v_risk_truth + v_logbook_truth + v_fmea_truth + v_weibull_truth`.

| 360 section | Source | Derivation | Live (AC-001) |
|---|---|---|---|
| Logbook entries | `v_logbook_truth` `.eq('asset_node_id', node.id)` (Phase-5b uuid keying, legacy text bridge dropped) | count + timeline merge, latest 20 | 12 ✅ |
| PM completed | `pm_completions` `.eq('asset_id', node.pm_asset_id)` — only if the node is linked | count + timeline merge | 0 — **see P9** |
| Last failure | logbook breakdown entries | most recent failure date | 11d ago ✅ |
| Edges / Neighbors | RCM edges | graph neighbors + "+ Add edge" | 0 (none seeded) |
| Risk Profile | `v_risk_truth` | rules-v1 score + factors; chip: "Daily snapshot 13:00 PHT · MTBF over 365-day window" | renders ✅ |
| Recommended Parts to Stage | `parts_staging_recommendations` | pending recs for this asset | renders |
| Live Telemetry | MQTT/OPC-UA ingest | sensor readings when connected | empty-state (no telemetry locally) |
| Weibull / P-F / FMEA / RCM strategy | `weibull-fitter`, `pf-calculator` edge fns (pure math, not LLM) + fmea/rcm truths | deterministic reliability math (WAT) | affordances present |
| Ask Asset Brain | `asset-brain-query` edge fn (Tier-3 conversational AI) | per-asset Q&A grounded in verified-state | = Track **A2** fold candidate |

**★ P9 — asset→PM bridge unlinked platform-wide:** `asset_nodes.pm_asset_id` is NULL for **all 30 nodes** in the hive (live count). The PM vertical itself is healthy (519 completions key on `pm_assets` directly — analytics 88.8% fine), but the 360's "PM completed" tile + PM timeline are **silently dark for every asset**. Root: seeder doesn't link `asset_nodes.pm_asset_id` (post-reseed). Graceful degrade hides it — exactly the "tile quietly dead" class. Action: seed the link (match on tag) + consider an honest "not linked to PM program" caption when `pm_asset_id` is null instead of a bare 0.

### 9.6 assistant.html — 0 tiles (chat surface) · LIVE-PROVEN ✅ · 1 major finding + 1 roadmap correction

**Roadmap correction: Track A1 is ALREADY SHIPPED** (2026-06-07, in-page comment "Phase 1+2: route through ai-gateway (the ONE front door)"). Live-proven today: question → `ai-gateway` (agent `assistant`, 4.8s) + `semantic-search` (3.6s); the Cloudflare worker (`workhive-assistant.workers.dev`) did NOT fire — it is now the deliberate fail-open fallback (25s ceiling), not the primary brain. Envelope-unwrap fixed. Remaining A1 work = residual verification only (cross-surface memory proof), not a build.

Provenance of what the page shows:

| Element | Source | Derivation |
|---|---|---|
| Chat answer | `ai-gateway` → `ai-orchestrator` (7-agent fan-out) | unified memory/persona/rate-limit via gateway; JWT-resolved caller |
| Fallback answer | Cloudflare worker (groq llama-3.x) | personal-context system prompt built from worker-scoped truth views: 10 logbook + schedule window + 6 badges + 20 inventory + 8 PM assets + 5 journal entries |
| Journal tab | `voice_journal_entries` | worker-scoped, latest 5 |
| Retrieval | `semantic-search` | embeddings over journal/knowledge |
| Per-message label | `ai_label_per_message` transparency contract | declares model source on every reply |

**★ P10 — the BRAIN answers PM-overdue from the retired flat-30 proxy:** asked live "How many PMs are overdue?", assistant said **"1 overdue (ABB ACS580-01, 16 days since last PM)"** — canonical frequency-aware truth says **5**. Root: `ai-orchestrator` PM agent reads `v_pm_compliance_truth` and its prompt hard-codes "overdue = no completion in over 30 days" (index.ts:62–75); the LLM even listed a 16-day item as overdue. This is the **third member of the P1/P5 family** — the F4 drift class survives in consumers `kpi_source_registry.json` doesn't govern (edge fns + python). Family fix: repoint shift-brain `fetchPMsDue` (P1), `predictive.py` (P5), and ai-orchestrator PM agent (P10) to `v_pm_scope_items_truth.is_overdue/is_due_soon`; add them as registered consumers; extend forbidden-pattern scan beyond HTML to edge fns + python-api.

### 9.7 audit-log.html — 0 tiles (feed page, correct) · LIVE ✅ · 0 findings

Single-source compliance feed: `hive_audit_log` (`actor, action, target_type/id/name, meta, created_at`), hive-scoped, supervisor-only, latest 500 within the selected range (24h/7d/30d/90d/all), realtime-subscribed (`supabase_realtime` on the table), paged 30 at a time, CSV export of the filtered view. Chip declares exactly this. Purpose: the enterprise-compliance audit trail (ISO 27001/SOC-2 ingredient). Renders graceful empty state when the window has no events (verified in the 06-10 deepwalk and again today: page-open clean). No derivations to drift — it displays rows verbatim.

### 9.8 community.html — 0 tiles (forum, correct) · LIVE ✅ · 0 findings

Social surface, no derived KPIs. Sources: `v_community_posts_truth` (hive Feed + 🌐 Global tab + Mod Queue), `community_replies` (threads), `community_reactions` (👍/🔧/🔥/👀 toggles), `community_xp` (`xp_total` — feeds the achievements XP economy). Category filters General/Safety/Technical/Announcements; pin/unpin moderation. Live: 49 seeded posts rendered with working reaction affordances at page-open. Displays rows verbatim — no formulas to drift.

### 9.9 dayplanner.html — 4 units · ALL LIVE ✅ (0/6/3) · 0 new findings

**Worker-scoped** personal planner (every query `.eq('worker_name', ME)`). In-page explainer documents all derivations:

| Tile | Source | Derivation | Live |
|---|---|---|---|
| Tasks today | `schedule_items` | `date = today` (**PHT**) | 0 |
| Tasks this week | same | current **Monday–Sunday** window | 6 |
| Overdue tasks | same | `date < today AND item_status NOT IN (done, closed, cancelled)` — open work that slipped | 3 |
| Verdict | derived | red if 3+ overdue; amber if today > 6 OR any overdue | renders |

Also on page: DILO/WILO/MILO/YILO calendar drilldowns (same rows, time-bucketed), open logbook items (`v_logbook_truth` worker-scoped, `status NOT IN (Closed, Resolved)`), full CRUD on `schedule_items` (auth-uid stamped). The §7 T3 scope-chip verdict applies here: these pills are "yours", pm-scheduler's are "hive" — the label should say so.

### 9.10 engineering-design.html — 0 tiles (calculator tool, correct) · catalog LIVE ✅ · 0 findings

The WAT calc surface: **56 calc types across 6 disciplines** (HVAC 11 · Mechanical 4 · Electrical 14 · Plumbing 10 · Fire 5 · Machine Design 12), tabs Calculator/History/Guide. Provenance discipline here is the platform's strongest:

- Every calc declares its **standards array in-page** (PSME Code, ASHRAE Fundamentals 2021, NBC PD 1096, ASHRAE 62.1, DOLE OSH, PDI BH-201/ASPE…) with per-input tips and rounding rules.
- Math runs in `engineering-calc-agent` (deterministic; AI only narrates) with Tier-E **formula contracts** (`canonical/formula_contracts.json` citing `standard_id + standard_clause`), enforced by `audit_standards_alignment.py` (citation-valid / clause-valid / input-coverage / partial-honesty / unit-match) + the engineering-calc-validator suite — the live-proof mechanism for the formulas themselves.
- BOM/SOW: `engineering-bom-sow` generates procurement list + contractor scope FROM a calc result (structured doc, Tier-3b tool — stays a tool under Track A, gets persona pass in A4).

Live: discipline catalog renders with counts; calc/run pipeline is gate-covered (not re-run here — validator suites own that proof).

### 9.11 hive.html — 4 units · ALL LIVE ✅ (composite verifies: 19 = 10+5+4) · 1 minor finding

The Live Board hub. §7 covered the 3 header cards; full spine:

| Element | Source | Derivation | Live |
|---|---|---|---|
| Maturity stair | `get_hive_readiness_current` (+`compute_hive_readiness` on stale — compute-on-first-view) · realtime on `hive_readiness` | WorkHive Stair Model 5-dim composite /100 → Stair 1–5 | Stair 1 |
| Adoption health | `get_adoption_risk_current` (+`compute_adoption_risk` >24h) · realtime | tier + risk /100 + champion | Healthy |
| Open issues | composite | openWO (`get_hive_board_dashboard`) + PM-overdue (registry-governed `is_overdue`) + stock problems (client count over `v_inventory_items_truth`) | **19 = 10 WO + 5 PM + 4 stock ✓ canonical-consistent** |
| Board / presence | `get_hive_board_dashboard` RPC + realtime presence channel | live member chips + activity | renders |
| Personal pills | `v_logbook_truth` worker-scoped counts | my open/closed | renders |
| Knowledge freshness | `v_knowledge_freshness_truth` | stale-SOP signal | renders |
| Members | `v_worker_truth` (wraps hive_members) | role-validated | renders |

Canonical Anchor L10 holds: the open-issues card consumes all 3 fuels its chip declares.

**★ P11 (minor) — open-issues stock leg recomputes client-side:** counts `q<=0 OR (min>0 AND q<=min)` over the truth view instead of reading the registry's `is_low_stock` flag, and the caption says "4 low stock" while 1 of the 4 is OUT-of-stock. Count is defensible (it's a "stock problems" roll-up) but the derivation is unregistered and the label imprecise. Action: read server flags (`is_low_stock` + out-of-stock) and caption "stock issues", register hive as a `low_stock` consumer.

### 9.12 index.html — marketing + signed-in "operational heartbeat" · ALL LIVE ✅ · 2 findings

Signed-out: marketing landing (no AI bubble by design, copy only). Signed-in adds the heartbeat strip (chip declares `v_logbook_truth + v_risk_truth + v_inventory_items_truth` + PM scope):

| Card | Source | Derivation | Live |
|---|---|---|---|
| My Open Jobs | `v_logbook_truth` worker-scoped | my open entries, newest first | AC-003 1d, TX-001 15d… |
| Hive Activity Today | board counts | jobs closed · PM done · active alerts (today) | 10 · 15 · 2 |
| Top At-Risk Assets | `v_risk_truth` | banded (critical/high), "All assets →" deep-link to asset-hub (§7 T5 path — earns its place) | AC-003 critical 90%, MTBF 12d |
| Low Stock (4) | `v_inventory_items_truth.is_low_stock` (registry-compliant) | server flag list | **4 — see P12** |
| PM overdue signal | `v_pm_scope_items_truth` `.eq('is_overdue', true)` (F4-fix holds — freq-aware, deduped) | feeds heartbeat alerts | wired ✓ |

**★ P12 — "Low stock" means two different things live:** `is_low_stock` flag = `qty ≤ min_qty` INCLUDING zero (live: 4 rows, one is the out-of-stock PSV spare @0). index shows "Low Stock (4)"; inventory.html buckets disjointly (Out 1 · Low 3). **Same label, 4 vs 3, two pages** — user-facing F4 class. CORRECTED root (from §9.14 trace): the view ALREADY exposes `is_out_of_stock` — inventory buckets out-first; **index just doesn't exclude `is_out_of_stock` rows from its "Low Stock" list**. Consumer-side fix on index (list both buckets: "1 out · 3 low"); no view change. (Hive's P11 leg folds into the same treatment.)

**★ P13 — battery blind spot (explains "0 units" on index):** the `oh-*` heartbeat cards are neither `data-rag-tile`-tagged nor `.simple-card` → `__UFAI.inventory()` missed a real KPI surface, so the §7 T2 risk cluster **undercounts** (index's Top At-Risk card belongs in it; same job as asset-hub Critical/shift-brain Top-risk). Action: rag-tag the `oh-*` cards (`tag_all_rag_tiles.py`) + extend the battery's untagged-KPI selector; re-run the survey.

### 9.13 integrations.html — 6 units · LIVE ✅ (0/0/0 = honest empty, no connectors configured) · 0 findings

CMMS bridge (SAP PM / Maximo / generic CSV). Tiles = connector health buckets over `integration_configs`:

| Tile | Derivation |
|---|---|
| Active | `enabled AND last_sync_at within stale cutoff` |
| Stale | `enabled AND (never synced OR last_sync_at beyond cutoff)` |
| Disabled | `enabled = false` |

Import pipeline provenance: vendor field maps declared in-code (SAP `AUFNR/EQUNR/ISTAT/ARBEI…`, Maximo `WONUM/ASSETNUM/ACTLABHRS…`, generic CSV) → mapping UI → upserts: `external_sync` (idempotent on `system_type,external_id,entity_type`) + `logbook` / `fault_knowledge` / `asset_nodes` (on `hive_id,tag`) / `pm_assets`+`pm_scope_items`; `v_external_sync_truth` provides dedupe truth; last-5-imports log with **24h Undo**. Purpose: legacy-system on-ramp; cross-links to plant-connections (§7 T5 — kept).

### 9.14 inventory.html — 4 units · ALL LIVE ✅ (1/3/0) · contributes the P12 correction

Parts ledger with approval workflow. The reference implementation for stock semantics (registry `low_stock` consumer):

| Tile | Source | Derivation | Live |
|---|---|---|---|
| Out of stock | `v_inventory_items_truth.is_out_of_stock` (`qty ≤ 0`), bucket precedence FIRST | red verdict if any critical part out | 1 (PSV spare) |
| Low stock | `is_low_stock` (`min_qty > 0 AND qty ≤ min_qty`) AFTER out-bucket — so disjoint | reorder nudge | 3 |
| Pending approval | worker-added parts awaiting supervisor sign-off; Use/Restock locked until approved | §7 T1 RELABEL pair | 0 |
| Verdict + coach line | derived | red any-out-critical / amber low-or-pending; action copy names the filter chip to tap | renders |

Mutations: Use/Restock write the ledger (`inv_transactions` — feeds analytics parts blocks §8); client strips read-only view flags before writes (line 677 — clean write-base/read-view split). Purpose: stock truth + the approval gate; "the AI for parts lives here" (per AI map).

### 9.15 logbook.html — 0 KPI tiles (entry surface, correct) · deep-debugged live · 1 real finding (+1 env artifact)

The data spine's WRITE surface: 3-step Log-a-Repair form, asset registration, CSV export, Mine/Team feeds, deep search. No derived KPI tiles — analytics derives FROM it. Provenance: reads/writes base `logbook` (write-surface exception; worker-guard `.eq('worker_name')` on updates), `hive_audit_log` insert on mutations (audit trail), `project_links`/`projects` (entry→project linking), membership gate re-validated per load against `hive_members` (DB-checked, kicked→state cleared, role re-synced — solid). Tier-3 AI tools: Speak-to-Fill (`voice-logbook-entry`), Photo Defect (`visual-defect-capture`), Tag OCR (`equipment-label-ocr`) — Track A4 persona candidates, stay tools.

**Live debug story (the "0 entries / Internal error." mystery):** page showed "No entries yet." for a worker with 500 entries. Traced live: auth fine, membership row fine, the exact 23-column mine-mode query (incl. the `.or(hive_id.eq.X,hive_id.is.null)` solo-merge) returns 200 rows manually. Thrower = **`getPendingEntries()` — the IndexedDB offline queue rejects with bare "Internal error."** in this Chrome profile (env artifact: profile's IndexedDB corrupted by force-killing the stale MCP Chrome earlier; not a product/data bug — 06-10 deepwalk had the feed working).

**★ P14 — offline-queue failure blanks the whole feed:** `loadEntries()` awaits `getPendingEntries()` with NO try/catch AFTER the cloud fetch succeeded — a queue read failure discards 200 fetched rows and renders "No entries yet." with only a bare `console.error`. Offline-first hardening rule violated: queue-read failure must degrade to cloud-only + visible toast, never blank. Same pattern risk wherever `getPendingEntries`/IndexedDB is awaited un-guarded (audit offline-queue.js consumers). Mobile relevance: iOS Safari private mode + storage eviction make IndexedDB failures a real field condition, not just a test artifact.

### 9.16 marketplace.html — 5 units · LIVE ✅ (12 / 2 / "Parts") · 2 pre-queued candidates surfaced

Industrial surplus exchange. Sources: `v_marketplace_listings_truth` (listings + grid), `marketplace_inquiries` (contact-seller), `marketplace_saved_searches`, `marketplace_watchlist`, `hive_audit_log` on mutations. **`PAYMENTS_ENABLED = false`** — Stripe checkout/escrow dormant by design (the "stuck loader" from the 06-10 walk was this, not a bug).

| Tile | Derivation | Live |
|---|---|---|
| Listings in view | count of current filtered grid | 12 |
| My listings | `.eq(seller = me)` | 2 |
| Current tab | **UI state shown as a KPI tile** ("Parts") | — |

Note for triage: the 06-08 sweep already queued (never dispositioned) exactly these two: **"Eliminate marketplace UI state tile"** (current_tab is navigation state, not information — Tesler violation) and **"Deduplicate marketplace listings view"** (listings_in_view vs listing_grid render the same rows twice at different granularity). Both fold into Track T disposition — recommend ACCEPT eliminate current_tab tile, REVIEW the grid/count pairing.

### 9.17 ph-intelligence.html — 0 tiles (BY DESIGN: Stair-3 honest gate) ✅ · 0 findings

Gated by `maturity-gate.js` at **Stair 3** with a dual condition documented in-code: "peer benchmarks need N≥5 hives in segment AND 30+ days of your own data" (anti-noise + k-anonymity). Baguio = Stair 1 → honest gate renders; 0-unit dump correct. Behind the gate: monthly anonymized PH-wide benchmarking report (`intelligence-report` edge fn) + a public API surface (`intelligence-api?endpoint=benchmarks|failure-modes|report`) + SAP/Maximo compare-upload funnel. Purpose: the network-effect data product; cross-links to integrations (§7 T5 — kept).

### 9.18 plant-connections.html — 4 status cards · ALL LIVE ✅ (honest empties) · 0 findings

The OT/IoT connection console. Each card is a connection-state read, not a derived KPI:

| Card | Source | Live |
|---|---|---|
| Broker status | `integration_configs` (+ `v_external_sync_truth` last-sync) | "Not connected" |
| Sensor topics | `sensor_topic_map` | "0 sensors" |
| Gateway traffic | `gateway_audit_log` | "No traffic" |
| Retention | `hive_retention_config` | "Defaults only" |

Plus `sso_configs` (enterprise SSO setup). All honest empty states with setup CTAs — nothing connected in the local env, correct. Note: these 4 cards are untagged (same P13 battery blind-spot class — rag-tag them in the same pass).

### 9.19 pm-scheduler.html — 4 units · ALL LIVE ✅ (5 / 25 / 0 / 89%) · findings already filed (P1 cross-ref, P2)

The PM backlog owner. §7 covered tile derivations; page-level provenance completes it:

- All three buckets read `v_pm_scope_items_truth` **baked signals** (`is_overdue` / `is_due_soon` / `next_due_date` via `COALESCE(last_completion, anchor, created_at) + frequency_days`) — the in-code comment explicitly records WHY (the deleted client fallback was the "home 21 vs page 0" bug, removed 2026-05-20). The reference implementation other consumers should match (P1/P5/P10 don't yet).
- Compliance % = `get_pm_compliance_smrp` RPC (**SMRP Metric 2.1.1**, 90d), explicitly distinguished in-page from the "on track now" snapshot; documented as the **Stair-2 gate metric** (>80% for 2 consecutive weeks).
- Per-asset detail drill-down reads the raw scope table with a `canonical-allow` comment (full completion history; the view only exposes last completion) — sanctioned exception, documented in place.
- P2 (label "Due this week" vs 14-day window) stands as the only open page-local finding.

### 9.20 predictive.html — RETIRED (Phase 4) · tiles still render if deep-linked · disposition = T4

Delisted from nav 2026-06-10; file kept so old deep-links don't 404. Tiles trace clean (`asset_risk_scores` latest-per-asset: hot = `risk_level IN (critical,high)`, healthy = `low`; earliest forecast = min `days_until_failure`; chip declares MTBF @365d fixed window vs Analytics' selectable — both correct, declared). Its jobs live in asset-hub risk-360 + analytics Phase 3. **Only action = T4** (exclude from survey corpus); optionally add a "this page has moved" banner if deep-link traffic shows up.

### 9.21 project-manager.html — 5 units · ALL LIVE ✅ (4 / 4 / 0 / 0) · 0 new findings

Project owner page (write surface → base `projects` legitimately). Tiles: project list 4 · active (`status='active'`) 4 · past end date (§7: `end_date < today AND status NOT IN (complete,cancelled,archived)`, red ≥3) 0 · on-hold/planning 0. Completion % = avg `pct_complete` over `v_project_items_truth`; `generate_project_code` RPC on create; chip declares `projects + project_items`. Verdict rule documented in-page.

### 9.22 project-report.html — 0 tiles (report page, correct) · 0 new findings

The project vertical's document page. Reads show the **PROJ-DRIFT fix holding in place**: `v_project_truth` with PostgREST output-aliases `id:project_id, end_date:target_end_date` (line 258 — the exact 06-10 repair), + `v_project_items_truth`, `project_links`, `v_project_progress_truth` (60 latest), and `project-orchestrator` invoke for the AI narrative. Live-verified 06-10 (47% · 3/7 · period render); orchestrator narrative belongs to Track A4 persona pass.

### 9.23 report-sender.html — 4 units · LIVE ✅ (0/0/0 composer idle) · 0 findings

Distribution layer: compose → send/schedule AI reports. Tiles are composer state (reports selected / recipients / saved contacts — counts of the current draft, not derived KPIs). Sources: `v_ai_reports_truth` (available generated reports), `report_contacts` (CRUD), `voice-report-intent` edge fn (speech → which-report-to-whom intent), `scheduled-agents` (recurring sends). Purpose: get reports out of the platform; Tier-3b voice tool stays a tool (A4 persona).

### 9.24 resume.html — 0 tiles (builder tool, correct) · 0 findings · D3 = OUT of companion scope

JSON-Resume builder: `resume_documents` (draft persistence, update-or-insert), `resume_versions` (history with a visible 10-version cap — older pruned), `resume-extract` (upload → AI extract) + `resume-polish` edge fns. Distinct product with its own data island — confirms the D3 recommendation (out of Companion unification).

### 9.25 shift-brain.html — 4 units · LIVE ✅ · P1 EXTENDED (chip lies too)

Tiles read the saved plan payload (`shift_plans`, generated by `shift-planner-orchestrator`, Promise.allSettled sub-agents):

| Payload leg | Source (in orchestrator) | Derivation |
|---|---|---|
| risk_top | `v_risk_truth` | banded `.in(risk_level,[high,critical])` ✓ (registry-governed, SB-1 fix holds) |
| pms_due | ⚠ `v_pm_compliance_truth.is_due` | **flat-30 proxy = P1** |
| carry_forward | `v_logbook_truth` | open entries > 8h old (prior-shift leftovers) |
| parts_prestage | inventory | at/below reorder point |

**P1 extension:** the page's source chip declares "shift_plans + v_risk_truth + **pm_scope_items**" while the orchestrator actually reads `v_pm_compliance_truth` — the chip repeats the docstring's lie. Fix both with the P1 repoint (same caption-truth discipline as the 06-10 chip fixes).

### 9.26 skillmatrix.html — 4 units · LIVE ✅ · P3 stands

Worker-scoped skill progress vs target. Model declared in-page: **WorkHive Skill Tier Model (platform-internal), 5 levels × 5 disciplines**; on-target = actual level (highest consecutive badge from L1) ≥ target; quizzes gated by reach + cooldown; badges from `skill_badges`. P3 (stale "max 5×6=30" explainer copy vs the 25 model — the SM-1 fix corrected the tile, not the prose) is the only finding. Distinct-subject vs achievements documented in §9.1.

### 9.27 voice-journal.html — 0 tiles (companion surface, correct) · LIVE (companion arc) · 0 new findings

The dedicated companion page: `voice-transcribe` (speech→text), `ai-gateway` agent `voice-journal` (the ONE front door; in-code comment at line 1020 documents the envelope unwrap — the L0 "flop" fix holding), `tts-speak` (Azure tier-2 fallback documented), `voice_journal_entries` (worker-scoped journal), `v_worker_truth`/`worker_profiles` (persona prefs). The memory-recall + fabrication fixes (companion arc, AI_ASSET_VERSION 6) ride this surface; its probe coverage lives in the companion dev tool, not here.

---

## 10. §9 roll-up — coverage + the findings register

**Coverage: 28/28 pages audited at provenance depth** (analytics = §8's 29 blocks; every other page = §9.1–9.27). Every tile on every page now has: source → derivation → standard/basis → live status, in this doc.

| # | Finding | Page(s) | Class | Severity |
|---|---|---|---|---|
| P1 | shift-brain pms_due reads flat-30 `is_due` + docstring AND chip claim scope-items | shift-brain / orchestrator | same-job-different-derivation | 🔴 |
| P5 | `predictive.py` stale FREQ_DAYS ×2 → calendar 1·5 vs canonical 5·25 + health-score skew | analytics P3 (+report §3.2) | missed-fix instance | 🔴 |
| P10 | ai-orchestrator PM agent prompt hard-codes flat-30 → the BRAIN tells workers 1 overdue vs canonical 5 | assistant + every gateway `assistant` caller | same family, AI surface | 🔴 |
| P9 | `asset_nodes.pm_asset_id` NULL for all 30 nodes → 360 "PM completed" dark platform-wide | asset-hub | seeder gap + silent-dark-tile | 🔴 |
| P7 | frequency-map validator blind to missing-vocabulary-absorbed-by-default (passes despite P5) | gate | gate-gap | 🟠 |
| P14 | offline-queue (IndexedDB) failure blanks logbook feed despite successful cloud fetch | logbook | offline-first hardening | 🟠 |
| P6 | analytics PM calendar recomputes vs reading baked truth signals | analytics P3 | read-don't-recompute | 🟠 |
| P12 | index "Low Stock (4)" includes out-of-stock; inventory shows 3 (consumer-side fix on index) | index/inventory | same-label-different-count | 🟠 |
| P13 | `oh-*` heartbeat cards (+ plant-conn status cards) untagged → battery/survey blind; T2 cluster undercounts | index, plant-conn | survey coverage | 🟠 |
| P2 | "Due this week" label vs 14-day window | pm-scheduler | caption-lies | 🟡 |
| P3 | "max 5×6=30" stale copy (model = 25) | skillmatrix | caption-lies | 🟡 |
| P8 | "max 60" total-level caption (model = levels→100; live 62 already exceeds) | achievements | caption-lies | 🟡 |
| P11 | hive open-issues stock leg client-derived + "low stock" lumps out-of-stock | hive | unregistered derivation | 🟡 |
| P4 | asset-hub tiles read base `asset_nodes`, chip says truth views (legit, undeclared) | asset-hub | doc/chip nuance | ⚪ |
| — | marketplace current_tab UI-state tile + grid/count duplication (06-08 queued, undispositioned) | marketplace | Tesler / dedup | 🟡 |

**The headline pattern Ian's instinct found:** the PM-frequency canonical fix (2026-06-10) reached the VIEW + html consumers, but **three non-HTML consumers kept the retired derivation** (edge fn prompt, python module, orchestrator fetch) — and the gate that should catch it only scans value-contradictions in a file set that misses prompts. "One number, one place" holds on PAGES; it does not yet hold for the BRAIN and the python layer. That's the strongest argument yet for the P1+P5+P10+P7 family fix as the first implementation batch.

---

## 11. THE SYNTHESIS — what actually gets fused (the streamline itself, 2026-06-12)

_Ian: "this one is similar to this — why don't we just fuse this together into one unified… I want that kind of thinking." This section IS the streamline: every cluster of surfaces doing the SAME JOB, with an opinionated fuse/keep verdict. Built on §7–§10's evidence._

### ★ THE ANCHOR PRINCIPLE (Ian, 2026-06-12): everything fuses ONTO the Analytics Engine

The Analytics Engine is the platform's richest computation source — 4 phases × 29 blocks, standards-stamped python formulas, the canonical RPCs. So the fusions below don't just share renderers; **they share the ENGINE.** The Analytics Engine becomes the platform's one computation brain, and every fused surface renders a SLICE of it:

| Engine phase | Anchors which fusion | What it already computes |
|---|---|---|
| Descriptive | the KPI headers everywhere | MTBF/MTTR/OEE/PM-compliance/Pareto (ISO 14224, 22400-2, SMRP) |
| Predictive | **F2** risk strip · **F3** stockout half | health scores, next-failure, anomaly baseline, stockout dates (ISO 13381-1, 7870-2) |
| Prescriptive | **F1** Action Brief — its 5 functions ARE AMC's 5 sub-agents | priority ranking, PM intervals, technician assignment, parts reorder, Groq narrative (ISO 55000/55001, SAE JA1011, SMRP) |

So F1's engine is NOT a new orchestrator merged from AMC + shift-planner — it's **the prescriptive phase given a `horizon` parameter** (shift / today / strategic). AMC and shift-planner get deleted as duplicate brains, not merged as equals.

**Two engineering caveats (honest, must be designed in):**
1. **Freshness:** the engine is snapshot-based (compute-on-first-view, daily cadence); the shift horizon needs fresher inputs → the horizon param triggers a scoped recompute over the live truth views for the shift window (cheap — it's a filter, not a full 90d pass), falling back to the latest snapshot.
2. **Live counts stay on truth views:** simple presence counts (open WO, members, pending approvals) are NOT analytics — they keep reading `v_*_truth` directly. The engine anchors DERIVED intelligence (risk, forecasts, recommendations, compliance), not row counts.

This also re-weights S1: P5/P6 (fixing the engine's own frequency map + making it read baked truth signals) stops being "one consumer among three" — **it's the foundation everything else will anchor on.** The engine must be canonical-correct before anything fuses onto it.

### F1 — ONE Action Brief ("what should we do?") — ★ THE FLAGSHIP FUSION

Today **four separate AI engines** each generate an action list from the SAME truths, rendered four different ways on four pages:

| Sub-job | AMC brief (alert-hub, `amc-orchestrator` 5 sub-agents) | Shift plan (shift-brain, `shift-planner-orchestrator`) | Prescriptive (analytics P4 + report §4) |
|---|---|---|---|
| Who's at risk | Failure-Predictor | `risk_top` (v_risk_truth banded) | Priority Ranking (ISO 55001) |
| Which PMs | PM-Planner | `pms_due` | PM Due Calendar + Interval Optimization |
| Which parts | Parts-Stager | `parts_prestage` | Parts Reorder + Stockout Risk |
| Who does it | Crew-Builder | (assignments in plan) | Technician Assignment (SMRP) |
| Narrative | Briefing-Composer | briefing | Groq Action Plan (ISO 55000) |

**The overlap is 1:1 sub-agent for sub-agent.** Three orchestrators maintaining three copies of the same brain, drifting independently (P1/P5/P10 proved they ALREADY disagree).

**Fusion:** ONE `action-brief` engine (fold AMC + shift-planner into one orchestrator with a `horizon` param: `shift` / `today` / `strategic-90d`) + ONE brief-renderer component. alert-hub renders today's brief; shift-brain renders the shift slice of the SAME row; analytics/report render the strategic slice. Project narrative stays separate (different subject). **Deletes:** 2 orchestrators, 3 bespoke renderers, and the cross-page "see also the AI plan over there" reminders — the reminders exist BECAUSE the brain is split.

### F2 — ONE risk strip (component, not copies)

Today: index `oh-top-risk`, shift-brain risk card, alert-hub risk-alert rows, asset-hub Critical tile — four bespoke renderings of `v_risk_truth`. **Fusion:** asset-hub = canonical risk home (already ruled, T2); ONE shared `risk-strip` component (top-N, same bands/ordering, deep-link to asset-360) reused everywhere else. Analytics keeps the analytical deep-dive (health scores = different altitude). **Deletes:** 3 bespoke renderings.

### F3 — ONE parts-action list

Today THREE analytic variants answer "which parts will block work": stockout forecast (P3), reorder recommendation (P4), parts-prestage (shift) — plus 3 count tiles (inventory Out/Low, index Low-Stock, hive stock leg). **Fusion:** one derivation (stockout-date + reorder-flag + prestage-need = one urgency-ranked list), one component; inventory owns it; index/hive show its count chip; F1's brief embeds it as the parts section. **Deletes:** 2 analytic variants + the P11/P12 inconsistencies by construction.

### F4 — ONE PM-due strip

After S1 makes the numbers identical: one `pm-due-strip` component (overdue + due-soon + scope label) reused by pm-scheduler (owner), shift-brain, analytics calendar, index signal. **Deletes:** per-page re-derivations; P1/P5/P10 can't recur because there's one renderer reading one signal.

### F5 — Growth: achievements + skillmatrix → ONE page (PROPOSE, Ian verdict)

Same audience (worker), same job ("how am I progressing?"), two vocabularies (XP domains/levels-to-100 vs badge tiers/targets) that §9 showed even confuse their own captions (P3, P8). **Fusion:** one "Growth" page, two tabs (Skills · Achievements), one level-language. **Deletes:** 1 nav node + the healthy/on-track lookalike confusion (T3c).

### F6 — Reports hub: analytics-report + project-report + report-sender → ONE page (PROPOSE)

Three pages = generate-doc, generate-doc, send-doc. **Fusion:** one "Reports" page — pick report type (analytics / project / benchmark), generate, then send/schedule in place (report-sender's contacts + scheduled-agents become the Send pane). **Deletes:** 2 nav nodes; the "go to report-sender to send this" hop.

### F7 — Connections: integrations + plant-connections → ONE page (PROPOSE)

Both are "connect external systems" consoles and §7's affordance map shows they already cross-link each other both ways. **Fusion:** one "Connections" page, tabs CMMS · IoT/OT · Enterprise (SSO/retention). **Deletes:** 1 nav node + 2 extra paths.

### F8 — AI Q&A: already Track A

Asset-hub Q&A + hive Coach fold into the Companion (A2/D2); persona pass (A4) makes the remaining narratives sound like ONE assistant. With F1, the platform's AI surfaces collapse to: **the Companion (conversational) + the Action Brief (push) + analytics (analytical)** — three roles, one persona, one memory.

### Net effect if all accepted

- **Pages: 28 → 24** (F5 −1, F6 −2, F7 −1) on top of Phase 4's page work.
- **AI "what to do" engines: 4 → 1** (+project), with horizon slices instead of clones.
- **Bespoke tile renderings → 4 shared strips** (risk, PM-due, parts, brief) — "one job, one place" becomes structural, not aspirational: a number can't drift if only one component renders it.
- Cross-page "reminder" links pointing at other pages' AI become unnecessary and get deleted with their parents.

### Phase mapping

Folded into the unified §4 table (2026-06-12): F2/F3/F4 = **S5** · F1 = **S6** · F8 = **S7** · F5/F6/F7 = **S8**. Disposition column lives in §4's "Open dispositions": F1 ☐ · F2 ☐ · F3 ☐ · F4 ☐ · F5 ☐ · F6 ☐ · F7 ☐.

### Walk gotchas captured (for the next live run)
- `ufai_battery.js` is a **single arrow function** — `(0,eval)(src)` returns it UNCALLED; must invoke: `const f=(0,eval)(src); f()`. (Cost one debug loop.)
- Playwright MCP `browser_evaluate` `filename:` saves to workspace root — zero-context-cost pattern for bulk harvests; move files after.
- Stale MCP Chrome profile lock → kill `mcp-chrome-*` processes, don't restart the MCP server.
- `npx supabase` dies in this repo path (`&` in "Build & Sell" breaks cmd) — use curl against `127.0.0.1:54321` with the standard demo anon JWT instead.
- Bridge rewrite (`test-data-seeder/app.py:3156`) covers URL+key — pages boot local automatically; sign-in persists in localStorage across the whole walk.

---

## 12. GROUP C SYNTHESIS — component dedup + the AI-fragmentation finding (2026-06-14)

_Ian: "ask my relevant skills (via Memento) what's still most valuable to streamline, then synthesize." This section is that synthesis — the skill-grounded answer to "what's left, and in what order." Skills consulted: Architect, Frontend, AI-Engineer, QA + `reference_holistic_critic_tooling.md` (the 2026-06-07 reputable-source research: jscpd / Nielsen-Norman / WCAG / axe-core). No external search needed — the skills already held it._

### Where S0→S8 left the platform
Number-level duplication (S1–S4) and page/tile-level duplication (S5–S8 / F1–F8) are **drained**. What the skills flag as still-redundant is one layer down — **duplicated CODE** — plus the half of Ian's original charter that S7 only started: **fragmented AI displays.**

### Ranked by value (the survey's own "user-felt weight" + skill leverage)

| Rank | Job still duplicated | Verdict | Lands as |
|---|---|---|---|
| 1 | **AI displays still fragmented** — same face, two brains (`assistant.html` vs `voice-journal.html`) + ~13 persona-less inline AIs | 🔴 Highest *user* value — literally the unfinished half of the charter ("all AI displays also fragmented"). But a *different kind* of work (AI unification, higher risk) than component dedup. | **D5 — surfaced, NOT committed.** Its own arc if Ian says go. |
| 2 | **~530-line `<script>`/`SUPABASE_URL` boilerplate** copy-pasted across shift-brain ↔ plant-connections + siblings | 🟠 Highest *leverage* — where the duplicated LINES actually live; the real path to <15%. Riskiest (every page's boot path). | **S13** |
| 3 | **`detail_panel` ×14** breakdown block | 🟡 Safe, proven S5 pattern; biggest single *named* clone family. | **S10** (lead) |
| 4 | **`.simple-card` 3-tile header ×15** | 🟡 Safe, proven pattern. | **S11** |
| 5 | **No forward-only gate on clone debt** (the 2026-06-07 `validate_clone_debt.py` is gone from the tree) | 🟢 Cheap, locks the gains in. | **S12** |

### Three corrections the skills forced on the first sketch
1. **S12 — `validate_clone_debt.py` was NEVER missing (correction logged at build time, 2026-06-14).** The "absent from the tree" claim came from a Glob scoped only to `tools/`; the validator lives at repo **root** and was registered + functional all along. S12 **enhanced it in place** (clone-COUNT → duplicatedLines ratchet + exclude predictive.html), it was not rebuilt. **Lesson: confirm a file's absence at the ACTUAL path (`git ls-files | grep name`) before declaring a rebuild — a single-dir Glob is not proof of absence.**
2. **Ratchet on % / lines, not count.** jscpd count went **73 → 70** (looks better) while % went **24.65 → 27.5** (worse) — S8's page fusions shrank the denominator. A count-based ratchet would rubber-stamp a proportional regression. Gate the %/lines.
3. **★ CORRECTED at S13 (2026-06-14): the "~530-line boilerplate" was largely a jscpd MIRAGE, not the real lever.** Investigation (reading both sides of the top clones) showed: the big 539-line clones are **template-shaped per-page render fns** (each renders its own data → survey **T6 = KEEP**, Jakob); `showToast` is **25 variants** (2 identical); the only true clone (Supabase init) is a **`getDb()` migration**, not a collapse. So `<15%` is NOT safely reachable without genericizing survey-KEEP code. **Group C WRAPPED at S10–S12** — real component dedup (toggle + card CSS) shipped, clone-debt **gated forward-only** at an honest 25.92% floor. **Lesson: jscpd's duplicated-LINE count conflates structural template-SHAPE with literal copy-paste — read both sides of a clone to confirm it's actually-identical-and-extractable before scoping a "collapse."** The getDb-migration is logged as **D7** (separate effort).

### The fork for Ian (D5)
Group C is the **component-dedup spine** Ian approved. The skills are clear that the single *most valuable* thing still un-streamlined is the **AI-display fragmentation** — the other half of the charter. It's deliberately left as **D5 (surfaced, not committed)**: say the word and it opens as a parallel arc; otherwise Group C stands alone. Either way — **plan-only until the build-go (D6).** _(D5 RESOLVED 2026-06-14 — see §6 changelog: the split-brain was already closed; the one remnant, hive.html's Reliability Coach, is now folded onto `ai-gateway` agent `coach`.)_

---

## 13. USER-FACING JARGON AUDIT (P15, 2026-06-14 — Ian: "why do we have these sloppy details… check everything in all pages, irrelevant details my users can't even understand")

**The complaint, verified.** Ian screenshotted dashboard captions reading like:
`Source: v_logbook_truth + v_risk_truth + v_inventory_items_truth · PM overdue via get_hive_dashboard · PM overdue: get_hive_dashboard.pm_overdue_count (distinct assets, 30-day anchor)` and `PMs Overdue: shared _pmOverdueCount (from loadPMHealth)` and `Empty or zero values are dimmed via hideZeroStat()` and `see KPI_ENGINE.md`. A Filipino plant supervisor/technician cannot read **any** of that — it's the platform's internals leaking onto the glass.

### 13.1 Why this happened (root cause — the honest answer)
The leak is the **provenance / honesty layer** misfiring, not random sloppiness:
- The platform has a deliberate, GOOD principle — *every canonical KPI must show WHERE it came from and WHAT window* (`renderSourceChip`, the `kpi_source_registry`, the "How these are derived" blocks, `KPI_ENGINE.md`). The intent is **trust + anti-fabrication**: show the worker the number is real, not invented.
- But the chip text was **authored in engineer voice** — whoever wrote each `renderSourceChip({source: …})` pasted the *literal implementation they were looking at* (the view name, the RPC, the helper fn, the doc filename) instead of translating it to the user's language.
- **No Designer/Content gate ever asked "would a Filipino plant supervisor understand this string?"** So a trust feature became a jargon dump. It's the classic *provenance-implemented-as-a-copy-of-the-internals* anti-pattern — the same root as exposing a stack trace to an end user.

### 13.2 Findings register (platform-wide scan, user-facing text only)
| # | Leak class | Examples | Where | Scope |
|---|---|---|---|---|
| **L1** | **DB view names** | `v_logbook_truth`, `v_risk_truth`, `v_pm_compliance_truth`, `v_asset_truth + v_fmea_truth + v_weibull_truth` | `renderSourceChip` `source:` field; explainer blocks | **37 pages** |
| **L2** | **RPC / edge-fn names** | `get_hive_dashboard`, `get_hive_dashboard.pm_overdue_count`, `v_logbook_truth via Postgres RPCs`, `ai-orchestrator edge fn (mode: coach)` | source chips | **26 hits** |
| **L3** | **Code identifiers** | `hideZeroStat()`, `loadPMHealth`, `_pmOverdueCount`, `shared _pmOverdueCount` | "How these are derived" + chips | **~9 pages** |
| **L4** | **Internal doc refs** | `see KPI_ENGINE.md`; (`PRODUCTION_FIXES.md`, `STRATEGIC_ROADMAP.md` etc. — verify which are user-visible vs JS comments) | explainer blocks | KPI_ENGINE.md ×9 |
| **L5** | **SQL predicates / column names** | `qty_on_hand == 0 OR qty_on_hand <= min_qty`, `created_at >= midnight (hive scope)`, `distinct assets, 30-day anchor`, `next_due < CURRENT_DATE` | source chips | several |
| **L6** | **Internal build-phase codes** | "Phase 8 of AGENTIC_RAG_ROADMAP.md", "Phase 1.3", "(W1 wiring gap)", "C4" in visible captions | scattered headings/notes | spot-check |

**Primary vector: `renderSourceChip` — 41 chips across 22 pages** (hive.html alone has 10). Secondary: the per-page "How these are derived" / "About this dashboard's data sources" explainer `<details>` blocks. _(Note: a `v_*_truth` in a JS `// canonical:` comment is NOT user-facing — the fix targets only rendered strings; the validator below must distinguish the two.)_

### 13.3 THE SYNTHESIS — what to do (one fix, two parts)
**Keep the trust signal; translate the content.** Provenance is worth keeping — workers DO benefit from "this is live, from your real data." The fix is a **plain-language provenance layer**, owned in ONE place (`renderSourceChip` in utils.js):

| Today (engineer voice) | Proposed (user voice) |
|---|---|
| `Source: v_logbook_truth + v_risk_truth + v_inventory_items_truth · PM overdue via get_hive_dashboard` | **"Live from your logbook, risk & inventory · updated when you open the page"** |
| `PMs Overdue: shared _pmOverdueCount (from loadPMHealth)` | **"Overdue PMs across your hive"** |
| `Empty or zero values are dimmed via hideZeroStat()` | **"Empty values are greyed out so you can see at a glance which have data"** |
| `qty_on_hand == 0 OR qty_on_hand <= min_qty` | **"out of stock, or below reorder level"** |
| `see KPI_ENGINE.md` | _remove_ (or link a user help page, never a dev doc) |

**Two work parts (plan-only — Ian's go before building, blast radius ≈ 22–37 pages, text-only ⇒ reversible):**
1. **Translate** — give `renderSourceChip` a friendly vocabulary (a `view → plain-label` map, e.g. `v_pm_compliance_truth → "PM compliance"`), and rewrite the ~41 call sites + the explainer blocks to user language. One owner, consistent voice.
2. **Gate it forward-only** — a new `validate_user_facing_jargon.py` (the S12/D7-style ratchet): scan **rendered** strings (chip args + visible text, NOT JS comments) for the forbidden patterns — `v_\w+_truth`, `get_\w+\(`/RPC names, `_camelCase()` / known helper idents, `*.md`, SQL operators (`==`, `<=`, `>=` with column names) — and FAIL so jargon can never leak onto the glass again. Register in `run_platform_checks.py`.

**Disposition:** AUDITED + synthesized (this section) → **BUILT 2026-06-14 as E1** (see §14 E1 row + §6 changelog). One refinement surfaced during the build and is now the locked design: the `source:` field is NOT stripped of view names — it stays canonical so `validate_source_chip_truth.py` can keep verifying lineage against real `.from()` reads — and `renderSourceChip` translates it through `WH_SOURCE_LABELS` at render time. So the jargon gate scans the user-visible fields (`freshness`/`window`/`notes` + explainer prose) and treats `source:` as the one sanctioned, machine-translated channel. This keeps lineage honest AND the glass plain. Skills written: designer, seo-content, qa, frontend.

**★ CORRECTION (2026-06-14, Ian caught it — screenshot of the "About this dashboard's data sources" block): E1 was INCOMPLETE.** The first pass fixed the source *chips* but missed the **secondary vector this very table named (L3/L4/L5 "explainer blocks")** — the per-page "how it's derived" `<details>` items + tooltips, which wrap raw tokens in `<code>` (`<code>v_maturity_truth</code>`, `<code>qty_on_hand &lt;= min_qty</code>`, `<code>KPI_ENGINE.md</code>`, `<code>hideZeroStat()</code>`) and in `title=`/`placeholder=`. `validate_user_facing_jargon.py` reported **0** while ~**31 leaks across 16 pages** sat on the glass — because it **exempted `<code>` and stripped attributes** (a green gate with a blind spot certifies the leak). **NOW FIXED:** all 31 translated to plain language (validator genuinely 0, live-MCP-verified on real asset-hub), AND the validator **hardened to scan inside `<code>`** (only `<pre>` exempt) **+ scan `title`/`aria-label`/`placeholder`** so the class can't recur. canonical-anchor `insight_panel` stayed PASS (lineage intact). Lesson → qa-tester.

---

## 14. STREAMLINE EXTENSION — the CONSISTENCY & CLARITY layer (2026-06-14, Ian: "ask relevant skills + reputable sources, synthesize, lay it out")

**Framing.** Phases S1–S8 + Group C + D5/D7 did the *structural* streamline — ONE truth per KPI, page fusions, component dedup, one AI front door. **What's left is the layer the USER actually feels:** make the now-consolidated platform **speak one language, look one way, behave one way.** P15 (the jargon leak) is the first crack in this layer; the items below are the rest.

### 14.1 Method (per the standing directive)
**Skills consulted:** `designer` (design system: colors/type/spacing/radius already defined — but as inline values, not tokens; owns "specify EVERY state — default/hover/active/disabled/**empty/loading/error**" + flags design debt), `seo-content` (microcopy/plain language), `qa-tester` (the holistic critic is per-element → blind to redundancy/IA — see `reference_holistic_critic_tooling`), `mobile-maestro` (44px touch, safe areas), `performance` (query fan-out), `architect` (the IA rubric `score_ia_streamlining.py`: KEEP/CONSOLIDATE/MOVE/REMOVE). **Reputable sources:** GOV.UK Content Design (plain English is the ethos — even experts prefer it, understand faster), NN/g (progressive disclosure "disclosure ladder" + reveal-on-demand; dashboard layout KPIs→trends→tables on an 8px grid; microcopy = verb+object, concise+neutral copy +58%/+124% usability), Design-system + WCAG 2.2 AA (consistent type/color/spacing tokens; focus ring 3px; touch target 44×44; contrast; ARIA; axe-core ratchet).

### 14.2 The synthesis — ranked by USER-FELT value (engine proposes, Ian disposes; all PLAN-ONLY)
| # | Item | What's still needed | Why (skill + source) | Owner | Gate (forward-only) | Blast |
|---|---|---|---|---|---|---|
| **E1 ✅ DONE 2026-06-14** | **Plain-language / microcopy pass** (the P15 jargon leak — chips + explainers) | ~~One voice across ALL user text~~ → **shipped:** `renderSourceChip` translates `source:` via `WH_SOURCE_LABELS`; **58 jargon strings / 16 pages** rewritten (chip notes/freshness/window + explainer blocks + RCM option labels); `validate_user_facing_jargon.py` ratchet at **0**. Remaining microcopy (button verb+object lint, tooltips, toast voice) folds into a later pass. | GOV.UK plain-English ethos; NN/g microcopy (+58%/+124%); Ian flagged it directly | seo-content + designer | ✅ `validate_user_facing_jargon.py` (registered, baseline 0, forward-only) | **High** (most pages) |
| **E2 ✅ DONE 2026-06-14** | **Consistent empty / loading / error states** | ~~Every dynamic surface shows empty + error + loading~~ → **shipped the mechanism + gate:** shared `whListSkeleton` / `whListError` in utils.js + `.wh-skeleton`/`.wh-list-error` in components.css (shimmer, reduced-motion fallback, 44px retry); **2 new List-View-Contract rules** (`frontend_list_view_has_loading_state` 33%, `frontend_list_view_has_error_state` 50%, both medium → ratchet, accept the shared-helper call OR a markup anchor OR catch→toast). Inventory wired as the live exemplar (skeleton-on-load + error+retry). Full rollout = forward ratchet (empty-state got to 93% the same way). | designer "specify every state"; List-View-Contract miner (loading was the 70%-blank gap); NN/g loading/empty-state | designer + frontend | ✅ 2 rules in `skill_rules_manifest.json` (mined by `mine_skill_rules.py`) | **High** |
| **E3 ✅ DONE 2026-06-14** | **Accessibility consistency — WCAG 2.2 AA ratchet** | **Built `tools/axe_scan.js`** — vendored `axe-core@4.10.2` (`tools/vendor/`, no npm dep — the `&` path breaks npx) driven by the installed Playwright via `node` at 390px mobile width; runs WCAG 2.2 AA (`wcag2a/2aa/21a/21aa/22aa`) and ratchets per-page violation nodes **forward-only** vs `axe_baseline.json`. **Honest baseline: 11/20 reachable pages all 0 violations** (416–1047 real els each → credible; the prior reactive a11y work held — contrast/44px/ARIA). The 9 session/hive-gated pages **skip-on-`signin=1`-redirect** (never bank a hollow bounce) → covered via journey-spec wiring (documented follow-up). | WCAG 2.2 AA; `reference_holistic_critic_tooling`; mobile-maestro 44px | qa + mobile-maestro + designer | ✅ `node tools/axe_scan.js` (baseline → forward-only; runs in the Playwright/Phase-4 layer, not the static `--fast` suite) | **High** (test layer) |
| **E4 ✅ DONE 2026-06-14** | **Design-token consolidation** (the visual half of Group C) | **Promoted the designer palette/type/spacing/radius to CSS custom properties** in `components.css` `:root` (`--wh-orange #F7A21B` / `--wh-blue #29B6D9` / `--wh-navy #162032` / steel / cloud + `--wh-space-*` 8px grid + `--wh-radius*` + `--wh-font` Poppins). components.css's own `.simple-card`/`.sc-hero`/`.tag-amber`/`.action-card` converted to `var(--wh-*)` as the exemplar. **Gate `validate_design_tokens.py`:** L1 token-block integrity (every canonical value present → palette can't drift/delete), L2 `#e8920a` drift-hex ban, L3 raw-brand-hex inline ratchet (baseline **1452**, forward-only → use `var()`). Full hex→var migration = ratchet. | design-system consistency + 8px grid (NN/g); natural S11/Group-C extension | designer + frontend | ✅ `validate_design_tokens.py` (registered in run_platform_checks) | **Medium** |
| **E5 ✅ DONE 2026-06-14** | **Progressive-disclosure consistency** | The explainer disclosure was already ~consistent (S10's `wireDetailToggle` + canonical "Show/Hide details" on 17/18 pages). E5 **finished + locked it:** migrated the last hand-rolled holdout (**predictive.html**'s bespoke `wirePrSummaryToggle` IIFE → `wireDetailToggle()`) → **18/18 canonical**, and added a List-View/Disclosure-Contract rule `frontend_detail_toggle_uses_shared_helper` (a page with `id="details-toggle-btn"` MUST call `wireDetailToggle()`, not hand-roll → 100% conformance, medium ratchet). Drift like logbook's "Hide extra details" is a *different* control (extra form fields) — left as-is. | NN/g progressive disclosure; builds on S10 `wireDetailToggle` | designer + frontend | ✅ skill rule (mined by `mine_skill_rules.py`, 18/18) | **Medium** |
| **E6 ✅ DONE 2026-06-14** | **Number / date / unit / currency formatting** | **Added `whFmtPeso`/`whFmtNum`/`whFmtDate`/`whFmtDuration` to utils.js** — ONE PH-locale source of truth (₱ en-PH + separators, `Asia/Manila` dates, locale numbers, singular/plural hrs/days), all **null/NaN-safe** (never `₱NaN`/`Invalid Date`). marketplace's `avg ₱${avgPrice.toLocaleString()}` → `whFmtPeso(avgPrice)` as the exemplar. Gate `frontend_currency_uses_shared_formatter` (a page printing ₱ should call `whFmtPeso()`) — 6 peso pages, ratchets up as they migrate (like E4's hex). | consistency heuristic; field locale (PH) | frontend + data-engineer | ✅ skill rule (mined) | **Medium** (polish) |
| **E7 ✅ DONE 2026-06-14 (gate; collapse = ongoing)** | **Performance / load consistency** (the flagged 5th dimension) | **Built `tools/request_budget_scan.js`** — node + Playwright (axe-scan sibling) loads each page, counts Supabase DATA requests (`/rest/v1/` + `/rest/v1/rpc/` + `/functions/v1/`) on load, ratchets per-page **forward-only** vs `request_budget_baseline.json` (fan-out can only shrink). Baseline: 11 reachable pages **1–10 calls** each (index=10 heaviest reachable; analytics/asset-hub 3–5; most ≤2). **★ hive.html (~37 calls) is auth-gated → skipped** (same as E3) → its fan-out collapse (`get_hive_board_dashboard`, partly done) is the deeper perf arc + journey-spec target; the gate locks the reachable surface forward-only now. | GROUNDED_SWEEP "Load/Stress is the real gap"; `project_fanout_rpc_collapse` | performance + data-engineer | ✅ `node tools/request_budget_scan.js` (Playwright/Phase-4 layer, not static `--fast`) | **High value / higher effort** |

### 14.3 Recommended sequence
**E1 first** (Ian flagged it, highest user-felt, and P15 already built the seed validator) → **E2** (broken/blank screens are the next thing users hit) → **E3** (axe-core ratchet — mostly test-layer, locks accessibility forward-only) → **E4** (visual tokens, finishes Group C's CSS half) → **E5/E6** (polish) → **E7** (its own performance arc, partly separate track). Each is the **CONSOLIDATE/clarify** half of the IA rubric, gated forward-only like every prior phase. **All plan-only — say which E# to open.**
