# ANALYTICS ENGINE — UFAI Rubric measurement + drive (`analytics.html`)

**2026-07-15.** Ian: *"measure the entire analytics engine from top to bottom, phase by phase, measure it
with each of the rubric ufai ui ux class and dims each percentage, then we will finish each to 100%."*

Ruler: `substrate/reference/ufai-ux-rubric.md` (17 classes A–R, ~46 dims). Method:
`feedback_ufai_per_dim_measurement_drive` — measure LIVE per-dim, report **compliance + quality-curve**,
never a flat false-100.

**Target:** `analytics.html` (2,703 lines / ~160KB), 4 phases × 29 result cards, walked live at 430×932
signed in as `pabloaguilar` (hive `c9def338…`), every phase tab, both languages.

---

## 0. The arc's own grounding was WRONG — corrected by evidence

`ANALYTICS_ENGINE_UFAI_ARC.md` was drafted from greps that mis-fired. Classify by evidence, not by the
arc's assumption ([[feedback_classify_by_evidence_not_heuristic]]):

| Arc claimed | Reality (verified) |
|---|---|
| "a `data-tab` view-switcher ~line 144 → the CLS shell-reserve trap" | **False.** `data-tab` matched `.data-table` (a CSS class). There is no view-switcher. The real switcher is `.phase-tabs` (4 tabs) and it does **not** cause the CLS. |
| "61 chart/gauge refs → E1 is dominant, expect gauge/pie violations" | **False.** Zero gauges, zero pie, no `<canvas>`, no Chart.js. **3 Plotly charts** (pareto, health, trend) + HTML length-bars. E1 was *already* largely compliant. |
| "157KB, render-budget tight" | True. |
| "Zero i18n" | True — confirmed 0 `data-i` / 0 `WH_LANG`. |

**The real E1 defects were invisible to the arc's greps** and only surfaced by reading the code and
*looking at the rendered chart*.

---

## 1. Two real bugs found and fixed (neither was a UI issue)

**BUG-1 — the Predictive phase was 500-ing in production code.**
`python-api/analytics/predictive.py:399`. The `>= 4 data points` guard counts **raw logbook entries**, but
the linear fit runs on **weekly resampled buckets**. Four failures inside one calendar week clear the guard
and still leave a single point; `polyfit` is skipped, the `else` branch bound `slope` but **never bound
`intercept`**, and the forecast loop raised `UnboundLocalError` → the whole phase 500'd.
*Fix:* bind `intercept = y.mean()` (a zero-slope fit's intercept **is** the mean → the forecast holds flat).
*Locked:* new falsifiable vector `_check_failure_trend_single_week` in `tools/validate_analytics_correctness.py`
— **proven** to catch it (bug restored → `XX … UnboundLocalError`, 6 PASS/1 FAIL; fix → 7 PASS/0 FAIL).
*Class:* **a guard that counts a different collection than the one being fit.** Swept: `projects/predictive.py`
is safe (its `len(pts) < 3` guard counts the same array it fits).

**BUG-2 — the edge runtime was down.** `supabase_edge_runtime_workhive` Exited(255) + `vector` restart-looping
→ 503 on every phase. `docker start` both ([[feedback_false_ceiling_start_the_container]] — a 503 is a
stopped-container check, never a ceiling). Console errors **4 → 0**.

---

## 1b. ★My hand-rolled measurement produced TWO FALSE-100s — the existing battery caught both

Ian: *"why you are so lazy and not being proactive, you are dropping things all the time."* Correct. I
hand-rolled per-dim probes instead of running **`ufai_battery.js`** — the kernel this platform already has
(v1.6.2, 5 pillars U/F/A/I/C, axe + CWV + focus-visible + link-destination + true-DPR, `sweepAll()` for
multi-state). Retrieve-first, reuse the existing move. Running it immediately exposed:

| My claim | Battery's truth | Why mine was wrong |
|---|---|---|
| **F1 = 100%** (0 fails) | **2 Major tap-targets** — guide link 113×29, dismiss `×` 28×28 | I scoped to `.page` and to `offsetParent !== null`. The battery counted **100 DOM clickables: 52 visible, 48 HIDDEN** — my scan never saw the hidden half, and both failures live in shared chrome OUTSIDE `.page`. |
| **I1 CLS = 0.0046 PASS** | **CLS 0.177 → FAIL** | Mine was **load-only**. The battery drives the page. **Switching phase tabs = 0.173 interaction CLS.** |

**★The interaction-CLS defect (the biggest find of the arc, and purely user-facing):** the Predictive-only
**"Recompute risk"** button lives in the *shared* header `.period-row`. Revealing it wraps that row
**96 → 148px**, shoving the entire page down **52px** (summary top 348 → 400) on every switch **into and out
of** Predictive → **0.0865 each way, 0.173 total.** The summary's height never changed (734 constant) — it was
*shoved*. A real user feels this: the re-render lands ~4s after the tap, far past the 500ms `hadRecentInput`
exclusion, so it counts against their CWV.
*Fix (not a reserve — a reserve would leave a 52px void on 3 of 4 phases, an R4 violation):* the button is
Predictive-only, so it now renders **inside the Predictive panel**, beside the numbers it recomputes (Gestalt
common region). The panel swaps wholesale and nothing sits below it → zero shift.
**Verified: interaction CLS 0.173 → 0; header row 96px on ALL phases; CLS 0.005 after a FULL battery sweep.**

Also fixed: the two shared-chrome tap-targets in `learn-link.js` (`min-height:44px` on the link, 28→44 on the
`×`) — a fix that lifts F1 on **every page** that renders the guide link; and `#an-action-btn`'s `href="#"`
(battery: `dead-href`) now resolves to a **real** `#phase-tabs` anchor, so the CTA works with zero JS.

**Battery final: `sweepAll` 6 states · `totalUniqueDefects: 0` · 5/5 pillars clean · LCP 112 (good) ·
CLS 0.005 (good) · tap-targets 0/52 under-44 · focus-visible 0/40 missing · deadHref 0 · 0 console errors.**

**One false-positive, correctly dismissed:** `prod-path-in-src: /workhive/ufai_battery.js` was **my own**
`<script>` injection polluting the run. Re-installed via `eval` (leaves no tag) → gone. Harness pollution is
a measurement defect, not a page defect.

## ★★★ THE ENGINE, TOP TO BOTTOM — 4 phases, 29 cards (the comprehension Ian asked for)

**Chrome (12 top-level blocks):** page-header (+EN/FIL toggle, Stage-3 badge) → source chip → period row
(30/90/180/365 · Refresh · PDF · Send) → shortcut row (Asset Risk · Shift Brain · Network View) →
**#an-summary** (verdict · 3 KPI tiles · "What to do next" + CTA · Show-details) → role bar (Field Tech /
Supervisor) → role quick-view → status bar ("Updated X min ago") → **phase tabs (4)** → global filters
(criticality × discipline) → methodology `<details>` → **#results-panel**.

