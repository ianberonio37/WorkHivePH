# Roadmap — PM/Analytics Canonical Hardening + Platform Streamlining
_Authored 2026-06-10, during the analytics 4-phase deep-walk. Living doc — Ian to prioritise._

This session started as a cross-page KPI parity audit, became a deep e2e walk of the
analytics 4 phases, and surfaced a canonical bug that had been silently skewing every
PM-due surface platform-wide. This doc captures: (1) what was found/fixed, (2) **why the
mega-gate didn't catch each finding + the validator that now closes the gap**, (3) the
plan to extend the deep walk, and (4) a critic's view on which displays to consolidate.

---

## 1. Findings ledger (this whole session)

| # | Finding | Severity | Status | Commit |
|---|---|---|---|---|
| F1 | Source-chip caption lag: alert-hub + hive board said "PM overdue: 30 days since last anchor" (retired flat-30d rule) while code uses frequency-aware `is_overdue`; hive chip also named the wrong source view (`v_pm_compliance_truth` vs `v_pm_scope_items_truth`) | Low (caption, count was right) | ✅ Fixed | d782b9e |
| F2 | **`v_pm_scope_items_truth.frequency_days` seeder-vocab drift** — CASE matched {Monthly,Quarterly,Semi-Annual,Yearly}; data is {Weekly,Monthly,Quarterly,Semi-annual,Annual} → Weekly/Semi-annual/Annual silently → ELSE 90. Drives `next_due_date`/`is_overdue`/`is_due_soon` platform-wide. Weekly PM showed "due in 90d" not 7. | **HIGH** | ✅ Fixed | ac67feb |
| F3 | `prescriptive.py FREQ_DAYS` identical drift → `calc_pm_interval_optimization` read "weekly = 30d" | Med | ✅ Fixed | 328539c |
| F4 | **pm-scheduler "compliance" mislabel** — computed on-track/total assets (0%/60%), not SMRP 2.1.1 (88.5%); contradicted Analytics + falsely failed the Stair-2 gate | **HIGH** | ✅ Fixed (canonical RPC) | ca98f8a |
| F5 | `parts_consumption_spike` contract violation — `spike_factor: null` for NEW_USAGE parts violates "must be number" (×6) | Low | ⬜ Open | — |
| F6 | Em-dash / degree-sign double-encoding (mojibake) in orchestrator/python output strings | Low (cosmetic) | ⬜ Open | — |
| F7 | RLS trap: MCP `grafana_reader` can't read RLS base tables (`pm_completions`=0 false-read); verify via `v_*_truth` | n/a (method) | ✅ Memory | — |
| F8 | "Analytics env-blocked" was STALE — all 4 phases work (postgres_rpc + Python API reachable after the 2h-ago edge restart) | n/a (doc) | ✅ Corrected | — |
| F9 | Flat 14-day `is_due_soon` window makes Weekly PMs *perpetually* "due soon" (28/30 assets). Computation correct; UX dull | Design | ⬜ Open (see §4) | — |

**Canonical wins shipped:** `get_pm_compliance_smrp` RPC = single source of truth for SMRP
compliance (pm-scheduler + analytics-orchestrator both read it; 88.5% / 519 of 586 / 30 assets).

---

## 2. WHY the mega-gate missed each finding (the gap analysis Ian asked for)

The gate is **strong on structure, weak on semantics**. It exhaustively checks *existence*
(columns, views, tokens, selectors, RPC args) but rarely checks whether a *derivation is
correct* or whether *independent copies of a rule agree*. Mapping each finding to its gap:

| # | Caught? | Why it slipped | Gate gap pattern | Closing action |
|---|---|---|---|---|
| F2 | ❌ No | `query-column-existence` confirmed `frequency_days` EXISTS; nothing checked the CASE produces the RIGHT number, or that the CASE covers the real `frequency` vocabulary | **Semantic-not-structural** + **value-space coverage** | ✅ `validate_frequency_map_consistency.py` (live view + static; registered G0 blocker) |
| F3 | ❌ No | Same — a Python dict copy, no cross-copy agreement check | **No single-source-of-truth check** across the ~6 frequency maps | ✅ same validator (static scan catches code copies) |
| F4 | ❌ No | `cross-surface-kpi-sentinels` (35) assert COUNT parity for the *same* metric, but pm-scheduler "compliance" and analytics "compliance" are computed *differently* under the same label — a definitional, not count, mismatch | **Same-label-≠-same-derivation** not asserted | ⬜ **NEW validator** (§3.A): two surfaces using a registered KPI label must read the same canonical source/RPC |
| F1 | ❌ No (`source-chip-truth` PASSED) | It validates the source *token* exists/queryable, not that the prose NOTE describes the *current* rule, nor that the token matches the view the code actually queries for that metric | **Caption-vs-computation** drift | ⬜ **Extend `source-chip-truth`** (§3.B): flag retired-rule keywords ("30 days since last anchor", "is_due") + bind source token → queried relation |
| F5 | ⚠️ Surfaced, not blocked | Tier-C contract emits `_contract_violation` inline but it's non-blocking (dashboard falls back) | **Non-blocking signal never escalates** | ⬜ **Ratchet** `_contract_violation` counts forward-only (§3.C) + fix the contract to allow `null`/sentinel for NEW_USAGE |
| F6 | ⚠️ Baselined FAIL | `em-dash` validator catches it but it's a frozen pre-existing FAIL | **Baselined cosmetic debt** | ⬜ Fix at source (Python `ensure_ascii`/UTF-8 normalise on generated strings) → baseline auto-tightens |
| F7 | n/a | Testing-method gotcha, not a product defect | — | ✅ Memory (`verify via v_*_truth, not base tables`) |

**The 4 meta-gaps to close (priority order):**
1. **Semantic/derivation validators** — assert mappings/formulas are *correct*, not just present. (frequency-map ✅ done; compliance-source next.)
2. **Same-label-same-derivation** — any KPI shown on ≥2 pages must read one canonical source. Extends count-parity sentinels to *source*-parity.
3. **Escalate non-blocking signals** — contract violations + baselined cosmetic FAILs get forward-only ratchets so NEW ones block.
4. **Caption-vs-code** — source chips must describe the *current* derivation (keyword denylist + token↔relation binding).

---

## 3. Concrete gate actions (backlog)

**A. `validate_kpi_source_parity.py`** (closes F4 class). A KPI registry maps each
user-facing metric label → its canonical source (view/RPC). The validator asserts every
page rendering that label reads from the registered source (no local re-derivation).
Seed registry: `pm_compliance → get_pm_compliance_smrp`, `pm_overdue → v_pm_scope_items_truth.is_overdue`,
`risk → v_risk_truth`, `low_stock → v_inventory_items_truth.is_low_stock`, `open_wo → v_logbook_truth status=Open`.

**B. Extend `validate_source_chip_truth.py`** (closes F1 class): (i) denylist of retired-rule
phrases ("30 days since last anchor", "is_due", "limit as count"); (ii) for each source-chip
`source:` token, confirm the page actually queries that relation for the chip's metric.

**C. Contract-violation ratchet** (closes F5 class): a validator that counts
`_contract_violation` entries across edge-fn live responses (or contract self-tests) and
fails on a rise above baseline. Plus fix `parts_spike_v1` to permit `spike_factor: null`
(or a `NEW_USAGE` sentinel) so the legitimate zero-baseline case is contract-valid.

**D. Encoding-hygiene at source** (closes F6): normalise generated strings to proper UTF-8
(Python `json.dumps(..., ensure_ascii=False)` end-to-end; audit the em-dash/°/× emitters in
`analytics/*.py` + orchestrator interpolations).

---

## 4. Open product/design decisions (need Ian's call)

- **F9 — frequency-relative `is_due_soon`.** Flat 14-day lead means Weekly PMs are *always*
  due-soon (28/30 assets, "BUSY WEEK" forever). Options: (a) leave it (a plant with 35 weekly
  PMs genuinely does ~35/week — arguably correct); (b) make the lead window frequency-relative
  (Weekly → 2d, Monthly → 7d, Quarterly+ → 14d) so "due soon" means "act now, not routine."
  Recommendation: (b) — more actionable — but it changes the canonical view again, so it needs
  a deliberate choice, not another silent edit.
- **Seed staggering** — moot: weekly completions are *already* staggered 06-02…06-08; the
  due-soon volume is inherent to weekly cadence, not a clustering artifact. No seed change needed.

---

## 5. Deep-MCP-walk extension plan (the interconnected web)

Method (locked this session): settle via `browser_wait_for` (never `setTimeout` in evaluate);
read via `browser_snapshot` on gated pages; recompute every tile against `v_*_truth` (NOT base
tables — RLS); apply *same-name-≠-same-derivation* + *worker-vs-hive-scope* + *TZ-aware "today"*.

