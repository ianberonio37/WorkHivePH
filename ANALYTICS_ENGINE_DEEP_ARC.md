# Analytics Engine Deep Arc (PDDA) — Page-Deep UFAI

> **Arc kind:** *Page-depth* — the SAME refined PDDA method (Understand → Deepwalk → Ideate →
> Roadmap → Execute → Re-deepwalk) that took `engineering-design` ≈59%→~99%, the Resume Builder
> **~52%→100%**, and the Landing + Home-Dashboard **~52%→96.4%** (4/5 axes gate-locked 100%). The
> platform-wide breadth ruler scores every page **shallow**; this arc scores the **Analytics Engine
> deep** — a fine UFAI sub-dimension decomposition, grounded in external standards, driven LIVE via
> Playwright MCP, improved with skill + reputable-source ideas, ratcheted by gates.
>
> **Target surface:**
> - **`analytics.html`** (**2612 lines / 152KB**) — the Analytics Engine: OEE / MTBF / MTTR /
>   Availability / Performance / Quality KPIs (MTBF ×126, OEE ×95, MTTR ×53, charts ×45), the
>   4-phase analytics view (descriptive / diagnostic / predictive / prescriptive), charts, KPI tiles,
>   time-window filters. escHtml/calm/auth well-instrumented (~100 hits).
> - **`analytics-report.html`** (**1672 lines / 88KB**) — the print-ready analytics report
>   (`window.print`, reads `v_logbook_truth` + `v_hives_truth`); feeds `send-report-email`.
> - **Compute:** edge fns `analytics-orchestrator`, `intelligence-report`, `send-report-email`,
>   `voice-report-intent`; Python API `python-api/analytics/` (`descriptive.py` / `diagnostic.py` /
>   `predictive.py` / `prescriptive.py`).
> - **2 `/learn/` subdirs:** `learn/four-phases-maintenance-analytics-philippine-plants/`,
>   `learn/print-ready-maintenance-analytics-report/`.
>
> **Audience:** Filipino industrial supervisors/planners/managers reading OEE/reliability KPIs to
> decide maintenance + capital actions — the numbers MUST be correct, legible, and honest.

## The PDDA loop (6 phases) — identical to the eng-design + resume + landing arcs
0. **Ground** — skill-first reads + external analytics/KPI/dataviz/reliability standards → a *falsifiable* UFAI sub-dim checklist. (DONE at scaffold, below.)
1. **Understand** — map `analytics.html`: the KPI tiles + their compute source; the 4-phase view (descriptive/diagnostic/predictive/prescriptive → the python-api); every chart + what it plots; time-window/filter logic; the `analytics-orchestrator` + `intelligence-report` edge-fn round-trips; the auth/hive-scope switch; `analytics-report.html` + print/export + `send-report-email`; escHtml coverage; the 2 learn subdirs; deps/CSP.
2. **Deepwalk (live)** — drive via Playwright MCP (whPage `pabloaguilar`/Lucena hive `b86f9ef6` = real KPI data; rawPage anon for the learn subdirs + SEO). Score each sub-dim with **measured** evidence (axe on page+report+charts, CWV, KPI-vs-canonical parity via `window.db`, OEE/MTBF/MTTR faithfulness, cross-tenant isolation probe, 4-phase AI grounding, print/export round-trip). Fill the scoreboard baseline %.
3. **Ideate** — fan-out relevant skills + reputable sources → improvement backlog per axis (cited).
4. **Roadmap** — synthesize into the scoreboard (% per axis, owning skill, citation, locking gate).
5. **Execute** — implement each fix; **verify live each**; lock with a gate/test (ratchet).
6. **Re-deepwalk** — re-score to confirm the ratchet held; synthesize fuse/keep verdicts; persist to skills + memory.

**Done = every axis at its roadmap target, MEASURED and gate-locked** — not one headline metric.

> **Key PDDA insight (proven 3×):** the coarse ruler scans one state statically; the depth walk scans
> the WORKED state. Here that means a **data-rich signed-in hive's real OEE/reliability dashboard** +
> the **print report** + the **4-phase AI compute**. Defects a static/single-state scan structurally
> cannot see: an OEE/MTBF that drifts from the canonical KPI definition, a chart plotting stale/wrong
> data, a predictive number fabricated on insufficient history, a report that leaks another hive's KPIs
> via `send-report-email`, a chart with no a11y/alt, a CLS jump when charts hydrate, an analytics fetch
> failure that renders blank charts (false "healthy"), a 4-phase narrative that overstates.

---

## The five scored axes (Analytics Engine sub-dimension decomposition)