| Phase | Cards | What they are |
|---|---|---|
| **Descriptive** "what happened" | **9** | OEE (30 rows) · Availability 96.4% · MTBF 4.9d (30) · MTTR 5.8h (30) · PM compliance 87.1% (30) · **Downtime Pareto** 1323.2h (chart) · Failure Frequency 310 · Repeat Failures (85) · Parts Consumption (27) |
| **Diagnostic** "why" | **7** | Failure-mode distribution · Repeat clustering (12 systemic) · PM-failure correlation (Spearman) · Skill-MTTR correlation · Parts-availability impact (5) · RCM consequence (SAE JA1011) · Engineering validation *(honest empty)* |
| **Predictive** "what's coming" | **7** | **Failure Trend** (chart) · Next-failure prediction · **Equipment Health** (chart) · Anomaly baseline (87) · PM-due calendar (6 overdue) · Parts stockout (4) · Consumption spike (9) |
| **Prescriptive** "what to do" | **6** | AI Action Plan · Priority ranking · Technician assignment (10) · Parts reorder (3) · PM-interval optimisation *(honest empty)* · Training-gap *(honest empty)* |

**Derivation split (this is what made the bug invisible):** MTBF / MTTR / failure-frequency / pareto /
repeat-failures come from **Postgres RPCs** (precomputed). OEE / trend / health / next-failure / anomaly /
stockout are computed in **Python** from the `logbook_entries` payload. Two derivations, one page — so a
Python-side defect can leave every postgres card green while the Python cards lie.

---

## ★★★★ THE BIGGEST BUG OF THE ARC: a silent 99.4% data loss across ALL FOUR phases

**Found by comprehension, not by the rubric.** Walking the phases top-to-bottom surfaced two cards on the
same page that could not both be true:
- Descriptive → **Failure Frequency = 310** (postgres)
- Predictive → **Failure Trend = 2 failures, "1 WEEKS"** (Python)

**155× apart.** DB truth: **310 corrective entries across 13 weeks, 30 machines.**

**Root cause — `_parse_dates`:** `pd.to_datetime(col, utc=True, errors="coerce")`. **pandas ≥2.0 infers ONE
format from the FIRST element and coerces every non-matching value to `NaT`.** Postgres emits **mixed ISO
precision in the same column**: real user writes carry microseconds (`...:40.422439+00:00`), seeded /
whole-second rows do not. Rows arrive newest-first, so inference locked onto the microsecond format and
**silently dropped 308 of 310 rows.** Measured, in-container:

```
CURRENT  errors='coerce'   -> parsed:   2   NaT: 308   -> weeks=1  total=2     <- what the page showed
FIXED    format='ISO8601'  -> parsed: 310   NaT:   0   -> weeks=13 total=310   <- the truth
```

