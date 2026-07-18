# ASSET HUB · ALERT HUB · SHIFT BRAIN — Page-Deep UFAI PDDA Arc

> ## ★ REMAINING BACKLOG (LOW severity, documented — not blocking; all keystones + Ian's reuse/connectivity ask + A-axis shipped+gated)
> Verdicts, not silent drops. Candidate for a follow-up pass:
> - **F6/F7 (alert triage UX):** system/amc historic rows lack a dedupeKey → no Seen/Snooze/Handled (they're informational, arguably correct); "handled" keys are name-stable so a re-fired signal stays hidden. Decision: add occurrence/date to the dedupeKey.
> - **F18 (asset-hub dead ext-card):** `loadDetailExternalIds` reads `node.external_ids` but the fleet select omits it → the External-systems card can never show. KEEP-or-CUT decision (CMMS-IDs feature) — add `external_ids` to the select, or retire the card.
> - **F20 (asset-hub 200-row fleet cap):** tiles/search/QR-scan operate on a silent 200-row slice; add a "showing first 200" note or paginate the count source.
> - **F21 (worker pending-tile phantom 0):** `loadPendingAssets` is supervisor-gated → a worker's "Pending assets" tile always reads 0 even with their own submission queued. Show the worker their OWN pending count (RLS-own-authored) or hide the tile for workers.
> - **F32/F35/F38 (alert-hub honesty nits):** never-completed PM gets a synthetic 30d-ago timestamp; anomaly badge hard-caps at 5 as a count; scheduled-agents cron copy says "morning" for a 14:00-PHT job.
> - **F41/F43 (asset-hub):** brain citations opaque ("logbook #3", no link); staging `expires_at` selected but never enforced (expired recs still acceptable, `in_stock` frozen at gen-time).
> - **Ext-2 reuse follow-ups:** retire asset-brain's DIRECT `asset-brain-query` fallback so 100% routes via ai-gateway (tenancy+PII+memory); centralize `whRiskColor(level)` in utils.js (risk-level→color hand-rolled 3×).

# ASSET HUB · ALERT HUB · SHIFT BRAIN — Page-Deep UFAI PDDA Arc  (drafted for a fresh window)

**Drafted 2026-07-12** (PM Scheduler arc's window, wrapping on Ian's (e) — "wrap this up, proceed to next fresh window").
Same 6-phase PDDA (Understand → Deepwalk → Ideate → Roadmap → Execute → Re-deepwalk) as eng-design / resume / landing /
analytics / integrations / Hive / Community / Marketplace / Project-Manager / Logbook / Inventory / **PM Scheduler**
(just landed 100%). Ian: *"I love the PDDA flow (same as logbook & inventory & pm-scheduler — we regressed from that
clean flow, back to it). Another, refined: PDDA for **Asset Hub, Alert Hub, and Shift Brain** + their subdirs, extend the
UI/UX + UFAI we already have. I'm striving for the BEST Asset Hub / Alert Hub / Shift Brain + their cross-page
connectivity using the reuse discipline. Refine + extend the terms I've missed. **Update the arc roadmap after EACH phase
with items + percentage so you don't get lost.** Wrap up, proceed in a fresh window."*

> **What this arc IS.** These three pages are the platform's **INTELLIGENCE / AGGREGATION layer** — they do not (mostly)
> capture new data; they COMPOSE and SYNTHESIZE from the canonical `v_*_truth` views + the orchestrator edge functions
> and present a supervisor's/tech's single pane. Deep-walk `asset-hub.html`, `alert-hub.html`, `shift-brain.html` (+ their
> `learn/` subdirs) as the real personas, measure every axis LIVE, and drive them to the **best intelligence surfaces** by
> (1) perfecting the **synthesis + triage UX** (one machine's whole story · one chronological alert inbox worst-first ·
> one shift plan you can act on), (2) treating each as a **faithful AGGREGATION** whose every displayed number/alert/plan
> must trace to a real source with no phantom/stale/double-counted signal (the X keystone for a consumer surface), and
> (3) applying the **reuse discipline** so they compose FROM the canonical primitives (v_asset_truth, v_risk_truth,
> v_pm_scope_items_truth, v_pm_compliance_truth, inventory, logbook, the orchestrators) rather than re-deriving them.

---

## ★ PRE-IDENTIFIED FRONTIER (from prior arcs' evidence — confirm/measure LIVE in Phase 0-2)

- **★ asset-hub has a KNOWN-OPEN JTBD.** The LIVE_PAGE_JOURNEYS roadmap scores asset-hub at **75–100% (3-4/4)** — the
  ONLY K4 page not at a clean 100% local. Phase 2 must find + close that open journey (likely the Reliability Workbench
  or Live Telemetry path). This is a pre-identified U keystone.
