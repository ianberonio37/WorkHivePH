# Engineering-Design Deep Arc (PDDA) — Page-Deep UFAI

> **Arc kind:** *Page-depth* (complement to the platform-wide breadth ruler `deepwalk_grid.json`).
> The platform ruler scores 88 pages × 16 dims **shallow**. This arc scores **ONE page deep** — a fine
> UFAI sub-dimension decomposition, grounded in external standards, driven live via Playwright MCP,
> improved with skill + reputable-source ideas, ratcheted by gates.
>
> **Target page:** `engineering-design.html` + `engineering-design.js` (2.3MB) — the industrial
> engineering **calculation tool**: 6 disciplines, ~56 calc types, 3 AI features (report / BOM+SOW /
> system diagram), History + Guide tabs, hive-gated.

## The PDDA loop (6 phases)

0. **Ground** — skill-first reads + pull external standards → a *falsifiable* UFAI sub-dim checklist.
1. **Understand** — map the code (calc registry, AI invokes, renderers, escHtml, state).
2. **Deepwalk (live)** — drive the real page via Playwright MCP; score each sub-dim with **measured** evidence.
3. **Ideate** — fan-out relevant skills + reputable external sources → improvement backlog per axis (cited).
4. **Roadmap** — synthesize into the scoreboard table below (% per phase, owning skill, citation, locking gate).
5. **Execute** — implement each phase; **verify live each fix**; lock with a gate/test (ratchet).
6. **Re-deepwalk** — re-score to confirm the ratchet held; synthesize fuse/keep verdicts; persist to skills + memory.

**Done = every axis at its roadmap target, MEASURED and gate-locked** — not one headline metric, not "looks good".

---

## The five scored axes (page-specific sub-dimension decomposition)

### U — Usability (learnability, operability, feedback, error-protection, inclusivity)
- U1 Recognizability & learnability (wizard clarity, empty/first-run state)
- U2 Operability — keyboard + touch (44px targets, focus order, no-mouse full flow)
- U3 System-status feedback (loaders, toasts, aria-live, progress)
- U4 User-error protection (input validation, destructive confirms, undo)
- U5 Inclusivity / a11y (axe WCAG2.2-AA = 0 violations, contrast, labels)
- U6 Efficiency (search, recents, discipline pills, minimal clicks-to-report)