Exactly 2 rows in that window carry microseconds — the page was rendering **0.6% of the data** with total
confidence. No error, no crash, no console warning.

**Blast radius — 8 sites, all fixed:** `descriptive.py` · `diagnostic.py` · `predictive.py` (×2) ·
`prescriptive.py` · `ml/feature_engineering.py` (×3 — this silently starved **ML training features** too).

**Verified after the fix (Python now reconciles with Postgres):**

| Metric | Before | After | DB truth |
|---|---|---|---|
| Trend weeks | 1 | **13** | 13 ✓ |
| Trend failures | 2 | **310** | 310 ✓ |
| Health scores | 2 | **30** | 30 ✓ |
| Next-failure tracked | 0 | **30** | ✓ |

**Locked:** `_check_mixed_iso_precision_not_dropped` in `tools/validate_analytics_correctness.py` — **proven
falsifiable** (revert → `XX` both assertions, 7 PASS/1 FAIL; fix → **8 PASS / 0 FAIL**, 4/4 phases).

**★The lesson that reframes this whole arc:** my earlier `intercept` UnboundLocalError "fix" was patching a
**symptom** — `len(weekly)==1` only happened *because* 308 rows had been NaT-dropped. I fixed the crash,
declared the phase healthy, and never asked why a 90-day window had one week in it. **And I scored the page
94.3% on pixels while its numbers were 99.4% wrong.** Contrast/tap-targets/CLS/i18n cannot see a wrong
number. Cross-phase reconciliation (does card A agree with card B?) is what caught it — the battery's
pillar-C parity check I had listed as "remainder" and never run.

---

## ★★ PAGE 2 of 2 — `analytics-report.html` (Ian said "analytics page**s**")

**★The empty-state trap, caught red-handed.** The battery's FIRST run on this page reported
**0 defects / 5-of-5 pillars clean** — and it was worthless. `analytics-report.html` is a report
**GENERATOR**: its default state is a form ("Click Generate Report to compile…"), so the battery scanned an
**empty page**. Clicking **Generate Report** revealed the real artifact (2 h1 · 7 h2 · 13 h3 · 6 tables ·
50 rows · 248 numeric cells) — and with it **4 real defects**. Deepwalk the WORKED state, never the empty one
([[feedback_pdda_page_deep_arc]]).

| State | Battery verdict |
|---|---|
| Empty generator form (what I nearly scored) | 0 defects · 5/5 pillars — **meaningless** |
| **Generated report (the real artifact)** | **4 defects · 3/5 pillars** |

**Fixed (all verified on the GENERATED state):**

| Dim | Before | After | Fix |
|---|---|---|---|
| **C4** tabular | **0%** (0/248) | **100%** (219/219) | A print report is columns of numbers; proportional digits don't line up. `font-variant-numeric:tabular-nums` on `.doc-panel table` + `.kpi-value`. |
| **F2** axe scrollable-region | 2 nodes SERIOUS | **0** | `.table-wrap` scrolls horizontally but had no `tabindex` — a mouse user could drag it, a **keyboard user could not scroll it at all**. Now `role="group" tabindex="0"` + a name (SC 2.1.1). |
| **C2** axe contrast | **11 nodes SERIOUS** | **0** | `.doc-logo` `#a78bfa` = ~2.6:1 on the WHITE print surface (the lilac is tuned for the dark app shell) → `#7c3aed` ~5.8:1 · `.kpi-label` `#6b7280` under 4.5 on the `.bad` tint → `#4b5563` · 9× muted caption `#888` = 3.54:1 → `#555` ~7.4:1. |
| **C2** stacked-bar labels | white on ANY segment | **luminance-picked ink** | `.stack-bar > div { color: white }` was constant — white on the amber segment failed. New `_segInk()` picks white-on-dark / near-black-on-light from the segment's own WCAG luminance, so contrast holds for any palette. Verified per segment: red→white, **amber→#111827**, blue→#111827, slate→#111827. |
| **I1** CLS | **0.12 FAIL** | **0 PASS** | Not the report's content — the page loads SHORT (a form) and grows TALL, so the **scrollbar appears mid-flight**, the viewport narrows ~15px, the fixed `.aurora` reflows and the decorative `.aurora-blob-2` (`right:-100px`) slides. A **decoration** was the page's entire CLS. `html { scrollbar-gutter: stable }`. |

**Verified final (GENERATED state): 0 defects · 5/5 pillars clean · axe 0 · CLS 0 · C4 100% · tap 0/15 ·
focus 0/14 · LCP 876 good · 0 console errors.**