- **★ asset-hub calls `asset-brain-query` directly (bespoke chat).** The AI_SURFACE_MAP §Step-3 flags the asset-hub
  "Asset Brain Q&A" box as a bespoke Tier-3 chat UI that should FOLD into the in-context Companion (`WHAssistant.setContext`
  {key:'asset:<tag>'} or route through `ai-gateway` agent `asset-brain` with `context.asset_tag`). Reuse + AI keystone.
- **★ AGGREGATION FAITHFULNESS is the X spine for all three** (parallel to the PM SMRP-parity + the DI-arc seesaw work):
  every alert-hub count (risk / PM-overdue / low-stock / pattern / failed-automation) and every shift-brain plan row
  (top-risk / PMs-due / carry-forward / parts-to-pre-stage) must == the canonical source it claims, with NO phantom
  (alert with no live cause), STALE (AMC brief / shift plan past its cron window not marked stale), or DOUBLE-COUNT.
  alert-hub already fixed one such bug (the retired flat-30-day PM proxy showed 26 vs the canonical 6 — [[reference_...]]).
- **★ CROSS-HIVE write-RLS sweep (the class that REPEATED on inventory→PM).** Phase 2 must audit every table these
  pages WRITE (asset_nodes, rcm_fmea_modes, rcm_strategies [approval-gated], asset-hub's pm_assets/pm_scope_items mirror,
  alert acknowledgements, shift_plans publish) for the `WITH CHECK=null`/permissive class ([[reference_pm_crosshive_write_holes]]).
  asset_nodes/rcm_fmea_modes/rcm_strategies carry the `tg_guard_approval` backstop — verify it holds live.

---

## Scope (grounded, 2026-07-12)

- **Surfaces:**
  - `asset-hub.html` (**3829 lines** — the largest of the three): asset search/scan + graph + timeline + similar-failures
    + **Reliability Workbench (FMEA + RCM + Weibull + P-F)** + **Live Telemetry** (sensor_readings + Z-score anomaly) +
    the PM mirror (pm_assets from asset_nodes; `_intervalToFrequencyLabel` just fixed 2026-07-12) + Asset Brain Q&A.
  - `alert-hub.html` (1614 lines): one chronological alert inbox aggregating risk / PM-overdue / low-stock / pattern /
    failed-automation + the **AMC daily brief** card (amc-orchestrator, 5 sub-agents, 06:00 PHT, one-tap supervisor approve)
    + filter chips + deep-links (`?asset=`).
  - `shift-brain.html` (925 lines): the autonomous shift plan (top-risk assets · PMs-due · carry-forward open work ·
    parts to pre-stage · publish-to-crew) + briefings at 06:00 / 14:00 / 22:00 PHT.
  - **`learn/` subdirs:** `asset-brain-360-one-machine-history-philippine-plant`, `building-asset-register-zero-budget`
    (asset-hub) · `plant-alert-inbox-amc-daily-brief`, `predictive-alert-thresholds-plants` (alert-hub) ·
    `autonomous-shift-planning-philippine-plants`, `maintenance-shift-handover-template` (shift-brain) ·
    `predictive-maintenance-on-a-budget-philippines` (cross). (Confirm article↔tool alignment + CTAs in Phase 0.)
- **Data model / connectivity (these are CONSUMERS + light writers):**
  - **Reads:** `v_asset_truth` (asset identity/MTBF/lineage), `v_risk_truth` / `asset_risk_scores` (risk), `sensor_readings`
    (telemetry), `v_pm_scope_items_truth` + `v_pm_compliance_truth` (PMs due/overdue/compliance), `v_inventory_items_truth`
    (low-stock/parts), `v_logbook_truth` (history/failures), `shift_plans`, `alerts`, the orchestrator outputs
    (amc-orchestrator, shift-planner-orchestrator, batch-risk-scoring, scheduled-agents).
  - **Writes (audit for the RLS class):** asset-hub → `asset_nodes`, `rcm_fmea_modes`, `rcm_strategies` (approval-gated),
    `pm_assets`/`pm_scope_items` mirror; alert-hub → alert acknowledgements / dismissals; shift-brain → `shift_plans` publish.

---

## ★ THE HEAVYWEIGHTS (refined + extended from Ian's thoughts)

### Heavyweight 1 — U: the BEST synthesis + triage UX for each surface
- **Asset Hub** = "one machine's whole story in one place" — search/scan → identity + lineage + MTBF + history +
  similar-failures + reliability workbench + live telemetry, with the Reliability Workbench (FMEA/RCM/Weibull/P-F) legible
  to a supervisor, not just an engineer. Close the known-open JTBD.
- **Alert Hub** = "one inbox, worst-first" — every signal in one chronological feed, the AMC brief at the top, filter to
  one type, one-tap act (deep-link to the source page). Worst-first + honest-empty + freshness.
- **Shift Brain** = "the shift plan I can act on" — top-risk + PMs-due + carry-forward + parts-to-pre-stage, publishable
  to the crew, with the 3-per-day briefing freshness honest.