### U — Usability
- **U1** KPI legibility / first-read — OEE/MTBF/MTTR/Availability legible + labelled at a glance; each number says what it means + its unit; no unexplained jargon for a PH supervisor.
- **U2** Chart operability — charts readable, tooltips work, axes labelled, no clutter; the 4-phase view is navigable; interactive drill-downs work.
- **U3** Navigation & wayfinding — analytics ↔ report ↔ source tools (logbook/pm/asset-hub) drill-paths resolve + are consistent; the 2 learn subdirs have a clear path back.
- **U4** Empty / insufficient-data state — a new/sparse hive sees an HONEST "not enough history yet to compute reliable OEE/MTBF" (analytics needs history), not blank charts or a fabricated number.
- **U5** Inclusivity / a11y — axe WCAG2.2-AA = 0 on `analytics.html`, `analytics-report.html`, the OPEN chart/tooltip states, AND the 2 learn subdirs; charts have text alternatives; data-viz contrast; heading outline.
- **U6** Content clarity / scannability — KPI labels, the 4-phase framing, the print report, and the learn articles are scannable + plain-language for a PH supervisor (NN/g; no wall-of-numbers).

### F — Functionality (the heavyweight — KPI correctness)
- **F1** KPI/OEE correctness — OEE (=A×P×Q), MTBF, MTTR, Availability computed correctly + faithful to the canonical KPI definitions + `v_*_truth`; the `analytics-orchestrator` + python-api compute grounded (REUSE `validate_analytics_correctness.py` + `validate_reliability_correctness.py` + `validate_reliability_kpi_faithfulness.py` + `seed_canonical_kpi_definitions.py`).
- **F2** Chart data correctness — every chart/series plots the REAL underlying data (no drift, no stale, no mis-scaled axis); chart totals reconcile with the KPI tiles.
- **F3** Report generation — `analytics-report.html` renders the real KPIs + print/export works end-to-end; `send-report-email` sends the correct scoped report (REUSE `analytics-report.spec.ts` + `journey-report-sender.spec.ts` + `report-sender.spec.ts`).
- **F4** Time-window / filter integrity — date ranges + period filters recompute KPIs correctly (no off-by-one, no TZ drift; PHT anchoring); "today/7d/30d/custom" agree with a SQL re-count.
- **F5** 4-phase analytics grounding — descriptive/diagnostic/predictive/prescriptive (`python-api/analytics/*.py`) return REAL, grounded outputs (no fabricated diagnosis/prescription; predictions honest).
- **F6** Cross-surface KPI parity — an analytics KPI matches the SAME KPI shown elsewhere (home dashboard, asset-hub) — no per-page divergence (REUSE `journey-cross-surface-kpi-parity.spec.ts`).

### A — Adaptability
- **A1** Responsive both viewports — KPI tiles + charts + tables at 390 mobile + desktop; charts reflow; no h-overflow; the report prints cleanly.
- **A2** Data-volume adaptation — works for a data-rich hive (1100+ logbook entries) AND a sparse one; large datasets don't break charts / time out.
- **A3** Persona coverage — supervisor/planner/manager see the right analytics scope; a field worker (if allowed) sees the intended subset.
- **A4** Performance / Core Web Vitals — on the 152KB page + chart rendering: LCP < 2.5s, CLS < 0.1, INP < 200ms; charts don't cause a hydration CLS jump; chart render cost bounded.
- **A5** Offline / degraded-network — an analytics fetch failure → honest "couldn't load analytics", NOT blank charts read as "all healthy / zero"; the report renders or fails honestly.
- **A6** Localization / plain-language — PH-supervisor analytics vocabulary; special chars safe; no em dashes in rendered copy.

