# BATTERY_LAYER3_MANIFEST.md — the whole Layer-3 UFAI battery we have

> Layer 3 = the **live, MCP-driven** grounded sweep (Playwright MCP in the real browser), as opposed to
> Layer 0 (`run_platform_checks.py`, static) and Layer 2 (the 1307-test headless Playwright suite). Layer 3
> ADDS only what L2 can't see live, per page/journey, grounded in numbers. This is the full inventory after
> closing all six BATTERY_INTELLIGENCE_GAPS (2026-06-08). Versions: `ufai_battery.js` **v1.6.1**,
> `journey_battery.js` **v0.2.0**, `companion_battery.js`, `analytics_correctness.js`,
> `tools/ia_semantic_critic.py`.
>
> **v1.6.1 (2026-06-08, L2-reinforcement walk):** clickAudit gained `click:not-keyboard-operable`
> (a `<div>`/`<span>` carrying its OWN onclick but no tabindex is mouse-only — WCAG 2.1.1; the
> name+dead-end checks MISS it when the div has text, e.g. clickable asset-cards). statesAudit
> `no-focus-style` now EXEMPTS native interactive elements (button/a/input/select/textarea carry a
> UA default focus ring — killed the `.filter-chip` false positive).

---

## 0. Install + boot (every page)
```js
// in Playwright MCP browser_evaluate, served from /workhive/ (relative):
const t = await (await fetch('ufai_battery.js')).text(); (0,eval)(t)(); await window.__UFAI.boot();
// CSS-390 mobile viewport: browser_resize(312,760) → innerWidth 390 at dpr 0.8
// RELOAD (not just delete __UFAI) after any synthetic DOM mutation OR battery-file edit.
```

## 1. `window.__UFAI` — the page-altitude interface battery (v1.6.0)

| Method | Subject | What it asserts (grounded) | Doctrine |
|---|---|---|---|
| `boot()` | — | injects axe-core + web-vitals; starts CWV capture at nav | setup |
| **`full({pageId,role,experience})`** | interface | **ONE-CALL entry point** → referee+form+click+states+component → `{totalMajor, byBucket, counts, majorDefects, cwv, coverage}` | the comprehensive-run driver |
| `run({pageId,role,experience})` | interface | REFEREE: U(axe contrast/tap/overflow/focus) F(wiring/links/console) A(CWV+reduced-motion) I(secrets/destructive/source-chips) C(garbage/range/loader/count-sum) | DEFECT→fix inline |
| `sweepAll()` | interface | clicks every tab/toggle, re-runs referee per state — multi-state coverage | DEFECT |
| `referee/usability/functionality/adaptability/internalControl/correctness` | interface | the individual pillars (run() composes them) | DEFECT |
| `correctness(spec)` `correctnessParity/Behavior/Invariants` | data | T0 invariants config-free; T2 behaviour + T3 oracle-parity via spec | DEFECT |
| **`formAudit()`** (Gap 2) | interface | per input/select/textarea: programmatic label (placeholder≠label), right input type, ≥16px font, autocomplete | DEFECT |
| **`clickAudit()`** (Gap 1) | interface | per clickable: accessible name, dead-end, **R-FP1 redundancy = (name × RESOLVED target), excluding per-list-item siblings** | DEFECT + critic |
| **`statesAudit()`** (Gap 4) | interface | per primitive family: active-state distinctness · :hover/:focus rule existence · disabled distinctness | DEFECT |
| `component(sel?)` (①) | interface | live per-primitive shape drift (.simple-card/.sum-card modal shape) | DEFECT |
| `inventory()` (IA Layer A) | data/IA | every `data-rag-tile` unit + untagged KPIs + affordances → `.tmp/ia_inventory/<page>.json` | feeds the surveyor |
| `critic` / `cwv` / `enumerateStates` / `_state` | — | critic candidates · core-web-vitals · state map · debug | critic / introspect |

## 2. `window.__JOURNEY` — the ③ journey-altitude battery (v0.2.0, `journey_battery.js`)
Install per page (idempotent), journals to `sessionStorage` across navigations.