**Walked this session:** index(Home), hive board, asset-hub, pm-scheduler, alert-hub, logbook,
inventory, predictive, dayplanner, analytics (all 4 phases).

**Remaining — walk each × role(supervisor/worker) × state(empty/partial/full):**
`shift-brain`, `community`, `marketplace`(+admin/seller/feed), `resume`, `skillmatrix`,
`achievements`, `voice-journal`, `assistant`, `audit-log`, `ai-quality`, `llm-observability`,
`engineering-design`, `engineering-calc`, `project-manager`, `integrations`, `plant-connections`,
`report-sender`, `ph-intelligence`, `founder-console`. For each: recompute KPIs vs canonical,
log derivation mismatches, fix + add a source-parity registry entry (§3.A).

---

## 6. Streamlining / consolidation (critic's view)

The platform has **one real dashboard (hive board) and several satellites that re-show slices**
of the same canonical signals. The same metric is rendered on up to 5 surfaces:

| Metric | Surfaces today |
|---|---|
| PM overdue | Home tile · hive board (×3: banner/open-issues/team-pulse) · alert-hub PM tab · pm-scheduler · analytics |
| Risk (crit+high) | Home tile · alert-hub · predictive · hive pattern-alerts · analytics predictive |
| Low stock | Home tile · hive board · alert-hub stock · inventory |
| PM compliance | pm-scheduler · analytics · hive maturity |

**Consolidation theses (for debate):**
1. **Retire/fold `predictive.html`.** It's already half-deprecated — the page itself says
   "Per-asset risk and history is now centralized in Asset Hub." It only renders the
   `v_risk_truth` table (5 assets). Fold its risk-ranking into the Analytics *Predictive* tab
   (which is richer) and/or Asset Hub; keep a redirect. **Removes a whole page.**
2. **Make `alert-hub` a drill-down of the hive board, not a parallel composer.** Both compose
   risk+PM+stock+pattern into a feed. Extract ONE alert-composition source (an RPC/edge fn) and
   have the hive board "Open issues" deep-link into alert-hub as the full feed — one composer,
   two views, zero re-derivation.
3. **Single dashboard contract.** Home's 4-tile glance + hive board headline duplicate each
   other. Keep Home as the *marketing+glance* entry that deep-links to the hive board as THE
   operational dashboard. All tiles read `get_hive_dashboard` (already exists) — no page
   recomputes.
4. **"What's happening today" is split 3 ways** — `shift-brain`, `dayplanner`, hive-board
   activity/team-pulse all answer it. Candidate to merge shift-brain's summary into the hive
   board (or vice-versa) and keep dayplanner as the *planning* tool only.

**Architectural through-line (the real fix behind all of this):** every KPI should have **one
canonical source** (view or RPC), and every surface should **read, not recompute**. We proved
the pattern with `get_pm_compliance_smrp`. Next canonical RPCs to mint: `risk` (exists as
`v_risk_truth` — enforce read-only), `oee`/`mtbf`/`availability` (one per metric), and the
alert-composition feed. Then §3.A's source-parity validator makes "read, don't recompute" a
gate invariant — which is what would have prevented F4 entirely.

---

## 7. Refined thoughts / things easy to miss

- **Prod is still wrong until deployed.** F2/F3/F4 are LOCAL. The production `v_pm_scope_items_truth`
  has the same broken CASE → prod PM due-dates / overdue / due-soon are skewed, and any alerts/
  analytics that fired off them were too. This makes the next deploy a *correctness* deploy, not
  a feature one. (Deploy stays Ian's call.)
- **The frequency bug was invisible to cross-page parity** precisely because every page read the
  same wrong view — they *agreed*, just on a wrong number. Cross-page agreement is necessary but
  not sufficient; you also need agreement with an *independent recompute from raw* (the Layer-B
  method). The gate should add a periodic "raw-recompute vs view" reconciliation for the hottest
  canonical columns.
- **One source of truth beats N correct copies.** Even after fixing all 6 frequency maps, they're
  6 copies that can drift again. The durable fix is to collapse them: SQL reads the view column;
  Python imports ONE `frequency.py` constant; JS reads `frequency_days` from the view. The
  validator is the safety net, but de-duplication is the cure.
- **Honesty surfaced a process bug in me:** I told Ian "all weekly PMs completed same day" — false
  (they were staggered). Verify the premise before proposing the fix. (Already in memory.)