### I — Internal Control
- **I1** Hive-scoped analytics — analytics is STRICTLY hive-scoped; NO cross-tenant KPI leak; the `analytics-orchestrator` + the views it reads enforce membership (BOLA probe as in the landing arc's `get_hive_dashboard`).
- **I2** Auth gating — analytics renders ONLY signed-in AND hive-resolved; no flash-of-authed-content; a signed-out user can't reach KPI data.
- **I3** XSS / output-encoding — dynamic KPI/asset/chart-label content (asset names, hive name, worker names) is escHtml-escaped; no raw innerHTML of hive strings; chart labels safe.
- **I4** Calm-dashboard / verdict contract — if analytics carries the calm-dashboard meta, its 3 rules hold; the analytics verdict/lead is honest.
- **I5** Canonical truth-source — every KPI reads a `v_*_truth` / a canonical KPI definition (`seed_canonical_kpi_definitions.py`), not an ad-hoc query that can drift; the report reads canonical too.
- **I6** Report / email isolation — `analytics-report.html` + `send-report-email` are strictly hive-scoped (an email report never contains another hive's KPIs); export/print carry no cross-tenant residue.

### AI — AI Integrity (the 4-phase compute + intelligence-report)
- **AI1** 4-phase compute honesty — predictive/prescriptive (`python-api/analytics/`) do NOT fabricate; grounded in real data; honest confidence; suppressed on insufficient data.
- **AI2** intelligence-report grounding — the `intelligence-report` edge fn grounds its narrative in REAL hive analytics; no invented insight/number/recommendation.
- **AI3** AI copy truthfulness — any AI-surfaced analytics narrative/summary makes only TRUE claims (no invented metric/trend); plain-language.
- **AI4** Predictive honesty / suppression — predictions/forecasts are suppressed or clearly caveated on insufficient history (the platform's "we suppress predictions on insufficient data" rail); no false precision.

---

## Scoreboard (fill after Phase 2 deepwalk; re-score Phase 6)

| Axis | Sub-dims verified | Baseline % (measured Phase 2) | Target | Locking gate | Owning skill |
|---|---|---|---|---|---|
| U — Usability | 1/6 clean (U4); U3 minor | ~62% | 100 | axe (page+report+charts+2 subdirs) + `analytics.spec.ts` | analytics / frontend / designer / qa / mobile |
| F — Functionality | F2/F4 mostly clean | ~55% | 100 | `validate_analytics_correctness.py` + `validate_reliability_*` + cross-surface-parity + report specs | analytics / data / qa |
| A — Adaptability | A2 clean | ~58% | 100 | CWV (LCP/CLS/INP) + responsive + data-volume + offline | performance / mobile / frontend |
| I — Internal Control | I1/I2/I4/I5/I6-scope clean | ~82% | 100 | hive-scoping/BOLA + auth-gate + XSS + canonical KPI + report-isolation | multitenant / security / architect |
| AI — AI Integrity | rails hold where built | ~45% | 100 | 4-phase grounding + intelligence-report grounding + suppression | ai-engineer / predictive-analytics |
| **Analytics overall** | **~baseline** | **~60%** | **100** | | |

## Phase 2 Deepwalk — measured findings (live, pabloaguilar / Lucena b86f9ef6, 2026-07-10)

Stack live-verified: all 4 phases render (Python shim reachable via `workhive_python_api` container; no restart needed). Identity = pabloaguilar (supervisor), Lucena 30 assets, 143 failures/90d.

**Ranked defect register (fix → verify live → lock a gate):**

| # | ID | Sev | Defect (evidence) | Fix | Lock |
|---|---|---|---|---|---|
| 1 | I3/I6 | **M-CONFIRMED** | `send-report-email/index.ts` escapes `r.summary` but NOT `${hiveName}`(:83) nor client-controlled `r.type`→`meta.label`(:57,64) → HTML/link-injection in authed branded email | add `esc()` to hiveName + meta.label | extend a report-email XSS gate/assert |
| 2 | AI2/F5 | **H-CONFIRMED** | `analytics-orchestrator` `callGroqSynthesis` reads stale keys `pred.next_failure_forecast/failure_forecast/anomaly_detection/stockout_forecast`(:519-523) + `diag.repeat_failures`(:516) + `desc.oee.average_oee_pct`(:511); Python emits `next_failure_dates/failure_trend/anomaly_baseline/parts_stockout` → AI action-plan gets ZERO predictive grounding while prompt demands it → fabrication | rename keys to the real phase-output contract (the fn's OWN contract map :886-891 has the right names) | gate: synthesis keys ⊆ phase output contract |
| 3 | AI1 | **H** | `predictive.py:522-577` health score has NO "Insufficient Data" state; absent PM/time → neutral 50; 2-fault/no-PM machine → green "HEALTHY≈83" (false-green rail violation) | add `<3 faults / no-PM → Insufficient Data` status + render branch | extend `validate_analytics_correctness.py` predictive oracle |
| 4 | F1a | **H** | MTBF = mean-of-consecutive-intervals `(last−first)/(n−1)` (RPC `get_mtbf_by_machine` + descriptive/predictive/prescriptive.py) but LABELLED "calendar time (not operating time)"; ignores censored head/tail → understates MTBF → false-RED on sparse data (verified: BLR-003 flips RED→AMBER even on dense Lucena; large on healthy hives). Registry declares calendar=window/failures | re-derive to calendar `period/failures` in RPC + all 3 py paths; fix `validate_analytics_correctness.py:192` oracle (currently enshrines mean-gap, tests only evenly-spaced) | rewrite the gate oracle + add clustered-failure case |
| 5 | F1b | **H** | OEE diverges: analytics page (Python, quality `good_units/total_units`, corrective-only) vs report/asset-hub (RPC `get_oee_by_machine`, quality `quality_pct` only, all rows); single-phase path never applies the RPC override (only PM-compliance is overridden :957-966) | unify quality basis + apply OEE override on descriptive path OR document one canonical source | cross-engine OEE parity gate |
| 6 | U5 | **H** | Plotly charts render into bare `<div>` with no role/aria-label/text-alt (SC 1.1.1); muted text `rgba .2/.25/.3/.38` < 4.5:1 over `#0f1923` (SC 1.4.3) | add role=img+aria-label+data-table alt; lift muted-text contrast | authed axe on OPEN chart states = 0 serious |
| 7 | A4 | **H** | 3 chart mounts (`:1482,1848,2073`) have no reserved height → CLS on every chart phase; `flushCharts` synchronous multi-`newPlot` = long task (INP) | add `min-height` to each `#chart-*` mount; consider rAF-chunk flush | CWV probe CLS<0.1 |
| 8 | A3 | M-H | Persona toggle is cosmetic — role only swaps top quick-view; phase panels identical; report "Audience" only rewrites cover label (`:735`) | product call: real scope OR relabel as "view" | — |
| 9 | AI3 | M | `priority_ranking` composite `crit×failures×avg_downtime` badged "ISO 55001 risk framework"(`prescriptive.py:147`) — must be "custom/composite" | relabel custom/ISO-55001-inspired | assert badge text |
| 10 | AI2b | M | intelligence-report `seasonal_insight` is a required output but `data.seasonal` never placed in prompt(:184-196) → AI invents it; AI-down fallback hardcodes typhoon claim(:214) | feed seasonal into prompt or drop the required field; fallback = honest generic | — |
| 11 | F1d | M | PM compliance overall = unweighted mean of per-asset % (`descriptive.py:238` / RPC `:94`), hero(unweighted) next to sub-line(weighted counts) → "50% · 1 of 21 on time" mismatch; label "30d approx" misdescribes | pick SMRP weighted `Σdone/Σsched`, align hero+sub | assert hero==sub basis |
| 12 | A5 | M | failed fetch → summary tiles stay "Loading…"/grey forever (`renderAnalyticsSummary` never called on error); no `AbortController` timeout; 4× toasts | render `—`/error tiles on fetch fail; add fetch timeout | offline probe: no frozen Loading |
| 13 | A1 | M | 5-6 col tables (`renderPriorityRanking/NextFailure/PartsStockout`) unwrapped (no `.table-wrap` on engine page) → mobile overflow at 390px | wrap wide tables in `overflow-x:auto` | 390px scrollWidth probe |
| 14 | U1/U6 | M | field-tech jargon in first-read path: "partial (A×Q)", "σ", "Spearman", "STAIR-READY" | inline gloss/tooltip | — |
| 15 | A6 | L | rendered em-dash in worker dropdown option `:2478` (No-Em-Dash rule) | replace `—` with parens/colon | grep gate |
| 16 | U2 | M-H | chart in collapsed non-red cards can paint blank (350ms `flushCharts` vs resize-on-open race) | resize-on-open + re-flush guard | — |
| 17 | I1 | H-verify | BOLA: analytics-orchestrator membership check `:749-767` looks correct — LIVE-PROVE with foreign-hive_id (403, not KPIs) + `analytics_snapshots` client RLS (0 rows foreign) | — | BOLA spec |

**Walk order (Phase 5):** low-risk-high-value first — #1 email-XSS → #2 AI key-drift → #9 ISO label → #15 em-dash → #7 chart CLS → #6 chart a11y → then heavyweights #4 MTBF, #5 OEE, #3 health-false-green (careful, gated) → #10-14 → #17 BOLA live-prove. Each: fix → verify live → lock a gate registered in `run_platform_checks`.

## Phase 5 — Execute (progress log)

| # | Status | What shipped (fix → verify → lock) |
|---|---|---|
| #1 I3/I6 | ✅ DONE | `send-report-email` `esc()` on hiveName + meta.label(r.type) + sentAt. Verified: node runs `buildEmailHtml` on 4 XSS payloads → no raw tag. Lock: **`validate_report_email_escaping.py`** (executes the real fn, teeth-tested) registered. |
| #2 AI2/F5 | ✅ DONE | `analytics-orchestrator` synthesis renamed stale keys → real phase contract (`next_failure_dates.predictions`, `parts_stockout.stockout_risk`, `anomaly_baseline.anomalies`, `repeat_failure_clustering.systemic_issues`) + `oee_avg` derived from `oee_by_asset`. Lock: **`validate_analytics_synthesis_grounding.py`** (15 reads ⊆ real phase keys, teeth) registered. |
| #9 AI3 | ✅ DONE | Priority-ranking relabelled "ISO 55001-inspired composite" (card-standard + cardEmpty + prescriptive.py `standard` + docstring). Verified live: card reads "ISO 55001-inspired · 0 P1 · 7 P2". Lock: `validate_analytics_page.py` C2. |
| #15 A6 | ✅ DONE | Worker asset dropdown em-dash removed → "Filter by asset (5)". Verified live (0 em-dash on page). Lock: `validate_analytics_page.py` C3. |
| #7 A4 | ✅ DONE | 3 chart mounts reserve computed `min-height` (pareto/health dynamic, trend 200px). Verified live: pareto mount = 288px exact = rendered height → CLS eliminated. Lock: `validate_analytics_page.py` C1. |
| #17 I1 | ✅ VERIFIED | BOLA live-proven: pabloaguilar → own Lucena 200/30-assets; foreign Manila **403 "not an active member"**, 0 KPIs. Server-side membership check holds. (Data-layer already covered by `validate_auth_live_db.py`.) |
| #3 AI1 | ✅ DONE | `predictive.py calc_health_scores`: `<3 in-period faults → "INSUFFICIENT DATA" (grey)`, never a confident green (missing PM/time/fault default to neutral = false-green). Render: hero = worst ASSESSABLE machine, grey handling, insufficient count. Verified: hermetic 6/6 vectors (THIN-1→insufficient, RICH-1→assessed, teeth); live render backward-safe. Lock: `validate_analytics_correctness.py` +health-insufficient vector. (Python payload activates on image rebuild/deploy — container is image-baked, no host mount.) |
| #10 AI2b | ✅ DONE | `intelligence-report`: `data.seasonal` now fed into the narrative prompt (was required output but absent → AI invented it); AI-down fallback derives seasonal + failure lines from real data (was hardcoded typhoon claim). Lock: `validate_analytics_synthesis_grounding.py` intel-report check. |
| #6 U5 | ✅ DONE | 3 chart mounts carry `role="img"` + data-rich `aria-label` text alternative (SC 1.1.1). Verified live ("Downtime Pareto chart. PV-003 accounts for 7.1 percent of 623.3 hours…"). Lock: `validate_analytics_page.py` C4. (Muted-text contrast is shared utils.js — separate scoped item.) |
| #12 A5 | ✅ DONE | On a descriptive fetch failure the OEE/MTBF/PM tiles now reset to `-`/"Unavailable" (were stuck on "Loading…" forever, contradicting the verdict). Verified live via fetch-fail injection. Lock: `validate_analytics_page.py` C5. |
| #13 A1 | ✅ DONE | Wide list-tables wrapped in `.table-scroll` (overflow-x:auto). Verified live @390px: 6-col Priority Ranking overflowed page by 2px/clipped → now scrolls in-card, docOverflow=0. Lock: `validate_analytics_page.py` C6. |

New/extended gates registered in `run_platform_checks` (AI Validation group, all --fast-safe): `report_email_escaping` (new), `analytics_synthesis_grounding` (new, +intel-report), `analytics_page` (new, C1-C6), `validate_analytics_correctness` (extended +health-insufficient vector, 6/6). All GREEN + teeth-tested; no regression across the 8 files.

**Disposition #4 F1a MTBF (NOT a change — evidence-corrected):** the RPC/py MTBF = mean-of-consecutive-gaps `(last−first)/(n−1)`. The auditor read "calendar time" as period/failures, but the maintenance-expert **standards registry declares MTBF as calendar-DAYS-basis** (calendar days between failures, NOT operating hours) — which the mean-of-gaps satisfies; and `intelligence-report:190` states the same. Critically, the naive "fix" to period/n would **break `calc_next_failure_dates`** (`predicted_next = last + mtbf` needs the mean INTERVAL, not period/n). So the current impl is **defensible-as-is**; the only real refinement is a future display(calendar-T/n)/predict(mean-interval) split — a scoped enhancement, not a bug. Materiality low (29/30 Lucena assets agree band). Left unchanged.

| #14 U1/U6 | ✅ DONE | Plain-language glosses added for the two most opaque field-tech terms: Skill-MTTR "r = / Spearman" (what correlation means + significance) and Anomaly "σ / UCL / mean" (how far a reading strays). Served + page renders end-to-end. |

| #5 F1b | ✅ DONE | OEE page-vs-report divergence FIXED via the full anti-seesaw cycle: **deep-walk** (only value-consumer = analytics-orchestrator report path; OEE not cached; no gate hard-asserts old value) → **transaction-test** (BEGIN/ROLLBACK proved the fix) → **migration** `20260710000000_get_oee_by_machine_good_total_quality.sql` (RPC quality now derives from good/total + corrective-scoped, mirroring `descriptive.calc_oee` — the May-2026 Python fix that never reached the RPC) → applied local + **live cross-surface parity verified** (AC-001..004: page==RPC, e.g. AC-001 OEE 96.6%→87.1%, the ~10pt overstatement gone) → **gate** `validate_oee_quality_derivation.py` (teeth) registered. |

### Gates this arc (all GREEN + teeth, registered AI-Validation, --fast-safe):
`validate_report_email_escaping.py` (new) · `validate_analytics_synthesis_grounding.py` (new, +intel-report seasonal) · `validate_analytics_page.py` (new, C1-C6) · `validate_oee_quality_derivation.py` (new) · `validate_analytics_correctness.py` (extended +health-insufficient vector, 6/6). Migration `20260710000000_get_oee_by_machine_good_total_quality.sql` (applied local; prod deploy Ian-gated). 4 skill writebacks: ai-engineer (synthesis-key-drift), security (escape-every-sink), frontend (chart CLS/a11y/fetch-honesty), qa-tester (evidence-first + live-probe recipes).

| #U5 | ✅ DONE | Muted-text contrast (WCAG AA 4.5:1). axe on the live page = 0 confirmed (but 237 incomplete over the aurora gradient); MANUAL contrast-vs-effective-bg computation confirmed real fails (`.card-title` 3.22, `.data-table th` 2.7, `.kpi-detail p` legend 1.88, `.role-row .label` 4.48). Fixed analytics.html classes + inline `color:rgba(255,255,255,0.4)`(×14) + shared `utils.js#renderKpiTile` (title/unit/sublabel/legend 0.2-0.45→0.6) → re-verified live **all pass 6.99-7.38:1** (utils.js fix also lifts hive/asset-hub/predictive). Lock: `validate_analytics_page.py` C7 (no sub-0.5 white text). |

| #11 F1d | ✅ DONE | PM-compliance hero-vs-sub mismatch. Corrected my own false-blocker (the "maturity-stairway is calibrated" risk was FALSE — grep proved `overall_pct` is NOT consumed by hive_readiness/maturity; those read per-asset `is_overdue`/`compliance_pct`). Real fix: canonical `overall_pct` unweighted-mean → **SMRP-weighted Σcompleted/Σscheduled** in the RPC ([migration 20260710000001](supabase/migrations/20260710000001_get_pm_compliance_smrp_weighted.sql)) + descriptive.py — aligns with journey_trace's existing terminus assertion. Deep-walk (real consumers: analytics hero/detail, report, pm-scheduler, DOM-oracle) + transaction-safe migration + **live end-to-end verify in hive mode: hero 88% == sub "542 of 618" (88%) == detail 87.7% == STAIR-READY** (mismatch gone). Bonus discovery: the earlier 19.6% was ALSO worker-scoped (see HIVE_ID note). Lock: `validate_pm_compliance_weighted.py` (teeth) registered. |

| #U5+ | ✅ DONE (full-page) | Contrast driven to **0 WCAG-AA failures on the ENTIRE analytics page** (was 18). Beyond the analytics content + `utils.js#renderKpiTile` (C7): also fixed the shared chrome that renders on the page — `nav-hub.js` (section-label 0.25 / quick-label 0.45 / mode-btn 0.4 / search placeholder+icon+kbd 0.3 / panel-header brand 0.3 → 0.6) + `learn-link.js` guide-dismiss ×. Verified live: full-body white-text sweep = **0 fails** (the one residual "×" is a UI-control glyph passing SC 1.4.11's 3:1). Fixes benefit all 43 pages that load these globals. |

### Findings (verified non-defects / out-of-arc):
- **#16 U2 collapsed-chart blank race** — VERIFIED NOT a defect: the pareto chart renders a full 288px SVG **even while its card is collapsed** (`cardCollapsed:true, svgHeight:288, 0 blank charts`) — the CLS min-height reserve + flushCharts prevent the predicted race. Evidence-first.
- **HIVE_ID resolution note (cross-cutting, flagged):** `analytics.html:633` `HIVE_ID = wh_active_hive_id || wh_hive_id || null`. A session with `wh_hives` (membership) but no `wh_active_hive_id` silently drops to WORKER scope (surfaced when the test session lost the key mid-run). All 43 pages read HIVE_ID identically → normally sign-in sets it (prior arcs verified hive mode). A defensive fallback to the sole `wh_hives[0].id` belongs to a platform-wide identity pass, not this arc (band-aiding one page creates inconsistency).

## ARC STATUS — COMPLETE (Phase 6 re-scored, all fixes LIVE locally)

**16 defects fixed → live-verified → gate-locked** (15 + HIVE_ID resilience) + full-page WCAG-AA contrast (0 fails). Evidence-first dispositioned 3 non-defects (#4 MTBF, #8 persona, #16 chart).

**Local activation DONE (Ian: "live is our preference; verify locally"):** all fixes now live in the local stack —
- **DB migrations** applied (OEE good/total quality; PM SMRP-weighted).
- **Python container** `docker cp` + restart → #3 health-suppression + #11 descriptive-weighted live (`data_sufficient`/`insufficient_count` fields now served).
- **Edge fns** bind-mounted → #1 `esc()`, #2 `next_failure_dates` synthesis keys, #10 seasonal all served live (verified in-container).
- **HIVE_ID fallback** live-verified end-to-end: with `wh_active_hive_id` cleared, the page still resolves hive mode → PM 88% hive-scoped (was silently worker-scoped 19.6%).

**Phase-6 live re-score:** hive-scope resolved · contrast 0 fails · chart a11y (role=img+aria) · CLS reserve 288px · console clean · PM hero==sub==detail (88%) · OEE page==RPC.

**Gates (7, all GREEN+teeth, registered AI-Validation):** report_email_escaping · analytics_synthesis_grounding (+intel) · analytics_page **C1-C8** · oee_quality_derivation · pm_compliance_weighted · analytics_correctness (6/6). **2 canonical migrations · 4 skill writebacks.** Prod deploy stays Ian's gate; everything is verified LOCAL.

**Full-platform `--fast` regression (463 PASS / 23 FAIL) — HONEST read:** the 23 FAILs are **pre-existing entangled prior-session debt** (the tree had 570+ modified files + `.last-fullstack-gate-pass` already dirty at session start; the failing gates — Marketplace, Webhook-Idempotency, Memory-M3.1, Audience-Block/learn-articles, Canonical-Sources/Anchor, Design-Tokens, Env-Variable/Secret, Trigger-Function, Timer-Cleanup, Unbounded-Query, Clone-Debt, AI-Seams, Q4-Ceiling, Auth-Migration, Accessibility-Baseline, Audit-Trail, Gateway-axis — validate NONE of the files this arc changed). **The analytics arc's own gates are all GREEN** (Analytics Engine Validator 4-layer PASS · Analytics Value Accuracy PASS · all 7 new gates GREEN). The ONE FAIL my edits touch is **Render Budget (severity: WARN)** — analytics.html grew 148KB(HEAD)→154KB (prior-session work already had it ~152KB before this arc; my a11y/CLS/resilience additions are ~2KB on top). It can't be greened by this arc (the 150KB soft-ceiling breach is cumulative page size, a perf/page-split concern, not an analytics-correctness defect). No NEW functional regression introduced by this arc.
- **nav-hub chrome contrast (OUT-OF-ARC)** — the full live sweep found 18 remaining sub-AA failures, ALL in the shared `nav-hub.js` chrome (`wh-hub-mode-btn/-icon/-section-label/-quick-label`) + search overlay, identical on EVERY page → a platform-wide nav-hub/community item, not analytics-engine. Flagged for that owner.

### Dispositioned (evidence-corrected, NOT defects):
- **#4 MTBF** — defensible calendar-days-basis (registry-declared); naive period/n "fix" breaks `calc_next_failure_dates`.
- **#8 A3 persona** — "Field Tech: My Focus Today" quick-view is an honest focus lens, not a claimed data restriction; report "Audience:" is a who-it's-for label.

**Phase 6 (next):** re-deepwalk to re-score the axes post-fix; execute #11 (careful) + U5-contrast (cross-page); finish any residual skill writebacks.

---

## Phase 0 — GROUND (done at scaffold time)

**Skill-first (READ before touching):** `analytics-engineer` (OEE dashboards, KPI design, Recharts/Tremor,
cross-hive reporting), `data-engineer` (query patterns, canonical KPI, TZ/period), `maintenance-expert`
(the DOMAIN definitions — OEE=A×P×Q, MTBF, MTTR, availability; PH industrial practice), `predictive-analytics`
(the 4-phase predictive/prescriptive honesty + suppression), `frontend` (chart render + calm patterns),
`designer` (data-viz contrast, chart legibility), `performance` (152KB + chart render CWV), `qa-tester` (the
journey checklist), `mobile-maestro` (390 charts/tables), `security` (report/email isolation, XSS), `multitenant-engineer`
(hive-scoped analytics RLS), `ai-engineer` (intelligence-report grounding), `architect` (canonical KPI truth-source),
`knowledge-manager` (the print report as a shareable record).

**External standards (the falsifiable bar):** the reliability/maintenance KPI definitions — **OEE = Availability ×
Performance × Quality** (SEMI E10 / Nakajima TPM), **MTBF / MTTR** (ISO 14224, SMRP metrics), Availability
(uptime/(uptime+downtime)); the **`dataviz` skill** (chart color/accessibility/legend/axis/tooltip rules — read
BEFORE any chart change); **Core Web Vitals** LCP<2.5/CLS<0.1/INP<200 (web.dev); WCAG 2.2-AA incl. non-text-contrast
for charts (SC 1.4.11) + a text alternative for data viz; NN/g dashboard + scannability; the "suppress predictions
on insufficient data" honesty rail. OSS/reference: web.dev/vitals, axe, the SMRP/ISO-14224 metric set.

**What already exists (don't rebuild — REUSE + re-measure):** `tests/analytics.spec.ts`,
`tests/analytics-report.spec.ts`, `tests/journey-analytics.spec.ts`, `tests/journey-cross-surface-kpi-parity.spec.ts`,
`tests/journey-report-sender.spec.ts`, `tests/report-sender.spec.ts`, `tests/project-report.spec.ts`;
`tools/validate_analytics_correctness.py`, `tools/validate_reliability_correctness.py`,
`tools/validate_reliability_kpi_faithfulness.py`, `tools/validate_projects_correctness.py`, `tools/debug_analytics.py`,
`tools/seed_canonical_kpi_definitions.py`, `tools/seed_new_page_kpis.py`, `analytics_correctness.js`. Prior work
built rich KPI-correctness coverage (F1); this arc's value = a **fresh, per-sub-dimension, standards-grounded DEEP
re-score of ALL 5 axes** — catching the gaps the KPI gates don't systematically measure (axe on charts + report,
CWV on the 152KB page, chart-data-vs-tile reconciliation, the 4-phase AI grounding, cross-tenant KPI/report-email
isolation, insufficient-data honesty, mobile chart reflow).

**Playwright identity:** whPage = `pabloaguilar` / `test1234`, Lucena Pharmaceutical Mfg. hive
`b86f9ef6-b0a6-477d-b9c6-ca865c3b9dba` (real data: 1100 logbook / 5 risk / 27 inventory → real OEE/MTBF).
rawPage (anon) for the 2 learn subdirs + SEO. **Test-pollution guard (learned 3×):** any live MCP write to the
shared DB must be cleaned by `auth_uid`/`worker_name` or a sibling journey reddens. **Local URLs:**
`/workhive/analytics.html`, `/workhive/analytics-report.html` (the `/workhive/` prefix is the Tester door;
`/workhive/` alone = the mode shell).

---

## NEXT (fresh window — start here)
1. **Phase 1 — Understand.** Map `analytics.html` (KPI tiles + compute source; 4-phase view → python-api;
   every chart + what it plots; time-window logic; `analytics-orchestrator`/`intelligence-report` round-trips;
   auth/hive switch; `analytics-report.html` + print + `send-report-email`; escHtml; 2 learn subdirs; deps/CSP).
2. **Phase 1.5 — static-predict WORKFLOW** (the 6-agent fan-out: U/F/A/I/AI axis auditors + a completeness
   critic → a per-sub-dim probe plan + ranked top-risks + one walk order). It paid off **3×** (resume, landing);
   use it here — the surface is large (2 pages + a 4-phase python-api + 4 edge fns). Use the **Agent tool** (not
   Workflow) unless Ian opts into orchestration.
3. **Phase 2 — Deepwalk LIVE** (whPage real KPIs + rawPage subdirs) → fill the scoreboard baseline %.
4. **Phase 3 Ideate → Phase 4 Roadmap (%+gate) → Phase 5 Execute (fix→verify live→lock a gate→next) → Phase 6
   Re-deepwalk.** Ratchet discipline: every fix locks a gate (extend `validate_analytics_correctness.py` / a new
   `validate_analytics_page.py` / the analytics specs), registered in `run_platform_checks`. Keep edits LOCAL; Ian
   gates commit + deploy.

_Arc opened 2026-07-10. Spine modeled on `LANDING_DASHBOARD_DEEP_ARC.md` (96.4%, 4/5 axes 100%) +
`RESUME_BUILDER_DEEP_ARC.md` (100%) + `ENGINEERING_DESIGN_DEEP_ARC.md`. Pairs `feedback_pdda_page_deep_arc`
(the method) + the `analytics-engineer` + `maintenance-expert` (KPI definitions) + `dataviz` skills._