| Method | Asserts |
|---|---|
| `reset()` | start a fresh journey |
| `step(label, {kpi: sel})` | read each KPI per page (number continuity) |
| **`act(label, fn)`** (Gap 3) | DO the job — fill/click — then snapshot; records errors (`journey-action-error`) |
| **`assertEqual(label, aSpec, bSpec)`** (Gap 3) | a control ↔ the data it drives agree; spec can be `{count: rowSel}` → `journey-action-inconsistency` |
| `verdict({tol})` | STATE continuity (identity constant) + NUMBER continuity + ACTION outcomes → defects |

## 3. `window.__CSB` — AI-behaviour subject-axis (`companion_battery.js`)
Grades **Agent · Memory · RAG · Safety** on grounded observables (gateway `model_chain`, `agent_memory` rows,
`cited[]` lanes, adversarial 0-leak). Drive on AI surfaces (assistant/voice-journal). Composes on top of `full()`.

## 4. `__ANALYTICS_PARITY` — data subject-axis (`analytics_correctness.js`)
`build(phase, oracle)` scrapes rendered analytics DOM, pairs with the orchestrator arrays → `parity[]` for
`__UFAI.run({parity})`. 33 per-tile checks across analytics' 4 phases.

## 5. Headless / Python companions (no browser)
| Tool | Role |
|---|---|
| `tools/ia_semantic_critic.py` (Gap 5) | LLM product-architect reasons over `ia_inventory_corpus.json` → TRANSFER/CONSOLIDATE/REMOVE/RELABEL, citation-validated |
| `tools/survey_ia_redundancy.py` + `score_ia_streamlining.py` | Layer-B cross-page redundancy map → 4-outcome rubric |
| `tools/survey_component_consistency.py` | static cross-page component drift |
| `tools/run_battery_family.py --gate` | ④ platform-altitude Mega-Gate G3 (forward-only ratchet) |
| `ufai_ingest.py` | route any critic candidate → `sweep_critiques.json` → disposition |

---

## 6. The comprehensive scenario protocol (Layer-3 full run)
For each `(page × role × state)` cell:
1. `browser_navigate` → page · install+boot · `browser_resize(312,760)` (CSS-390).
2. `await __UFAI.full({pageId, role, experience})` → record `totalMajor` + `byBucket` + `majorDefects`.
3. `__UFAI.sweepAll()` for multi-state; open modals manually; re-run on the deep states.
4. AI page → also drive `__CSB`; data page → also `__ANALYTICS_PARITY` + `__UFAI.run({parity})`.
5. Cross-page job → `__JOURNEY` (step/act/assertEqual/verdict).
6. DEFECT → fix inline; CRITIC → `ufai_ingest.py`. Log the cell.
**Auth:** supervisor `leandromarquez` / worker `bryangarcia`, hive `b0c61993`, pw `test1234` (native-setter
sign-in). If KPIs all read 0 + `JWT issued at future`/401 → re-sign-in (stale token, not no-data).
**Roles × states are the multiplier** that takes ~28 pages × ~6 battery methods × ~4 states × ~3 roles into the
thousands of grounded assertions = the "full scenario".

---

## 7. REINFORCE the L2 1300+ scenarios with L3 (the plan, 2026-06-08)
The Layer-2 Unified Mega Gate = **128 specs / 1323 test blocks**, of which **73 `journey-*` specs / 1121
blocks** are the scenarios. They assert **functional / data / isolation** truths. L3 reinforces them with the
**interface-DEPTH** the L2 specs don't run. The overlap is small and the gap is real:

| L2 journey already checks | L3 REINFORCES with (non-overlapping) |
|---|---|
| `journey-interaction-audit`: no unwired onclick / no dead links | `clickAudit`: accessible-NAME on every control + **R-FP1 redundancy** (name×target, list-aware). _Proven: dayplanner full() found 24 `click:no-accessible-name` on `<div>`s that "no unwired onclick" passes._ |
| `journey-mobile-a11y`: viewport · global focus-visible-alternative · toast aria · `text-sm`-on-input (iOS) · `<main>` · 44px CTAs | `formAudit`: programmatic **label[for]** + **input TYPE** + autocomplete (L2 misses the 16 unlabeled fields = W-form); `statesAudit`: **per-primitive** :focus rule + **selected-state distinctness** |
| `journey-dayplanner` etc.: add-task validation + happy-path DB · tab switch · `overdue counts OPEN-only` (DB-verified) | `assertEqual` (action-journey): **UI↔data consistency** — tapping "Overdue (2)" renders exactly 2 rows (L2 verifies the DB number; L3 verifies the rendered list matches it) |
| `journey-cross-surface-kpi-parity` / `*-fanout-parity`: same KPI agrees across pages (DB) | `__JOURNEY` number-continuity live + `ia_semantic_critic` (same-label-different-unit RELABEL the parity check can't reason about) |
| `journey-companion-*` / `journey-agentic-rag`: agent/RAG/memory functional | `__CSB` companion battery (Agent·Memory·RAG·Safety grounded observables) |
| `journey-analytics`: analytics functional | `__ANALYTICS_PARITY` 33 per-tile rendered==oracle |

### L3 COMPLETENESS rule — a SCAN affordance requires a GENERATE affordance (2026-06-08)
Deep MCP walk (operate the feature, don't just audit it) found logbook's "Scan equipment tag" had **no QR generator anywhere** — a faked half-loop. Closed it: `asset-qr.js` (`WHAssetQR.printTag/tagSvg/render`, lazy-loads qrcode-generator from jsdelivr) + a "Print QR tag" button on asset-hub asset detail, encoding the asset **tag** (the value the scanner matches on `asset.asset_id`). Round-trip VERIFIED: generate("M-001") → scan "M-001" → `selectAsset` → `asset_node_id` persists. **Standing L3 rule:** for any `scan/import/read X` affordance, assert a `generate/print/export X` counterpart exists (and the round-trip resolves A→A); a one-sided loop is a Major IA defect. Same walk found the platform-wide `v_asset_truth.id`→`asset_id` 400 in `utils.js` (every logbook entry was saving `asset_node_id=null`) — surface logic/data/FK bugs by VERIFYING the row, not the toast. See [[feedback-deep-mcp-walk-every-page]].

**Operationalize two ways:** (a) DURABLE — a headless `tests/journey-l3-interface-reinforcement.spec.ts` that
loads each page, installs the battery (it's plain JS, runs headless too), and asserts `full().totalMajor`
forward-only-ratchets → the L3 audits join the Mega Gate permanently; (b) LIVE — the MCP comprehensive run
(§6) walking the journey page-set with `full()` + `act/assertEqual`.

### Status — BOTH BUILT (2026-06-08)
**(a) DURABLE spec SHIPPED** — `tests/journey-l3-interface-reinforcement.spec.ts` auto-joins G2 (playwright
`testDir: './tests'`). Loads each page via the pre-authed `whPage` fixture at CSS-390, fetch+evals the battery,
asserts `full().totalMajor <= CEILING[page]` (forward-only). **5 pages pass headless (47.6s); teeth proven by
negative control** (drop pm-scheduler ceiling 1→0 → fails on the FAB major). Ceilings: dayplanner 0,
pm-scheduler **1** (the deferred FAB-occlusion — already in sweep_critiques.json; drop to 0 when it ships),
logbook 0, asset-hub 0, inventory 0. Extend by adding `{page: ceiling}` to the `CEILING` map.

**(b) LIVE walk done for the journey core (supervisor role):**
| Page | full().totalMajor | What L3 caught that L2 passed → action |
|---|---|---|
| dayplanner | 0 (was 24+168) | keyboard-dead `<div onclick>` hour slots (day **24** + week **168**) → +role/tabindex/keydown/`aria-label`/`.dp-slot:focus-visible`, both renderers; Enter opens modal (verified) |
| pm-scheduler | 1 | keyboard-dead `.asset-card` `<div onclick=openDetail>` (×10) → +role/tabindex/keydown/`aria-label`/`:focus-visible`; **assertEqual** tap-Overdue → 6 cards == KPI 6 (MATCH); remaining major = deferred FAB-occlusion |
| logbook | 0 | clean (8 fields, list+step-1 form labelled) |
| asset-hub | 0 | clean (30 cards use accessible controls); live-boot CWV is late-capture → unconfirmed, L2 perf owns it |
| inventory | 0 | clean (87 clickables, 81 list-items correctly R-FP1-excluded) |

**NEXT WINDOW:** extend the live walk to the rest of the journey set (hive, predictive, alert-hub, shift-brain,
analytics, community, marketplace, resume) and the **worker** role × empty-hive state (the parent-opacity /
empty-state traps surface only there); add each clean page to the durable `CEILING` map as it's verified.