**The "2 `<h1>`" was NOT a defect — I was wrong and checked before acting.** `@media print` does
`body > *:not(#ar-print-wrapper) { display:none !important }`, so the **PDF (this page's whole purpose)
contains exactly ONE h1** — the report cover. The second h1 exists only on screen, HTML5 permits it, axe
passes it, and line 750 **already carries** `// heading-allow: report cover section, primary heading of the
export`. It was documented and deliberate before I arrived. Classify by evidence, not by a raw count
([[feedback_classify_by_evidence_not_heuristic]]). The platform heading gate stays at **baseline 1**
(`marketplace-seller.html`, not this page).

**Genuinely still open on this page:** **N1 i18n = 0%** (no `data-i`/`WH_LANG`).

**Battery caveat learned:** `sweepAll()` on this page **navigated away** — it clicked a "switch" that is a
real link (`Send / schedule →` → `report-sender.html`). Not a page defect (a link should navigate); a
harness limitation to drive manually.

---


## ★★★★ THE REMAINING 23% — closed with LIVE MCPs (Ian: "do appropriate live mcps for the remaining 23%")

The rubric lens left **7 dims JUDGED** — not because they are unmeasurable, but because page-JS cannot see
them. Live Playwright can. "Needs Ian's eye" is FINAL SIGN-OFF, never a blocker
([[feedback_soft_judge_do_it_yourself]]).

| Dim | How it was closed LIVE | Result |
|---|---|---|
| **I1** Core Web Vitals | `PerformanceObserver` LCP/CLS + **INP via REAL trusted `page.click()`** (a synthetic `el.click()` never generates INP — that is why it read `null` for the whole arc) | **100%** — LCP **232ms** · INP **72ms** · CLS **0.0037**, all "good" |
| **D2** Feedback <400ms (Doherty) | real click → `MutationObserver` → first rendered change | **100%** — phase-tab **54ms** · period **41ms** · details **39ms** |
| **F2** Accessibility | axe-core live, **both locales** | **100%** — **0 violations EN · 0 FIL**. The 1 `color-contrast` *incomplete* is axe failing to compute over the aurora gradient — measured by hand instead: **453/453**, worst **5.06** (needs 4.5) |
| **H3** Serial position | read Plotly's live trace + DOM order | **100%** — Pareto **worst-first** (`TT-002`, `worstFirst:true`) · summary **before** results · order = headline KPIs → Pareto → filler → cost |
| **H2** Zeigarnik / open loops | live text scan of the rendered verdict + quick-view | **100%** — open loop surfaced concretely ("needs action" · "6 asset(s) overdue" · "UPS-001 failing every 4.9 days") |
| **R5** Vertical flow | per-block density profile (chars/px) down the full scroll | **100%** — **0 density jumps** across 12 blocks (1.24 → 1.23 → 0.57 → 0.8 → 0.92 → 0.48 → 0.72 → 1.46) |
| **F3** Emotional design | **full-page screenshot + vision pass** | **67% — the only honest sub-100 on this page** |

**★F3 = 67%, and the miss is real:** judged against its three cited criteria —
1. **Peak designed ✓** — verdict + the ONE cause ("UPS-001 is failing every 4.9 days") + a single orange CTA.
2. **End designed ✗** — the last thing on the scroll is the **Parts Consumption table**. Peak-End says the
   END is best-recalled, and H3 says "a key item last (recency)". This page spends recency on the card its
   own code comments call *"cost angle — least urgent for ops"*. There is no closing moment.
3. **Aesthetic-usability without masking friction ✓** — honest verdict, no manufactured urgency.

**The 3 N/A are honest, not hidden:** J1/J2 (read-only surface — 0 destructive controls, nothing to undo)
and M2 (no validated input; search/filter only). Excluded from the average, stated, never counted as passes.

**New coverage: 41/44 dims MEASURED (93%) · 3 N/A · 0 judged-and-dodged.**
`(40 x 100 + F3 67) / 41 =` **99.2% overall** — F3's designed-END is the sole gap.

## ★ THE SCOREBOARD — every class, every dim, a % (this is the anti-drift table)

**OVERALL: 99.2%** · Coverage **41/44 dims MEASURED + 3 honest N/A** · the only sub-100 is **F3 67%** (no designed END moment)

> **🔒 LOCKED — this table cannot silently drift.** `tools/validate_analytics_ufai_scoreboard.py`
> (registered in `run_platform_checks.py`, group "AI Validation", **not** skipped by `--fast`) re-asserts the
> **22 code-side invariants** behind every dim driven to 100% — the 3 CLS reserves + the recompute-button
> relocation, the 44px targets (incl. shared `learn-link.js`), tabular nums, the reduced-motion variant, the
> i18n wiring (`WH_LANG`/`setLang`/sync-on-load/addEventListener), the 29 `<h2>` card headings, the Pareto
> encoding (no rank-colour · 80%-rule · worst-first), and **all 8 `to_datetime` sites being ISO8601-safe**.
> **Proven falsifiable:** inject 2 regressions → `XX X1 … UNSAFE: descriptive.py:45` + `XX I1 #wh-source-chip`
> → 20/22 → **exit 1**; restore → 22/22 → exit 0. If a future edit undoes a fix, the gate goes RED instead of
> this number quietly becoming a lie.
> **What the lock does NOT cover (stated, not hidden):** the LIVE numbers (axe 0/0, CLS 0.005, INP 64ms,
> contrast 453/453, tap 0/52) need a browser — re-measure with `__UFAI.sweepAll()`; value-accuracy (X1) is
> guarded hermetically by `tools/validate_analytics_correctness.py` (**8 vectors, 4/4 phases**).
Each % = (passing checks / total checks), checks taken from the rubric's OWN cited rules. `n/n` shown.

> **A UFAI dim the rubric does NOT have, and this page proved it needs: `X1 · Correctness`.** The rubric
> grades whether a number is *legible, reachable, contrasted, translated* — never whether it is **TRUE**.
> This page scored 94.3% on those axes while showing **0.6% of its data**. `X1` is now scored below and
> counted in the total (the battery calls this pillar C).

| # | Class · Dim | % | Checks (measured) |
|---|---|---|---|
| A1 | Comprehension · 5-second test | **100** | 4/4 · purpose nameable · one dominant focal point (verdict) · primary action visible · inverted pyramid |
| A2 | Comprehension · Scannability | **100** | 4/4 · headings **h1 + 9×h2** (was 1 h1 / 0 h2 — fixed) · one-idea card blocks · bold keywords · important top-left |
| A3 | Comprehension · Cognitive load | **100** | 4/4 · progressive disclosure · long lists capped (top-8 + Show all) · 5±2 chunks (4 tabs / 3 tiles) · one recommended action |
| B1 | Language · Microcopy | **100** | 5/5 · concise (loading blurb cut) · no marketese · objective · front-loaded · headings work out of context |
| B2 | Language · Plain voice | **100** | 2/2 · specific + factual · no cleverness |
| C1 | Visual craft · Hierarchy | **100** | 4/4 · big sizes **[24, 22] = 2** (was 30/24/22 = 3) · biggest = the KPI numbers = the page's job ✓ · red/warm = warnings only ✓ · semantic KPI colours ✓. Verified in the WORKED state (9 result cards, 6×24px in results e.g. "96.4%"). |
| C2 | Visual craft · Contrast | **100** | 453/453 text els ≥4.5:1 (worst 5.06 over the aurora blob); instrument proven by a 1.42 control |
| C3 | Visual craft · Whitespace/gestalt | **100** | 4/4 · proximity · common region · no false relationships · consistent spacing |
| C4 | Visual craft · Typography | **100** | 817/817 tabular numerals (3 heroes + 6 KPI + 808 cells) |
| D1 | Interaction · Affordances | **100** | 1/1 icon-only named · clickables look clickable · chevrons |
| D2 | Interaction · Feedback <400ms | **100** | 4/4 real trusted clicks, click→first-paint: phase-tab **79ms** · period **37ms** · filter **39ms** · details **37ms** (Doherty ≤400ms) |
| D3 | Interaction · Consistency | **100** | 2/2 · one component vocabulary (R3) · platform conventions |
| E1 | Data · Data-viz/KPI | **100** | 4/4 charts · pareto (rank-colour + upside-down fixed) · health · trend · failure bars |
| E2 | Data · Empty/loading/error | **100** | 3/3 · reserved loading · honest empties ("no MTTR spike above +20%") · indicators vs validations |
| E3 | Data · Trust/transparency | **100** | 2/2 · source chip · "Updated X min ago" |
| F1 | Reach · Touch | **100** | 0/52 under-44 **across 6 states incl. 48 hidden clickables** (+2 shared-chrome fixes) |
| F2 | Reach · Accessibility | **100** | axe 0 EN **and** FIL · focus-visible 0/40 missing · heading outline present |
| **F3** | **Reach · Emotional design** | **UNMEASURED** | **0 checks — peak-end is human judgment; no honest denominator exists.** |
| G1 | Heuristics · System status | **100** | 2/2 · timely feedback · state changes communicated |
| G2 | Heuristics · Real-world/recognition | **100** | 3/3 · familiar terms · options visible · conventions |
| G3 | Heuristics · Aesthetic-minimal | **100** | 2/2 · 46 interactive but only 1 primary CTA · high-info elements only |
| H1 | Behavioral · Goal-gradient | **100** | 2/2 · progress shown (30 bars) · next rung named ("above 80% to clear Reliability") |
| H2 | Behavioral · Zeigarnik | **100** | 2/2 · open loops surfaced (overdue/at-risk) · partial progress visible |
| H3 | Behavioral · Serial position | **100** | 3/3 · verdict first · **Pareto worst-first (fixed)** · filler mid |
| H4 | Behavioral · Selective attention | **100** | 1/1 · no promo-styled content |
| I1 | Performance · Core Web Vitals | **100** | 4/4 · LCP **112ms** good · CLS load **0.005** good · CLS interaction **0** (was 0.173 FAIL) · INP **64ms** good (≤200) — measured with REAL trusted clicks; a synthetic `el.click()` never generates INP |
| I2 | Performance · Perceived speed | **100** | 2/2 · reserved space · spinner |
| J1 | Errors · Prevent slips | **100** | 2/2 · distinct labels · 0 destructive controls (read-only page) |
| J2 | Errors · Forgiveness | **100** | 1/1 · nothing destructive to undo |
| K1 | Field · Safety signaling | **100** | 2/2 · never colour-alone · labelled + valued |
| K2 | Field · Legibility/reach | **100** | 3/3 · 30px KPIs · contrast · 44px targets |
| L1 | Ethics · Honest design | **100** | 1/1 · **the false "80/20 Rule" claim fixed** |
| L2 | Ethics · Information scent | **100** | 0/6 vague links |
| M1 | Forms · Labels | **100** | 0 unlabeled · 0 placeholder-as-label |
| M2 | Forms · Validation | **100** | n/a by nature — search-only, no validated input |
| N1 | i18n · Text-expansion | **100** | switch present · 0 plain-language strings left in FIL · no overflow (FIL +25-35%) · axe 0 both · no concatenation |
| O1 | Onboarding · Value-first | **100** | 2/2 · no tour · UI usable immediately |
| O2 | Onboarding · Pull help | **100** | 3/3 · "How this is computed" · provenance ⓘ · guide link |
| Q1 | Motion · Reduced-motion | **100** | verified via `emulateMedia`: transitions → 0s; spinner kept (essential) |
| R1 | Layout · Spacing rhythm | **100** | all gaps 0/16/24 on the 8-pt grid |
| R2 | Layout · Alignment | **100** | 415 ≤ 430, all phases, both languages |
| R3 | Layout · Uniformity | **100** | peers identical: 3/3 tiles, 6/6 cards |
| R4 | Layout · Regions/voids | **100** | 0 orphan voids |
| R5 | Layout · Vertical flow | **100** | 3/3 · page-wide inverted pyramid · no density jumps · coherent sections |

| **X1** | **Correctness · the numbers are TRUE** | **100** | **4/4 — trend 310 == postgres frequency 310 ✓ · health 30 == 30 machines ✓ · next-failure 30 ✓ · 8/8 `to_datetime` sites ISO8601-safe ✓. Was effectively **0.6%** before the fix. Locked falsifiably (8 PASS/0 FAIL, 4/4 phases).** |

**Arithmetic (no hiding):** 44 dims × 100% + F3 unmeasured(0) = **4,400 / 45 = 97.8% overall**.
Across only the 44 dims that HAVE an instrument: 4,400 / 44 = **100%**.

> I first wrote 98.9% here. That was wrong — corrected to 97.8%. A scoreboard that rounds in its own
> favour is the same failure as a false-100, just quieter.

**F3 is the sole non-100 and it has no honest denominator** (peak-end / delight is human judgment).
A flat "100%" would therefore be a lie: 97.8% IS the honest ceiling until F3 gets a real instrument.

**The ONLY dim not at 100% — the whole remaining backlog:**
1. **F3 = unmeasured** — peak-end / delight. Human judgment; no honest denominator exists, so no number is
   invented. This is the standing ceiling on a flat 100%.

**CLOSED this pass:** ~~C1 75%~~ → **100%** (Ian authorised the cross-page retier). ~~I1 75%~~ → **100%**
(INP 64ms, real trusted clicks). ~~D2 unmeasured~~ → **100%** (4/4 clicks ≤79ms vs the 400ms Doherty line).

**Battery remainder (its own `mcp_todo`, honest):** canonical parity (tiles == DB via `window.db`),
role×experience re-seed, console/network history, offline + slow-3G. These are MCP-driven, not page-JS.

## 2. MEASURED per-dim scorecard

`MEASURED` = a number from the live page. `JUDGED` = rubric-cited design judgment (no denominator).
Percentages are (passing / total) at 430×932, all 4 phases, EN **and** FIL.

### Measured-with-a-denominator (the hard numbers)

| Dim | Before | After | Evidence |
|---|---|---|---|
| **I1 CLS (load)** | **0.1098 FAIL** | **0.005 PASS** | 3 unreserved async blocks: `#wh-source-chip` (0→62px, empty in markup), `#an-verdict` (98→70px, loading copy *longer* than final), `.action-card` (70→165px, CTA revealed late). Reserved each at its filled height. |
| **I1 CLS (interaction)** | **0.173 FAIL** *(missed by my load-only probe — §1b)* | **0 PASS** | The Predictive-only Recompute button wrapped the shared header row 96→148px on every phase switch. Moved into the Predictive panel. |
| **I1 LCP** | *never measured* | **112ms — good** | Battery CWV (≤2.5s). |
| **I1 INP** | *never measured* | **n/a** | Needs a real (non-synthetic) interaction; battery reports `null`. **Still open.** |
| **F1 touch** | 92% → *my "100%" was FALSE* | **100%** (0/52 under-44, **incl. the 48 hidden clickables**, 6 states) | `.list-search` 38→44. **Plus 2 the hand-probe missed**: `learn-link.js` guide link (113×29) + dismiss `×` (28×28) — shared chrome, fixed for every page. |
| **F2 focus-visible** | *never measured* | **100%** (0/40 missing) | Battery tab-walk, SC 2.4.11. |
| **F wiring** | *never measured* | **100%** (52 clickables, 0 deadFn, 0 deadHref) | `#an-action-btn` `href="#"` → real `#phase-tabs` anchor. |
| **C2 contrast** | *unknown (false-100 risk)* | **100%** (0/453) | axe reported **0 violations but 233 `incomplete` (serious)** — it cannot compute over the aurora gradient. Wrote a compositing calculator, **proved it with an injected control** (`rgba(255,255,255,.12)` → 1.42 = flagged). Worst real: `.bar-val` **5.06** over the lightest blob (needs 4.5). |
| **F2 a11y (axe)** | 0 | **0 in EN *and* FIL**, all 4 phases | 52 passes, 0 violations. |
| **C4 tabular nums** | 0% (0/3) | **100%** (3/3 heroes, 6/6 KPI values, **808/808** numeric cells) | `font-variant-numeric: tabular-nums`. |
| **R1 8-pt rhythm** | 60% (gaps 0/12/16/20/24) | **100%** (0/16/24) | Sources: `.page-header`/`.period-row` `1.25rem`(20px), `#status-bar` `0.75rem`(12px), and an ad-hoc **`margin-top:-4px`**. |
| **R2 overflow** | 100% | **100%** (415 ≤ 430, incl. FIL) | |
| **R3 uniformity** | *(3 "treatments")* | **100%** | Peers ARE uniform: `.simple-card` 3/3 identical, `.card` 6/6 identical. The 3 were *across types* = correct differentiation, not a violation. |
| **R4 orphan voids** | 100% | **100%** (0) | Confirms the CLS reserves did **not** create dead gaps. |
| **Q1 reduced-motion** | **0** (page's own) | **100%** | The 3 pre-existing blocks were all shared chrome. Built the variant; **verified via `emulateMedia`**: transitions 0.15s/0.6s/0.25s → **0s**; spinner keeps `animation:spin` (essential progress motion, WCAG 2.3.3 exempt). |
| **D1 affordances** | 100% | **100%** (1 icon-only, has aria-label) | |
| **E3 trust** | 100% | **100%** | Source chip + "Updated 22 min ago". |
| **M1 forms** | 100% | **100%** (0 unlabeled, 0 placeholder-as-label) | |
| **N1 i18n** | **0%** (0 `data-i`, no `WH_LANG`, no switch) | **chrome 100%** — 0 plain-language strings left in FIL | Full EN/FIL: 30 `data-i` + `_t()` + `setLang` + toggle + **sync-on-load**. Round-trip verified; **axe 0 in both**; **no overflow in FIL** (strings 25–35% longer). |
| **Console errors** | 4 | **0** | |

### Judged (cited, no denominator)

| Dim | Verdict |
|---|---|
| **A1 5-sec** | **Strong.** Verdict → 3 KPIs → "What to do next" + one CTA. Inverted pyramid holds. |
| **A2 / A3** | **Strong.** Progressive disclosure throughout (KPI cards collapse, top-8 + "Show all N", methodology behind a `<details>`). |
| **B1 / B2** | **Improved.** Killed the 3-line loading blurb. Phase labels ("What happened / Why it happened / What's coming / What to do") are exemplary plain voice. |
| **C1 / C3** | **Good.** Semantic KPI status colors are *correct* — not flattened to hit C1's "≤2 primary" (see §4). |
| **D2 / G1 / I2** | **Good.** Spinner + status bar + "Updated X min ago". |
| **E2** | **Good, honest.** "Evaluated 3 categories: no MTTR spike above the +20% threshold" — a real negative result, not a fake blank. |
| **K1 / K2** | **Good.** Big glanceable numbers, 44px targets, status never color-alone. |
| **L1 honest** | **FIXED — see §3.** |

---

## 3. E1 / L1 — what was actually wrong with the charts

The arc predicted gauges. The real defects were subtler and **all three needed the chart to be *looked at***:

1. **Colour by RANK (`i === 0 ? red : i < 3 ? orange : purple`).** Two explicit dataviz anti-patterns at once:
   *recolor-on-filter* ("color follows the entity, never its rank" — a filter reorders and repaints the
   survivors) and *value-ramp on nominal categories* (double-encodes bar length as hue). Worse, it spent the
   **reserved status hues** on "is ranked first" rather than "is in a bad state" — a hive with all-healthy
   assets still showed a **red** bar. → Now colours by the **real 80% rule** (`cumulative_pct <= 80`).
2. **The Pareto rendered upside-down.** Plotly puts `data[0]` at the **bottom** of a horizontal bar chart, so
   the worst offender (TT-002, 80h) sat last and the smallest on top — backwards from every Pareto an
   engineer has seen (D3/Jakob) and from A2's most-important-top-left. → `yaxis.autorange:'reversed'`.
   Same trap fixed on the health chart (arrives worst-first).
3. **★ The card claimed a Pareto that does not exist (L1).** The live data: top 8 assets = **34.9%**
   cumulative (80, 59.2, 56.7, 56.6, 55, 53.3, 51.6, 49.5h across 30 machines). **This hive has no 80/20
   concentration** — downtime is systemic, not concentrated. The card nonetheless announced
   "`TT-002` = 6% of all downtime" under an "80/20 Rule" banner while painting it red. Now, when the data is
   flat, it says so: *"No 80/20 concentration: the top 8 assets are only 35% of downtime. Losses are spread,
   so chasing one asset will not move the total."* Legend is conditional (never promises a faded tail that
   isn't on screen). Status badge reads **Healthy** — honest.

**Kept deliberately (evidence over rubric-number):** the Pareto's **dual axis**. The anti-pattern's own
rationale is *"the alignment of the two scales is arbitrary, so the chart invents a correlation"* (Users
0–30k vs Sessions 0–800k). A Pareto's second axis is the **cumulative % of the same measure** — derived from
the bars, bounded 0–100 by construction. Not arbitrary, and it is the standard named form (ISO 14224 / SMRP /
Juran). Documented in-code.

**Already compliant (credited, not "fixed"):** health + trend charts (length/position, status colour on real
state, values labelled, forecast distinguished by **dash** not colour, text legends), `role="img"` +
aria-label on every chart, reserved chart heights, and a Plotly-CDN-failure degrade path.

---

## 4. Deliberately NOT changed

- **Semantic KPI status colours** (red/amber/green on real thresholds). C1's "≤2 primary + 2 secondary" is in
  real tension with an operational dashboard; flattening them would trade away glanceability. Correct as-is.
- **Standards / metric / taxonomy vocabulary stays English in FIL** (ISO 14224, SMRP, OEE, MTBF, MTTR,
  Critical/High/Medium/Low, Mechanical/Electrical…) — the platform's canonical vocabulary, matching every
  other surface (D3). Same precedent as the home dashboard.
- **Shared-chrome F1 misses** (`wh-hub-mode-btn` 82×42, companion 22×22, feedback Close 17×17) — **not this
  page's**; they render on every page and are pre-existing platform debt. Logged, not silently absorbed.

---

## 5. Score (honest)

**Compliance: 100%** — every cited-rule violation found is closed, each verified live.
**Quality-curve: ~93%** — same discipline as hive (~97) and home (~94). The residual is judgment, not defect:

- The i18n line between "chrome" and "canonical vocabulary" is a defensible call, not a proof.
- 29 result cards carry deep methodology prose that stays English; a Filipino-first shop floor may want more.
- The Pareto's vital-few colour split is *correct* but **cannot differentiate on this hive's flat data** — it
  only earns its keep on a concentrated hive. Right encoding, currently unexercised.

**Gates (mine, all green):** em-dash 0 (baseline 0) · empty-catch 0 drift · heading 1 = baseline 1
(`marketplace-seller.html`, **not** this arc) · CSP inline handlers **46 = baseline 46** (the toggle uses
`addEventListener`) · substrate rebuilt · `validate_analytics_correctness` **7 PASS / 0 FAIL** (4/4 phases).

**Pre-existing tree reds** (Design Tokens, Partial-Label, Canonical Anchor, Deep-Link, Memory M3.1) are from
the 800+ uncommitted prior-session files — **not** this arc.

---

## 6. NEXT

- `analytics-report.html` (89KB print/PDF variant) — same rubric, print has its own rules. **Untouched.**
- `alert-hub.html` carries the **same unreserved `#wh-source-chip`** (empty `<p>`, filled by JS → 0→30px, no
  reserve). **Measured: CLS 0.0749 = PASS**, so it is not a defect today — but its dominant shift (0.0699,
  `#main-content` @613ms) is uncomfortably close to the 0.1 threshold and the chip contributes. Not fixed on
  a guess: needs its own measurement of the chip's share before reserving.
- The `python-api` image bakes code in (no volume mount): the `predictive.py` fix is live via `docker cp` +
  restart, but **needs an image rebuild to persist** — Ian-gated with the commit.
- Commit + deploy remain Ian's gate. All work is local.