### Heavyweight 2 — X: faithful AGGREGATION + provenance (the consumer-surface X keystone)
Every displayed count / alert / plan row must reconcile to its canonical source (no phantom / stale / double-count), the
freshness of cron-generated content (AMC brief, shift plan) must be honest (marked stale past its window), and the
source-chip / "where from?" provenance must be correct. Tamper-evidence = the cross-hive write-RLS sweep + the
approval-gate backstop on asset_nodes/rcm_fmea/rcm_strategies.

---

## ★ EXTENSIONS (refined + extended — the terms Ian implied)

- **Ext-1 — ALERT-STATE / RISK-STATE facet** (parallel to inventory stock-state · logbook entry-kind · PM-state): an alert
  or asset is in a STATE (critical/warning/info/resolved · high/med/low risk) that should ROUTE its action + downstream
  (escalate/act/acknowledge/quiet). Phase-3 fork: first-class action-router vs derived pill.
- **Ext-2 — REUSE compose-FROM (lead: fold asset-brain-query into the Companion).** These 3 pages are the platform's
  heaviest reuse consumers. Synthesis verdicts (FUSE / keep-distinct, fitness-gated): asset-brain bespoke chat → Companion
  (the pre-identified lead); alert-hub ↔ shift-brain overlap (both surface PMs-due + top-risk — one canonical owner?);
  the AMC brief (alert-hub) vs the shift plan (shift-brain) — same orchestrator family, keep-distinct-with-a-reason or fuse?
- **Ext-3 — FRESHNESS / CRON-HONESTY loop** (the term Ian implied for cron-generated intelligence): AMC brief (06:00) +
  shift briefings (06:00/14:00/22:00) are cron-generated; verify the loop is honest — a brief past its window is marked
  STALE, a failed cron doesn't show a silently-old plan as current ([[reference_cron_silent_failure_retention]] class).
- **Ext-4 — RELIABILITY WORKBENCH + PREDICTIVE-THRESHOLD provenance** (asset-hub's FMEA/RCM/Weibull/P-F + the
  `predictive-alert-thresholds` learn): verify the workbench math is standards-grounded + the approval-gate holds + the
  learn articles map to real affordances ([[feedback_articles_tool_aligned]]).
- **Ext-5 — LIVE TELEMETRY grounding** (asset-hub sensor_readings + Z-score anomaly): verify the telemetry tile grounds in
  real sensor_readings (not confabulated), the anomaly chip math is correct, and the MQTT/OPC-UA bridge path is honest-empty
  when no data.