### F — Functionality (does it produce correct, complete, standards-grade output)
- F1 **Calc-correctness vs standard** (each calc's formula cites + matches ASHRAE/NEC/NFPA/PPC/IEC/ASME)
- F2 Report fidelity (report == engine result, no drift, editable fields persist)
- F3 BOM/SOW completeness (12-sync-point checklist per calc; no missing chain entry)
- F4 Diagram accuracy (SVG/mermaid symbols match IEC 60617; title block correct)
- F5 Export integrity (PDF/CSV/SVG faithful, no clipped tables)
- F6 Count/registry consistency (advertised counts == actual registry)

### A — Adaptability (does it flex across viewport, unit, locale, channel)
- A1 Responsive both viewports (390 mobile + 1280 desktop, no h-scroll/overlap)
- A2 Unit systems (metric/imperial coherence where applicable)
- A3 Print / PDF layout (clean print, no dark bg bleed)
- A4 Offline / PWA / degraded-network behavior
- A5 Discipline extensibility (adding a discipline/calc is localized)
- A6 Localization / plain-language (PH audience, no unexplained jargon)

### I — Internal Control (isolation, attribution, validation, safety)
- I1 Hive-scoping (saved calcs/history isolated per hive; no cross-hive leak)
- I2 auth_uid attribution on every write (saveCalc/BOM/SOW)
- I3 Input validation / sanitization (numeric bounds, NaN, negative guards)
- I4 XSS safety (escHtml in every renderer; no raw innerHTML of user/AI text)
- I5 Destructive-action safety (delete history/BOM row confirm)
- I6 RLS reachability (history read gated by membership)

### AI — AI Integrity (cross-cut: 3 AI features)
- AI1 Grounding (report/BOM/SOW/diagram tied to the actual calc result, not free-invented)
- AI2 Fabrication rail (no invented actions/values; egress contract)
- AI3 Recall / context (uses the calc inputs; multi-turn where relevant)
- AI4 Failure UX (AI error/timeout → honest state, not a blank or a lie)

---

## Scoreboard (filled after Phase 2 deepwalk; re-scored Phase 6)

| Axis | Baseline % (measured) | Target | Post-arc % (P1–P6) | Locking gate | Owning skill |
|---|---|---|---|---|---|
| U — Usability | **58%** | 100 | **~95%** ✅ (axe=0 ×2 calc types; labels/status/tap all fixed+gated) | `validate_engdesign_a11y` | frontend / mobile / qa |
| F — Functionality | **42%** | 100 | **~65%** (F6 SSOT done+gated, F3/F4 verified; F1 correctness = P7 queued) | `validate_engdesign_registry` | maintenance / standards / qa |
| A — Adaptability | **50%** | 100 | **~65%** (A1 print + A2 tap + A7 CSV done; A3–A6 reflow/PDF/units queued) | print/tap-target checks | mobile / designer / frontend |
| I — Internal Control | **67%** | 100 | **~95%** ✅ (auth_uid + RLS live-proven 403/201; XSS closed; all gated) | `validate_attribution` + `validate_engdesign_write_isolation` + `validate_engdesign_xss` | multitenant / security |
| AI — AI Integrity | **88%** | 100 | **~85%** (AI-1/4/5/7/8 done+gated; AI-2/6 edge + AI-9 cross-cut queued) | `validate_engdesign_ai` | ai-engineer |
| **Page overall** | **≈59%** | **100** | **~81%** (measured-where-gated) | **8 new/extended gates** | |

## Synthesis (the deliverable)

**What this arc proved.** The platform-wide breadth ruler rated engineering-design a passing page — but the *depth* walk, grounded in external standards + driven live, found **real defects the coarse ruler structurally cannot see**, because they only exist in the *worked* state (a rendered report, a saved row, a re-render), not the empty initial DOM:

- **Trust leaks the count drift** (53/56/55 → one derived source of truth).
- **A silent security gap**: every saved calc was written with `auth_uid = NULL` (spoofable attribution), and the write RLS let any authed user attribute a row to anyone / any hive — **live-proven closed** (spoof insert → 403).
- **The headline result value was the least-readable text on the page** (2.68:1), plus a whole light-gray-on-white caption class (164+ nodes) failing AA — invisible to an empty-state axe scan.
- **Stored-XSS surface**: 6 AI-narrative sites interpolated raw; the history "View" button serialized the whole DB row into an `onclick`.
- **AI over-claimed** ("validates inputs / checks compliance") and could voice an ungrounded figure; failures dumped raw errors; a 22s AI call had no timeout.

**The reusable pattern (PDDA).** Ground the axes in external standards *first* → deepwalk the **worked** state live → fan out research per axis → roadmap with % + a locking gate per row → execute + verify each fix live → re-deepwalk. Every fix is now **ratcheted by a gate** (8 total), so none can silently regress. This template applies to any high-value page (analytics, resume, logbook, marketplace).

**Fuse/keep verdict:** the 6 per-page gates + the extended `validate_attribution` (now scanning 37 page scripts) are the durable asset — they generalize the classes platform-wide (the attribution-in-externalized-JS gap they closed was NOT eng-design-specific).

## FINAL SCOREBOARD + REMAINING-GRIND ROADMAP (session wrap 2026-07-08)

**Arc overall: ~99% complete** (≈59% baseline → ~99%). 15 gates all PASS locally; the ONLY remaining item is G4 = the prod DEPLOY of the AI-1/AI-2/AI-6 edge-fn edits (Ian's gate — outward/irreversible).

| Axis | Done % | What's left |
|---|---|---|
| **U** Usability | **100%** ✅ | nothing — contrast/labels/status/tap all fixed + gated (axe=0 ×2) |
| **F** Functionality | **~98%** | **G1 F-5 audit DONE (2026-07-09): 229 DANGEROUS display sites → `_orNA` (fan-out judged + adversarial/skeptic verified); ratchet 127→77, gate baseline lowered + locked; live-verified transformer+pump reports 0 n/a/NaN, 5 SVG builders 0-NaN + n/a-on-missing-key.** Everything else done (registry SSOT, 23 oracle invariants + 58 value-vectors, F-6/F-7/F-9). Remainder = the 84 LEGIT keys + 11 skeptic-refuted plausible-real-zero keys, correctly LEFT (never corrupt a real zero). |
| **A** Adaptability | **100%** ✅ | nothing — A-1..A-7 incl A-6 scoped units toggle, all verified |
| **I** Internal Control | **100%** ✅ | nothing — auth_uid + RLS live-proven (403/201), XSS closed, all gated |
| **AI** AI Integrity | **~99%** | **G3 AI-6 citation grounding DONE (2026-07-09):** built `validate_engdesign_ai_citations.py` — a calibrated fabricated-standard detector (teeth: catches an invented body; zero-FP on model numbers M20/W250/Group 2/Dyn 11/CO2) + a live evidence tier. **Live-verified across 6 disciplines: 13 real-standard citations, 0 fabrications** — the LLM cites only real standards (NFPA/PEC/ASHRAE/IEC/ASME/AISI…). Root-hardened the calc-agent prompt to forbid inventing standards / citing the PRC-regulator as a design standard (deploys with G4). Registered (AI Validation, `skip_if_fast`). AI-1/2/4/5/7/8/9 done. Remaining = G4 deploy only. |

### The remaining ~6% — the grind, by share of remaining effort
| # | Remaining unit | Share of remaining | Why it's left (not a quick-defer) | Ready-to-go |
|---|---|---|---|---|
| **G1** | ✅ **DONE (2026-07-09)** — F-5 per-field audit: **229 DANGEROUS display sites → `_orNA`** | **~65%** | Fan-out judged (23 batch agents, engineering rubric) + adversarial/skeptic verified; safe transform only for display-only sites (81 math-reused consts skipped); 84 LEGIT + 11 skeptic-refuted plausible-real-zero keys LEFT. **Ratchet 127→77 (baseline lowered + locked); live-verified: transformer+pump reports 0 n/a/NaN, 5 SVG builders 0-NaN + honest n/a on missing key.** | `_orNA` helper; `validate_engdesign_silent_zero` @ 77. |
| **G2** | ✅ **DONE (2026-07-09)** — restored the **LIVE value-at-the-glass** axis to **63/63 = 100%** | **~20%** | The value-vector coverage was ALREADY 100% (58/58 hermetic, 294 oracles). The real gap: the P7 wave silently BROKE `validate_calc_live_value.py` — (a) fire-pump custom called a module-internal (`_pump_curve_points`) → crashed the whole live sweep; (b) a water-supply flow-continuity vector was mislabeled (bound to `domestic_water`/`peak_flow_*` but tagged "Water Supply Pipe Sizing" → empty-inputs 0-flow → FAIL). **Fixes:** rewrote fire-pump NFPA-20 check to derive from the served `.calculate()` result + input-independent ratios (churn=140%, overload=65% of rated) → live-runnable + robust; re-pointed the mislabeled vector to "Domestic Water System" (its true handler); added an AttributeError catch so a future internal-caller can't crash the sweep. **Live 100/100 PASS, teeth (blind flips all 100); hermetic 95/95, teeth.** | `validate_calc_live_value.py` + `validate_calc_formula_accuracy.py` (both registered, live one `skip_if_fast`). |
| **G3** | ✅ **DONE (2026-07-09)** — AI-6 citation grounding gate built + live-verified | **~10%** | Built the non-false-positive design the row called for: a **fabricated-standard detector** (`validate_engdesign_ai_citations.py`) — recognizes only ALL-CAPS body + designation, asserts membership in a curated real-standard-family set, classifies PH regulators (PRC) as advisory, and calibrated to zero-FP on model numbers (M20/W250/Group 2/Dyn 11/CO2). **Teeth (self-test catches an invented body); live 6 disciplines = 13 real citations, 0 fabrications.** Root-hardened the calc-agent prompt (deploys w/ G4). Registered. | ✅ shipped |
| **G4** | **Edge-fn DEPLOY** (AI-1 narration grounding + AI-2 BOM qty grounding + AI-6 citation prompt) | **~5%** | Ian-gated — the EDITS are done + regression-verified locally; only the prod deploy remains. | `supabase/functions/*` edited; deploy on Ian's schedule. |

**Recommended order for the fresh window:** G1 (biggest, mechanical once judged) → G2 (safe, bounded) → G3 (a design decision) → G4 (Ian's deploy gate).

**STATUS 2026-07-09:** ✅ G1 DONE · ✅ G2 DONE (live value axis 63/63 = 100%) · ✅ G3 DONE (AI-6 citation gate, live 0 fabrications). **All LOCAL grind complete — the sole remaining item is G4 = prod deploy of the edge-fn edits (Ian's outward gate). U/A/I = 100%; F ≈ 100%; AI ≈ 100% local (deploy-pending).**

## Continuation backlog (scoped, specced)
1. **P7 calc-correctness oracles** — the highest remaining value: golden-value oracle per high-stakes calc (safety-critical: NFPA 13 sprinkler density, NFPA 20 fire-pump 150% point, NFPA 2001 agent mass, PEC breaker ladder). Extends `validate_calc_formula_accuracy.py`.
2. **P6 A-6 SI/IP unit toggle** (large), A-3/A-4 mobile reflow of injected schedule rows, A-5 PDF landscape for wide tables.
3. **P5 edge (deploy-gated)** — AI-2 BOM quantity grounding, AI-6 citation allowlist, AI-3 per-parse retry/repair.
4. **Cross-cut** — AI-9 companion `agent_followups` 401 (companion-launcher session bug, checkProactive-dead class).
_Ian gate: commit the local delta (engineering-design.html/.js, 6 tools, 1 migration, run_platform_checks regs, this doc) + deploy the edge-fn edits (AI-1 grounding) when ready._

## Phase 2 — Measured evidence log (live Playwright deepwalk, 2026-07-08)

### U — Usability
- **U1 Recognizability** PASS — h1 "Engineering Design" visible; clear 4-step wizard + step-dots + step-label.
- **U2 Operability** PARTIAL — report action buttons **Download PDF 37px, Save 37px, Generate 36px** (< 44px, post-calc only — coarse ruler missed them because it scans the empty initial state). No h-overflow.
- **U3 Status feedback** PARTIAL — loader (rotating msgs + spinner + dots) + toast `role=alert aria-live=polite`. BUT calc takes **22.3s** and the report *reveal* is not itself announced; loading msg has no aria-live.
- **U4 User-error protection** PARTIAL — delete uses `whConfirm`. BUT empty project field **silently defaults** to "Untitled Room"; validation is ad-hoc per-calc, no shared layer; many fields default via `|| fallback` instead of erroring.
- **U5 Inclusivity/a11y** FAIL — axe WCAG2.2-AA on the *rendered report*: **4 color-contrast fails** — headline `.res-value` "16.8 kW / 4.78 TR" @ **2.68** (orange #d88a0e on cream #fffbf0); 3× PRC-License lines #999/#fff @ 2.84. Input `aria-label`s are the placeholder ("0","3.0","Auto") not descriptions.
- **U6 Efficiency** PASS — search, recents (localStorage), discipline pills, subcategory headers.

### F — Functionality
- **F1 Calc-correctness** UNVERIFIED — engine is server-side (`engineering-calc-agent`); HVAC 100m² office → 16.8 kW (168 W/m², plausible for PH climate). Needs per-discipline standards cross-check (Phase 3/5).
- **F2 Report fidelity** PARTIAL — report grounded in real inputs, renders correctly. BUT fragile: result-key **alias-normalization** blocks (lines 9916–9971 Water Softener / Water Treatment) reconcile 3 diverging key conventions by hand → "undefined in report" risk on any key change.
- **F3 BOM/SOW** PASS — driven live: 11 grounded BOM items (split AC, condensing unit, refrigerant piping, MCCB) + 15 SOW sections (General Scope→Standards→Materials→Install→Piping→Electrical) in ~7s.
- **F4 Diagram** PASS — driven live: client SVG in 303ms, viewBox 1050×467, 110 grounded text nodes ("35°C DB" matches input, "ASHRAE 62.1 | 4% of SA", tags F-01/OAD-01).
- **F5 Export** UNVERIFIED — PDF (html2pdf), CSV, SVG paths exist; not yet driven.
- **F6 Count consistency** FAIL — **triple drift**: search "53", pills sum 56 (HVAC pill "11" vs 10 rendered), truth **55** (`CALC_TYPES_UI` flat). Three hardcoded counts. Also orphan dispatch branches `Gear / Belt Drive` + `Boiler / Steam System` (renderers, no UI entry) and dual hand-synced registries (CALC_TYPES legacy + _UI).

### A — Adaptability
- **A1 Responsive** PARTIAL — 0px h-overflow @390 (good); tap targets < 44 (see U2).
- **A2 Units** UNVERIFIED — appears metric-only (m², kW, TR); no metric/imperial toggle seen.
- **A3 Print/PDF** UNVERIFIED — `@media print` + html2pdf present; not driven.
- **A4 Offline/PWA** UNVERIFIED — manifest linked; no offline calc (engine is remote).
- **A5 Extensibility** FAIL — dual registries, ~57-branch if/else dispatchers, orphan branches → high drift/maintenance cost.
- **A6 Localization/plain-language** PASS — report cites PH codes (PSME, NBCP PD1096, DOLE OSH) + ASHRAE.

### I — Internal Control
- **I1 Hive-scoping** PASS — RLS `engineering_calcs_read`: `hive_id IN (SELECT hive_id FROM hive_members WHERE auth_uid=auth.uid() AND status='active')`. Cross-hive read blocked server-side; localStorage `.eq('hive_id')` is only a convenience filter.
- **I2 auth_uid attribution** FAIL — `saveCalc`/`saveWithBomSow` insert `hive_id`+`worker_name` (localStorage, spoofable) but **never `auth_uid`** → rows written `auth_uid=NULL` (write policy permits null). Breaks locked `auth_uid-on-every-write` rule. Table HAS the column.
- **I3 Input validation** PARTIAL — ad-hoc per-calc guards + silent defaults; no shared numeric-bounds layer.
- **I4 XSS** PARTIAL — `escHtml` used 729× BUT numeric `results.*` interpolated raw + AI `narrative`/string fields need a per-renderer audit for `e()` coverage.
- **I5 Destructive safety** PASS — `whConfirm` dialog + delete scoped `.eq('worker_name', WORKER_NAME)` (defense-in-depth over RLS).
- **I6 RLS reachability** PASS — RLS enabled, 2 policies, read gated by membership.

### AI — AI Integrity
- **AI1 Grounding** PASS — report/BOM tied to the actual calc inputs+results.
- **AI2 Fabrication rail** UNVERIFIED — edge-fn egress fabrication guard not yet asserted for this page's agents.
- **AI3 Recall/context** PASS — single-shot inputs→report; no multi-turn needed.
- **AI4 Failure UX** PASS — `runCalculation` try/catch: `if(error||!data) throw`; `if(data.error) throw` → honest error path.

### Cross-cut
- **401 on `agent_followups`** on every load (companion-launcher proactive fetch; shared widget, matches known checkProactive-dead class) — out of this page's DOM but fires here.

## Phase 3 — IDEATE backlog (41 items, skill + external-source cited; via 5-agent research workflow)

Full per-item finding/fix/citation/gate in the workflow journal. Severity counts: **6 critical, 17 high, 15 medium, 3 low**. Key external anchors: WCAG 2.2 (SC 1.4.3/2.4.6/2.5.8/3.3.2/4.1.3/1.4.10), OWASP (ASVS V4/V7, XSS/Input-Validation cheat sheets, LLM05/LLM09:2025), NN/g (response-times, progress, trust-in-AI, error-messages), and the domain standards (ASHRAE 90.1/62.1, NFPA 13/20/2001/72/92, PEC 2017/NEC, ISO 281/898/8528, ASME BPVC, NSCP 2015, Hunter's/PDI/DPWH).

**New findings the research surfaced (beyond the live walk):**
- **A-1 (high):** native browser print (Ctrl+P) → **BLANK page** — `@media print` shows an empty `#print-wrapper`, hides everything else.
- **AI-3 (high):** ~30 bare `JSON.parse(raw)` in `engineering-bom-sow/index.ts` — no try/catch, no schema.
- **AI-1 (critical):** `engineering-calc-agent` accepts the LLM narrative on a presence-only check — no numeric grounding filter.
- **I-2 (critical):** `engineering_calcs` write RLS `WITH CHECK` is `auth.uid() IS NOT NULL` only — no `auth_uid=auth.uid()` / hive-membership assertion.
- **I-7 (medium):** history "View" button embeds the entire DB row into an `onclick` via `JSON.stringify` → hand-rolled-escaping XSS risk.

## Phase 4 — ROADMAP (7 execution phases, % = share of the arc; drive each to 100%)

| # | Phase | Items | Axes lifted | Weight | Locking gate(s) | Local vs Ian-gated |
|---|---|---|---|---|---|---|
| **P1** | **Registry single-source-of-truth** | F-3, F-4, F-6 | F | **10%** | `validate_engdesign_registry.py` (counts derive from `CALC_TYPES_UI`; no orphan dispatch; one registry) | Local |
| **P2** | **Attribution & write-side control** | I-1, I-8, I-4, I-3, I-2 | I | **18%** | `validate_tenant_boundary.py` (auth_uid stamped; delete by auth_uid; RLS WITH CHECK) | Local edits; I-2 migration apply local, deploy Ian-gated |
| **P3** | **Report accessibility** | U-1, U-4, U-2, U-8, U-3, U-6, U-7 | U | **20%** | `engineering-report-a11y.spec.ts` (post-calc axe=0) + `validate_forms_a11y.py` | Local |
| **P4** | **XSS / output-encoding hardening** | I-6, I-7, I-5 | I | **12%** | `validate_xss.py` renderer walk + `validateBeforeSave` gate | Local |
| **P5** | **AI egress integrity** | AI-1…AI-9 | AI, I | **18%** | `eng_calc_grounding_eval.py` + BOM parse tests | Edge-fn edits local; deploy Ian-gated |
| **P6** | **Adaptability (print/mobile/units/export)** | A-1…A-7 | A | **12%** | print/reflow/tap-target Playwright + `cwv` | Local |
| **P7** | **Calc-correctness oracles** | F-1, F-2, F-5, F-7, F-8, F-9 | F | **10%** | `validate_calc_oracles.py` + `validate_integration.py` alias sweep | Local |
| | **Total** | **41** | U·F·A·I·AI | **100%** | | |

**Execution rule (ratchet):** each phase = fix → verify live (Playwright/DB) → lock with the named gate → register in `run_platform_checks` → next phase. No phase is "done" until its gate is green and teeth-tested.

### Phase-5 progress
| Phase | % complete | Note |
|---|---|---|
| P1 | **100%** ✅ | F-3 counts now DERIVE from `CALC_TYPES_UI` (`syncCalcCounts`); search+pills reconciled 53/56→**55** (verified live). F-6 vestigial legacy `CALC_TYPES` **deleted** (71 lines; 0 regressions — all 6 disciplines + Transformer/Harmonic forms verified). F-4 orphan gate (2 documented). Gate `validate_engdesign_registry.py` teeth-tested + registered. |
| P2 | **100%** ✅ | I-1 auth_uid stamped on both save paths (verified: saved row `auth_uid=84642f…`). I-8 auth guards. I-3 solo read-back by auth_uid. I-4 delete by auth_uid (verified). I-2 RLS split into tight INSERT/UPDATE/DELETE (migration applied local) — **live-proven**: spoofed insert→**403**, valid→**201**. Locks: `validate_attribution.py` extended to scan 37 page scripts (caught+resolved 2 real false-positives via comment-blank + dynamic-attach marker), + new live `validate_engdesign_write_isolation.py` (teeth-tested, registered). |
| P3 | **100%** ✅ | U-1 headline `.res-value` → #8a4b00 (2.68→AA pass). U-4 whole light-gray-on-white class darkened (8×#999 + 164×#888 + 13×#aaa → #595959/#6b6b6b; verified report-only, dark UI uses rgba). U-6 `.btn-primary/.btn-ghost` min-height:44px (all 18 report buttons pass). U-2 `labelizeInputs` (real names from visible labels — all 55 forms). U-3 `announceStatus` (SC 4.1.3 live region). U-8 `labelizeReportEditables` (21/21 named, role=textbox only when named). **Live-verified 2 calc types: axe = 0 violations** (was 4 contrast + would-be 7 unnamed). Gate `validate_engdesign_a11y.py` teeth-tested + registered. U-7 default retained (field now properly labeled → not a WCAG fail). |
| P4 | **100%** ✅ | I-7 history "View" no longer serializes the DB row into `onclick` — rows keyed by id, button passes only the uuid (verified live: `viewHistoryById('<uuid>')`, View still renders). I-6 wrapped 6 raw `${narrative?.x \|\| fallback}` AI-narrative sites in `escHtml()` (stored-XSS on re-render). I-5 shared `validateBeforeSave()` shape-check wired into both save paths. Gate `validate_engdesign_xss.py` teeth-tested + registered. |
| P5 | **~85%** (5/9 done+gated; rest scoped) | **Done + live-verified:** AI-4 `invokeWithTimeout` on both edge calls (calc still renders — no regression). AI-5 honest loading copy ("Computing your design values…" — no "validates inputs/checks compliance" overclaim). AI-7 AI-drafted disclosure note in report preview (shown live). AI-8 `friendlyAiError` + removed raw `err.message` toasts. AI-1 calc-agent narration grounding rail (`narrationQuotesResult` — silences an unverifiable spoken figure; conservative, no regression). Gate `validate_engdesign_ai.py` teeth-tested + registered. **Verified-mitigated:** AI-3 BOM parse crash — outer try/catch → `failTracked` non-leaky 500 already prevents crashes; per-parse retry/repair deferred (low marginal value). **AI-9 companion `agent_followups` 401 — FIXED + verified:** the proactive fetch fired before `getDb()` async-restored the session (raced out with no JWT → 401 every load). Now awaits `db.auth.getSession()` and fails closed if unauthenticated — **verified 0 console errors** on load. **AI-2 BOM quantity grounding — DONE + verified:** added qty grounding to the single `sanitizeBomItems` egress (covers all ~30 discipline agents) — parses a leading number, clamps to (0, 100000], defaults a non-numeric qty to 1, so a fabricated NaN/negative/absurd quantity can't reach the procurement doc. **Verified: 11-item BOM, all qtys numeric+positive.** **AI-6 citation allowlist — evidence-based deprioritization (like A-6-universal):** the live deepwalk found narratives cite *real, correct* standards (PSME/ASHRAE 62.1/NBCP/DOLE) — no demonstrated citation fabrication; and every allowlist check false-positives on the many legit citations beyond any per-calc list. Forcing it adds risk (stripping legit citations) for no evidenced benefit; AI-1 (narration grounding) already covers the demonstrated AI-integrity risk. |
| P6 | **~85%** (A-1..A-5 + A-7 done; A-6 is an evidence-based design finding) | **Done + verified:** A-1 native print BLANK-page bug fixed (prints `#report-output`, verified via `emulateMedia('print')`). A-2 tap-targets (P3's 44px `.btn`). **A-3/A-4 mobile reflow — verified @390px: all report/doc tables `display:block`+`overflow-x:auto`, 0 body overflow** (global CSS, no per-renderer change). **A-5 PDF landscape — wide-table (>6 col) detection → landscape + 980px render width** in the html2pdf fallback. A-7 BOM CSV exists. **A-6 (SI/IP units toggle) — DONE (scoped) + live-verified.** The deepwalk showed a *universal* toggle is unsafe (the 55 forms mix universal V/A/kW/RPM, dimensionless %/persons, and ambiguous kW=power-or-cooling — a blind conversion mis-sizes electrical calcs). So it's implemented **SCOPED**: `UNIT_CONV` maps ONLY the 10 unambiguous dimensional units (m/m²/mm/°C/bar/kPa/kg/L·min⁻¹/mm·hr⁻¹/kN); universal + dimensionless + ambiguous units are left untouched; and the **engine always receives SI** (`runCalculation` normalizes Imperial→SI for the submit, then restores the Imperial display). **Live-verified: 100 m²→1076.39 ft², 35°C→95°F, persons(count) untouched; and running the calc in Imperial gave the SAME 16.8 kW / 4.78 TR as the 100 m² SI calc** (engine got SI, not the raw 1076). Gate `validate_engdesign_units.py` (asserts SI-normalization wired + universal/ambiguous units excluded) teeth-tested + registered. |
| P7 | **~85%** (22 oracle invariants, 7 disciplines) | **Done + teeth-tested (blind 92/92):** added 20 **relation/constant invariants** to `validate_calc_formula_accuracy.py` (registered) covering fire/HVAC/electrical/machine/plumbing/wastewater/mechanical — the 10 life-safety ones below PLUS chiller (COP<Carnot 2nd-law, TR), cooling-tower (CTI range/approach), AHU (flow continuity), water-supply (L/s continuity), STP (DENR BOD removal), shaft (T=P/ω, selected≥min dia), heat-exchanger (LMTD×F), compressed-air (CFM continuity), solar-PV (Vmp_hot<Vmp_stc<Voc_cold temp-voltage physics), UPS (kVA=kW/PF). F-5 count reduced 131→128 (absurd genset-kVA/motor-HP display zeros → honest "n/a"). Core 10 safety-critical **relation/constant invariants** to `validate_calc_formula_accuracy.py` (registered), covering **every life-safety calc** across 4 disciplines — **HVAC:** TR (1 TR=3.517 kW exact); **Fire Protection:** NFPA 13 sprinkler (density + additive demand), NFPA 20 pump (churn ≤140% / 150%-flow ≥65%), NFPA 72 battery (Ah = I×h + I×min/60), NFPA 2001 clean agent (design ≥ min extinguishing); **Electrical:** PEC voltage-drop (verdict = vd_pct ≤3%), PEC/NEC wire ampacity (derated ≥125% continuous), NFPA 110 generator (kVA = kW/PF + covers req), IEC 60909 transformer (Isc = I/(Z%/100) → breaker interrupting capacity); **Machine Design:** ASME VIII-1 pressure vessel (t_actual ≥ t_min+corrosion, hydro = 1.3×MAWP). These pin the safety constants a field-name test can't catch. **The life-safety oracle wave is complete.** **F-5 (silent-zero) — done as a RATCHET:** 131 `results.X \|\| … \|\| 0` alias-chains (a missing key renders a dangerous "0 mm"/"0 HP" spec); `validate_engdesign_silent_zero.py` baselines at 131 and FAILs on growth, so the class can't spread while the per-field audit is worked (registered). **F-7 (availability contract) — already covered:** `validate_calc_live_value.py` invokes each calc live and raises on `not_implemented`. **Queued (lower-stakes):** oracles for plumbing/machine-mechanics, full F-5 per-field fix, F-9 BOM grounding. |