## The scored axes (fill % LIVE in Phase 2) — per page × axis
- **U** — best synthesis/triage UX (asset story · alert inbox worst-first · actionable shift plan; close asset-hub's open JTBD).
- **X** — aggregation faithfulness + provenance + freshness (every count/alert/plan traces to source; cron-honesty).
- **F** — flows E2E (search/scan an asset · workbench · acknowledge an alert · approve the AMC brief · publish a shift plan).
- **A** — plant-floor mobile (axe-0 WCAG 2.2 AA @390px on all three; reuse `axe_scan_live.js`).
- **I** — integrity + audit (the cross-hive write-RLS sweep on asset_nodes/rcm/mirror/shift_plans; approval-gate backstop).
- **AI** — grounded (companion answers asset/alert/shift questions grounded via the truth views; fold asset-brain-query in).

## The PDDA loop (6 phases — identical to prior arcs) — ★ UPDATE THE SCOREBOARD AFTER EACH PHASE
1. **Understand** — map all 3 pages + subdirs + every table + every connectivity edge (IN reads + light writes + OUT).
2. **Deepwalk baseline (MEASURED LIVE)** — Playwright MCP (supervisor/tech/new-user @390px) + postgres MCP. Deepwalk the
   WORKED state; fill the scoreboard %. Confirm the frontier (asset-hub open JTBD · aggregation faithfulness · the RLS
   sweep · fold-asset-brain). LIVE-audit the write-RLS class + any phantom/stale aggregation.
3. **Ideate** — fan-out skills (analytics-engineer, predictive-analytics, ai-engineer, notifications, realtime-engineer,
   frontend, mobile-maestro, qa-tester, security, multitenant, maintenance-expert for reliability, data-engineer) +
   reputable sources (RCM/FMEA/Weibull/P-F, alert-fatigue/inbox design, shift-planning) → cited backlog per axis.
4. **Roadmap** — synthesize the scoreboard (% per axis per page) + the synthesis verdicts (alert/risk-state facet; the
   reuse FUSE/keep-distinct calls: asset-brain→Companion, alert-hub↔shift-brain overlap, AMC-brief↔shift-plan).
5. **Execute** — keystone-first (asset-hub open JTBD + aggregation faithfulness + the RLS sweep + fold-asset-brain), then
   cheapest-first; LIVE-verify EACH slice; ratchet a measured-% board; forward-only gate in `run_platform_checks`;
   skill + memory writeback. **Reconcile the render-budget + sentinel ratchets as the LOCK spoke**
   ([[feedback_gate_green_is_part_of_done]] — read the log's real EXIT, not the wrapper's).
6. **Re-deepwalk** — re-run the persona walk; confirm every axis at its roadmap target, measured + gated; full
   `run_platform_checks --fast` exits 0 (the arc isn't done until the gate itself is green).

## ★ CANONICAL-REUSE + CROSS-PAGE CONNECTIVITY (Ian's steer 2026-07-12) — synthesis + verdicts
_Grounded by the `asset-alert-shift-reuse-connectivity` fan-out (3 mappers, live-verified against code, not stale docs)._

### Cross-page deep-link connectivity — the CURRENT graph (all edges verified live)
**No broken edges.** Every deep-link the trio EMITS has a reader on its destination. (The old
COGNITIVE_LOAD_II matrix saying "alert-hub / pm-scheduler have no reader" is now STALE — those
readers exist; this arc's F4 added alert-hub's `?asset=` reader.) Resolved edges:
- index → asset-hub `?tag=` (QR-scan + Top-At-Risk) · search-overlay → asset-hub `?node_id=` · shift-brain → asset-hub `?tag=` (renderRiskStrip) · alert-hub → asset-hub `?tag=` · index → alert-hub `?focus=` · shift-brain → pm-scheduler `?asset=` (renderPmDueStrip) · alert-hub → pm-scheduler `?asset=` · shift-brain → inventory `?q=` (renderPartsStrip) · alert-hub → inventory `?q=` · asset-hub → marketplace `?listing=`.
- **NEW this session (completed the loop):** asset-hub detail → alert-hub `?asset=<tag>` ("🔔 View alerts" button) — makes the F4 reader live (was an orphan reader) and gives asset↔alert **bidirectional** connectivity. Round-trip live-verified.
- **Locked by** `validate_deeplink_param_contracts.py` (existing forward-only ratchet — REUSED, not rebuilt; exit 0).
- Remaining (LOW, catalogued): shift-brain reads no inbound param (terminal node — nothing deep-links INTO it); asset-hub's "+ Add via PM/Inventory" links are bare (don't hand off asset context).

### Canonical-reuse (compose-FROM) verdicts — lead with the strongest FUSE
1. **FUSE — stock-severity classifier → `whStockSeverity(row)` in utils.js (DONE this session).** alert-hub RE-DERIVED low-stock bands from raw qty (HIGH: the canonical is_low_stock/is_critical_low/is_out_of_stock flags were fetched-but-ignored; the view's migration built them "so the threshold logic isn't reimplemented across 10+ pages"), and renderPartsStrip classified urgency a 2nd divergent way. **Now both call ONE helper reading the canonical flags.** Owner: utils.js. Deleted: alert-hub's `qty<=rp/2` math + strip's inline out-check. Live-verified (Loctite=high/critical-low, others=medium; strip unchanged).
2. **REUSE — staging alert reuses canonical `risk_level` (DONE).** alert-hub's staging alert re-derived a band from `risk_score>=0.85`; now reuses the v_risk_truth `risk_level` already in the feed (falls back to score only if no canonical row). Same asset can't show two bands.
3. **PARTIAL-FUSE — asset-brain box: keep the UI, retire the direct fallback.** The "Ask Asset Brain" box ALREADY routes primarily through `ai-gateway` agent `asset-brain` (tenancy + PII-redaction + memory layers) with a direct `asset-brain-query` fallback. Verdict: **KEEP the per-asset box** (it's the right in-context affordance — the AI_SURFACE_MAP "fold" is satisfied by the gateway routing already in place), remaining work = retire the direct fallback so 100% goes through the gateway. LOW urgency (fallback is a graceful degrade).
4. **KEEP-DISTINCT — AMC brief (alert-hub) vs shift plan (shift-brain).** Same orchestrator family, but different JTBD: AMC brief = supervisor's morning digest to **approve** (one-tap dispatch, daily); shift plan = actionable per-shift worklist to **publish** to crew (per-shift). Both already reuse `renderActionBrief` (analytics-orchestrator prescriptive engine) so the AI narrative can't drift. Fusing would conflate two verbs/cadences/audiences.
5. **KEEP-DISTINCT — alert-hub ↔ shift-brain PMs-due + top-risk.** Both read the SAME canonical (v_pm_scope_items_truth.is_overdue + v_risk_truth high/critical band). Divergence is freshness + caps (inbox = live-per-load; plan = frozen snapshot), NOT logic — acceptable by design.
6. **CLEANUP (DONE) — deleted dead shift-brain renderers** rowRisk/rowPM/rowPart ("kept for reference", superseded by the shared strips) so compose-FROM is the only path. renderRiskStrip is confirmed the single risk-list renderer across all 3.
7. **LOW follow-up — `whRiskColor(level)` not centralized:** the risk-level→color map is hand-rolled 3× (asset-hub list chip, asset-hub detail card, renderRiskStrip CSS) — same canonical band, 3 palettes. Candidate for a shared helper (catalogued, not blocking).

## PHASE 5 EXECUTION LOG (keystone-first, each LIVE-verified + gated) — updated 2026-07-12
| # | Finding | Fix | Live-verified | Gate |
|---|---|---|---|---|
| **F1** | staging `parts` jsonb DOUBLE-ENCODED (seeder `json.dumps`) → asset-hub 0 parts + alert-hub "0 parts…3 parts" self-contradiction | seeder `parts_staging.py` + `shift_plans.py` pass list/dict directly; defensive parse in asset-hub `_parsePartsField`, alert-hub inline, shift-brain payload; fixed 3+3 existing rows in-place | ✅ asset-hub shows 3 parts; alert-hub "**3 parts recommended**"; 0 console errors | ✅ NEW `validate_intelligence_jsonb_shape` (exit 0) — **caught a 2nd instance: shift_plans.payload 3/5 string** |
| **F2** | asset-hub staging handlers call `toast(...)` (id-global div, not fn) → TypeError, no feedback | 4 sites → `showToast(...)` | ✅ "Select at least one part" toast fires, 0 console errors | (covered by walk) |
| **F11** | `asset_risk_scores` FOR ALL member-writable → worker can fabricate/overwrite the risk cache feeding all 3 pages + analytics (LIVE-EXPLOITED: insert+update OPEN_VULN) | migration `20260712000013` locks writes to service-role (matches sensor_readings) | ✅ insert BLOCKED, update 0-rows, read OK, service-role write OK | ✅ NEW `validate_intelligence_write_isolation` 4/4 (exit 0) |
| **F10** | `asset_nodes_write` USING owner-branch ungated → departed member could DELETE own rows | same migration: owner-branch now hive-membership-gated | ✅ cross-hive insert BLOCKED (defense-in-depth) | ✅ (same gate) |

| **F3** | alert-hub feed sorted newest-first (buried criticals) + CTA "filter to Critical/High using the chips" (no severity chip exists = impossible) | worst-first SEV_RANK sort (critical→high→medium→low→info, then recency); CTA rewritten honest; F34 'low' vocab added | ✅ feed order 2×critical→4×high(incl 8d-old Kaeser)→medium; CTA honest; 0 errors | ✅ NEW `tests/alert-hub-triage.spec.ts` 2/2 |
| **F5** | alert-hub automation_log query had no hive filter (RLS-only) | added `.eq('hive_id')` | ✅ (defensive; every other source hive-filtered) | (walk) |
| **F40** | filtered-empty state said "All clear" while other alerts existed | honest "None under this filter · N alerts under other filters" | ✅ System filter → honest message | ✅ (same spec) |
| **F4** | inbound `?asset=`/`?tag=` deep-link ignored (pre-catalogued A1 "alert-hub no reader") | aliased to the existing `?focus=` reader | ✅ logic-verified (proven alias pattern) | (walk) |
| **F15** | shift-brain stale/archived plan rendered under hardcoded "Live" chip; archive didn't hide | `.neq('status','archived')`; `_planIsFresh` shared helper → STALE badge + honest chip | ✅ fresh=no badge/"Live"; stale 22-06=STALE badge+"STALE·from Jul 6"; archive hidden | ✅ NEW `tests/shift-brain-freshness.spec.ts` (2 pass, 1 skip=self-heal) |
| **F14** | shift-planner-orchestrator wrote a plausible empty plan when all sub-agent fetches failed (silent-zero) | orchestrator records `fetch_errors[]`+`degraded` in payload; shift-brain shows incomplete-data banner | ✅ live invoke: `fetch_errors:0` + field present; seeded degraded → banner "This plan is incomplete — risk_top, pms_due failed…" | ✅ (same spec) |
| **F12** | AMC brief + amc-expire-stale crons lived only in manual enable_amc_cron.sql (prod URL) → never armed on fresh envs | migration `20260712000014` arms both via portable-URL pattern | ✅ 3 cron jobs now in cron.job (amc-brief/amc-expire/signature-scan) | ✅ `validate_cron_schedule_integrity` L5 (NEW layer, exit 0) |
| **F13** | failure-signature-scan claimed a daily cron; none existed → pattern alerts age silently | same migration arms `failure-signature-scan-daily` | ✅ armed | ✅ (L5) |
| **F13b** | (found BY the new L5 gate — reuse dividend) hierarchical-summarizer header claimed "pg_cron daily" but never scheduled | header corrected to real trigger (backfill tool + semantic-fact-extractor on-demand); arm-as-drain-cron logged for Ian | ✅ L5 green | ✅ (L5) |

**Gates registered/extended in `run_platform_checks` (Platform group, skip_if_fast, severity=fail):** NEW `intelligence-jsonb-shape`, NEW `intelligence-write-isolation`; EXTENDED `cron-schedule-integrity` with **Layer 5** (fn-claims-cron → must be scheduled) — **reuse discipline: extended the existing cron-validator family rather than shipping a parallel `validate_cron_honesty.py` (deleted)**.

**Additional fixes (cheapest-first batch, all LIVE-verified):** F8 anomaly KPI DOM-scrape race → module-state `_anomalyCount` + re-summary (verdict no longer stuck "All clear"); F16 shift-brain silent count caps → orchestrator flags `payload.caps` per section, shift-brain shows "N+"; F17 LOTO/permit safety badge on carry rows; F19 timeline mislabel (`idx===0&&legacy_asset_id` → `idx===0`; proven via null-legacy probe); learn F27-F29 render bugs (raw Python list literal → `<ol>`, `**markdown**` → `<strong>`, fabricated "ISO 14224"/"Named study (2022)" citations → honest captions across asset-brain-360 / autonomous-shift-planning / plant-alert-inbox-amc).

**★ PHASE-6 RATCHET RECONCILIATION (feedback_gate_green_is_part_of_done — my additions tripped 5 forward-only ratchets, all reconciled, NOT rebaselined):**
- **No-Em-Dash:** 5 displayed em-dashes in my new UI (STALE/degraded/LOTO/CTA/empty-state) → colons/periods. Exit 0.
- **Design Tokens:** `#29B6D9` raw brand-hex in the View-alerts link → `var(--wh-blue)`. 465=baseline.
- **Empty Catch:** 2 comment-only catches in renderAnomalyEngine → `/* empty-catch-allow: … */` marker. drift 0.
- **Seed→Consumer L2:** my sort comparator `(a,b)` collided with the validator's `b` alias for `amc_briefings.brief` → `b.severity` mis-read as a brief key. Renamed params to `(x,y)` (identical logic). Exit 0. (Inaccuracy-not-backlog class.)
- **KPI Source Registry:** deleting dead `rowRisk` removed shift-brain's last textual `risk_level` → registry flagged "missing signal". Honest fix: repointed the `top_risk_band` consumer to `utils.js` (renderRiskStrip, where the band display now lives post-reuse). Also HARDENED the validator's latent `detail`-vs-`reason` KeyError crash (was masking which finding fired). 3/3 + self-test green.

**✅ FULL GATE GREEN: `run_platform_checks --fast` → EXIT 0** (asset_alert_shift_final.log, 2026-07-12). All 7 reconciled ratchets PASS in-suite (KPI/em-dash/design-tokens/empty-catch/seed-consumer/memory-M3.1/migration-immutability) + the 3 new/extended arc gates (intelligence-jsonb-shape, intelligence-write-isolation, cron-schedule-integrity L5) PASS + 0 regressions (Flywheel Turn diff clean). The arc is done to the gate criterion ([[feedback_gate_green_is_part_of_done]]).

## SCOREBOARD (update after EACH phase — Ian's instruction) — updated 2026-07-12 Phase 0-2 + Phase-5 keystones F1/F2/F10/F11
| Page / Axis | Baseline % | Current % | Note |
|---|---|---|---|
| Phase 0-1 Understand | 0% | **100%** ✅ | 6/7 workflow mappers (937k tok) + crossrefs slice done inline. Full maps in scratchpad understand_0..5.json |
| Phase 2 Deepwalk baseline | 0% | **~70%** | asset-hub + alert-hub live-walked @390px + DB-reconciled; shift-brain live walk + live RLS probes + axe remaining |
| Asset Hub — U | ~70% | **~90%** | F1 staging JTBD FIXED+gated E2E; F2 toast FIXED; workbench/timeline/brain/telemetry good. Remaining: F19 timeline mislabel, F20 200-cap, F21 worker pending phantom |
| Asset Hub — X/AI | ~80% | **~88%** | tiles 30/6/0 == DB ✅; brain grounding faithful ✅; F1 staging faithfulness FIXED. Remaining: F18 dead ext-card, F24 report undercount, F41 opaque citations |
| Alert Hub — U/X | ~65% | **~90%** | F3 worst-first FIXED+gated; F5 hive-scoped; F40 honest-empty; F4 deep-link reader. Remaining: F6 undismissable rows, F7 handled-forever, F8 anomaly race |
| Shift Brain — U/X | ~55% | **~85%** | F14 silent-zero degraded-banner FIXED+gated; F15 stale/archive/Live FIXED+gated. Remaining: F16 silent caps, F17 LOTO dropped from carry rows |
| I — cross-hive write-RLS sweep | ~80% | **~95%** | F11 asset_risk_scores LIVE-locked+gated; F10 asset_nodes owner-branch hardened; pm/shift/amc/anomaly/sensor/alert_dismissals SECURE. Remaining: F9 attribution auth_uid class (cross-cutting) |
| A — mobile axe @390px (×3) | — | **100%** ✅ | added the trio to axe_scan_live PAGES; asset-hub 0/931, alert-hub 0/753, shift-brain 0/598 els — **axe-0 WCAG 2.2 AA**; baseline ratcheted; validate_axe_live exit 0 (new LOTO/STALE/degraded/View-alerts UI all clean) |
| Ext-1 alert/risk-state facet | 0% | **~40%** | F34 'low' severity vocab FIXED; SEV_RANK canonical rank established. Remaining: first-class action-router vs derived-pill fork |
| Ext-2 reuse (compose-FROM) + connectivity | ~70% | **~92%** | whStockSeverity single-source (alert-hub+strip); staging reuses risk_level; dead renderers deleted; asset↔alert loop completed+gated (deeplink contracts); FUSE/keep-distinct verdicts synthesized. Remaining LOW: retire asset-brain direct fallback, whRiskColor helper |
| Ext-3 freshness/cron-honesty | ~30% | **~90%** | F12 AMC+expire armed via migration; F13 signature-scan armed; F13b hierarchical-summarizer header corrected; F15 stale marked; L5 cron-honesty gate. Remaining: F38 UTC/PHT copy, F43 expires_at |
| Ext-4 workbench/threshold provenance | **~75%** | — | FMEA/Weibull/P-F live + canonical views ✅; F31 pump-modes-on-generator seed/AI quality; F28 thresholds article funnels to unbuilt config |
| Ext-5 live-telemetry grounding | **~80%** | — | GEN-001 card live+honest, GEN-003 hidden honest ✅; F25 double anomaly math; F26 reload storm; no sensor-quiet staleness cue |

## PHASE 0-2 FINDINGS REGISTER (live/DB/static-verified 2026-07-12)
**Keystones (fix-first):**
- **F1 (X/U KEYSTONE)** `parts_staging_recommendations.parts` DOUBLE-ENCODED (jsonb_typeof='string', all 3 rows) → asset-hub staging card renders 0 parts while rationale says "3 parts"; alert-hub top critical alert reads "0 parts recommended … 3 parts appear" (self-contradicting). Fix: producer (parts staging generator fn) writes array not string + defensive parse in both consumers + gate.
- **F2 (U)** asset-hub staging handlers call `toast(...)` but page defines `showToast` → `toast` resolves to div#toast (id-global) → TypeError; NO user feedback on stage/dismiss (lines ~1778-1821).
- **F3 (U KEYSTONE)** alert-hub feed sorts newest-first (line 1197), NOT worst-first; verdict/CTA says "clear the top" + "Filter to Critical/High using the chips" but no severity chip exists → triage JTBD cannot complete as instructed.
- **F10 (I KEYSTONE)** asset_nodes RLS: USING owner-branch `auth_uid = auth.uid()` has NO hive scoping; DELETE authorized by USING alone → departed member can delete own non-approved rows cross-hive. + WITH CHECK doesn't pin auth_uid=auth.uid() (attribution spoofing).
- **F11 (I KEYSTONE)** asset_risk_scores `FOR ALL` open to ANY active member — a worker can fabricate/overwrite risk_level on the batch-owned cache feeding asset-hub/alert-hub/shift-brain/analytics. Align to sensor_readings pattern (client INSERT/UPDATE/DELETE locked).
- **F14 (X KEYSTONE)** shift-planner-orchestrator: all-sub-agent-failure still upserts a plausible empty plan ("No assets above risk threshold") — silent-zero class, no error marker.
- **F15 (X KEYSTONE)** shift-brain: loadPlan has no date ceiling/status filter → week-old or archived plan renders under hardcoded "Live · shift plan generated on load" chip; archive doesn't hide; publish is advisory (workers see drafts; no crew notification).
- **F12 (Ext-3 KEYSTONE)** AMC brief cron exists only in manual enable_amc_cron.sql (prod URL hard-coded) — never armed locally/fresh envs; alert-hub shows "None today" with no unarmed-automation signal. amc_expire_stale also un-cronned. F13: failure-signature-scan claims daily cron, none exists → pattern alerts age silently as "active".

**Alert-hub triage defects:** F4 inbound ?asset= ignored (outbound links emit it); F5 automation_log query lacks hive filter (leak or dead source); F6 system/amc rows undismissable (no dedupeKey, href '#'); F7 "handled" hides forever (keys lack occurrence/date, re-fires stay hidden); F8 anomaly KPI DOM-scrape race (verdict can say "All clear" while critical signals load) + no 'expired' branch; F32 never-completed PM gets synthetic 30d-ago timestamp (buried by newest-first); F34 'low' severity renders tag-medium (vocab mismatch); F35 anomaly badge caps at 5 as count; F40 kind-filtered empty state says "All clear — no active alerts"; F42 "bookmark via logbook" dead-end.
**Asset-hub defects:** F18 External-systems card dead (external_ids never in select); F19 timeline mislabel branch (idx===0&&legacy_asset_id); F20 200-row fleet cap silent (tiles/search/QR-scan operate on slice); F21 worker pending-tile phantom 0 (loader supervisor-gated); F22 approve/reject audit rows log raw UUID (pending nodes not in _allNodes); F23 pm mirror writes criticality 'Major' (off-vocabulary); F24 printed Reliability Report caps corrective-events at LIMIT 8 + stray </main>; F25 double anomaly definition (server is_anomaly vs client Z-score incl. candidate point; hardcoded "3-sigma" claim); F26 telemetry reload storm (no debounce); F31 FMEA seeds are pump-domain modes on a generator (maintenance-expert quality); F41 brain citations opaque ("logbook #3", no links); F36/F43 staging updates id-only guard + expires_at unenforced + in_stock frozen snapshot.
**Shift-brain defects:** F16 silent server caps (10/30/30/30) flow into tiles/verdict/"Show all N"; F17 carry rows drop loto_applied/permit_reference (SAFETY); F37 shift window from LOCAL browser hours not PHT; worker dead-end copy promises retired cron ("runs on the hour"/06:00-14:00-22:00).
**Cross-cutting:** F9 attribution violations (approved_by/acted_by/acknowledged_by/published_by = spoofable localStorage name, no auth_uid — standing-rule breach); F33 alert-hub re-derives low-stock despite is_low_stock/is_out_of_stock canonical fields; F38 scheduled-agents cron UTC/PHT mislabels (pm-overdue = 14:00 PHT sold as morning); F39 unguarded JSON.parse in 3 scheduled-agents runners fails whole hive run.
**Learn (7 articles):** F27 render bugs — asset-brain-360 prints a raw Python list literal + unconverted **markdown**; two "Source: Named study (2022)" template leaks under fabricated charts; <ol>-in-<p> invalid HTML; F28 predictive-alert-thresholds funnels readers to configure tiers/thresholds Alert Hub doesn't have (ISO 10816 content itself is correct); F29 handover-template CTA claims shift-brain "auto-fills the 5-section handover" (it doesn't; hive.html owns handover); F30 pm-on-a-budget CTA can't deep-link analytics ?phase=predictive (no param handling).
**Verified-good (baseline ✅):** tiles 30/6/0 == DB; risk chips == canonical bands (crit≥0.85 GEN-003 90%, high≥0.70 FL-001 78%); stock 3 == canonical; telemetry honest both states; anomaly-empty honest; AMC "None today" honest-display (given F12); asset-brain answer == logbook root_causes (date+cause exact); chips sum == All; footer refresh stamp honest; RLS secure: pm_assets/pm_scope_items (fixed 20260712000012), rcm_fmea_modes/rcm_strategies (+tg_guard_approval), shift_plans, amc_briefings, anomaly_signals, sensor_readings (fully locked), alert_dismissals.

## What we already built that this arc EXTENDS (don't re-do; build on)
- **The `v_*_truth` canonical views + the KPI source registry + source-chip provenance** → the X aggregation-faithfulness spine.
- **The child/ledger-table WITH-CHECK rule** ([[reference_pm_crosshive_write_holes]] + [[reference_inventory_txn_crosshive_tamper]])
  → the I write-RLS sweep; `validate_pm_write_isolation.py` is the gate template.
- **`setContext` piiSafe grounding (inventory/PM pattern)** + the AI_SURFACE_MAP fold-into-Companion plan → the AI axis.
- **`axe_scan_live.js`** → the A axis (all 3 pages). **The cron-silent-failure class** ([[reference_cron_silent_failure_retention]])
  → Ext-3 freshness. **The reliability-KPI faithfulness gate** (DI arc) → Ext-4 workbench provenance.
- **The ratchet-reconciliation discipline** ([[feedback_gate_green_is_part_of_done]]) → the Phase-5 LOCK spoke.

## NEXT (fresh-window execution starts here)
1. **Phase 0-1 (Understand):** map all 3 pages + 7 learn subdirs × every axis; measure connectivity (all the truth-view
   reads + the light writes); inventory the reuse-overlap surfaces (asset-brain↔Companion, alert-hub↔shift-brain,
   AMC-brief↔shift-plan). Pinpoint asset-hub's open JTBD.
2. **Phase 2 (Deepwalk baseline):** live persona walk (supervisor/tech/new-user, 390px), DB-verified; fill the scoreboard.
   LIVE-audit the write-RLS class + aggregation faithfulness (phantom/stale/double-count) + cron-freshness.
3. **Phase 3-5:** keystones = asset-hub open JTBD + aggregation faithfulness + the RLS sweep + fold-asset-brain-into-Companion;
   then cheapest-first per axis; each slice LIVE-verified + gated; reconcile the ratchets; the full gate must exit 0.
Test: pabloaguilar / test1234, hive resolves via `wh_active_hive_id` (reseed rotates auth_uids — re-sign-in + set the key).
Pairs the PM Scheduler arc (aggregation-consumer X + the child-table WITH-CHECK security class + ratchet-reconciliation) +
[[feedback_synthesis_not_just_audit]] (fuse-into-ONE / keep-distinct) + [[feedback_pdda_page_deep_arc]] (the method) +
the analytics-engineer + predictive-analytics + maintenance-expert + notifications skills.
