# WorkHive Canonical Sources Audit

Date: 2026-05-09. Author: Asset Brain session (Phases 0-4 just shipped).

The platform has grown to ~50 tables, 28 edge functions, and 21 live pages.
Several domain concepts now have parallel implementations across that surface.
This audit lists every shared concept, where it currently lives, and the
proposed single canonical source. The goal is one view per concept, every
agent and orchestrator reads from that view, and a validator catches drift.

Three tiers of scatter:

- **DRIFT**: 3+ implementations, no consensus, agents pick wrong one. Highest priority.
- **CONVERGENT**: multiple readers, single underlying source, just needs documentation + a wrapper view so the contract is explicit.
- **ALIGNED**: already canonical, register it in the table so AI agents can find it.

---

## DRIFT (fix first, biggest payoff)

### D1. Asset identity

The most painful scatter on the platform.

| Source | PK type | Owner | Used by |
|---|---|---|---|
| `assets` | text | inventory + logbook FK | inventory.html, logbook.html, parts deduction |
| `pm_assets` | uuid | PM scheduler | pm-scheduler.html, pm_completions.asset_id, pm_scope_items |
| `asset_nodes` | uuid | Asset Brain (new, May 8) | asset-hub.html, shift-brain payload, asset_brain_overview view |

Three IDs for one physical machine. `asset_nodes` already carries optional
`legacy_asset_id` (text) and `pm_asset_id` (uuid) FKs precisely so we can
unify reads going forward.

**Canonical source proposal**: `v_asset_truth`

```sql
CREATE OR REPLACE VIEW v_asset_truth AS
SELECT
  n.id              AS asset_id,            -- canonical uuid
  n.hive_id,
  n.tag,
  n.name,
  n.level,
  n.iso_class,
  n.criticality,
  n.location,
  n.parent_id,
  n.legacy_asset_id,                         -- bridge for legacy reads
  n.pm_asset_id,                             -- bridge for PM reads
  n.external_ids,
  n.status,
  n.created_at,
  n.updated_at,
  -- Aggregate footprint (was asset_brain_overview)
  (SELECT count(*) FROM logbook l
     WHERE l.hive_id = n.hive_id AND l.asset_ref_id = n.legacy_asset_id) AS lifetime_logbook_entries,
  (SELECT max(l.created_at) FROM logbook l
     WHERE l.hive_id = n.hive_id AND l.asset_ref_id = n.legacy_asset_id
       AND l.maintenance_type = 'Breakdown / Corrective') AS last_failure_at,
  (SELECT count(*) FROM pm_completions pc
     WHERE pc.hive_id = n.hive_id AND pc.asset_id = n.pm_asset_id) AS pm_completed_count
FROM asset_nodes n
WHERE n.status = 'approved';
```

Owner skill: architect. Freshness: realtime (view).

### D2. Asset risk score + reasoning

Same risk computed three different ways depending on which surface asks.

| Source | Computation | Surface |
|---|---|---|
| `batch-risk-scoring` edge fn | Delegates to Python API | nightly write to `asset_risk_scores` |
| `predictive.html` direct read | Reads latest `asset_risk_scores`, renders `top_factors` flat | Risk Ranking, Heatmap, Trend tabs |
| `asset_brain_overview` view | Joins asset_nodes to logbook + pm_completions, derives `current_risk` differently | Asset Hub stats card |
| `analytics-orchestrator` Phase 3 | Recomputes via narrative LLM call on raw logbook | Analytics Engine Phase 3 prose |
| `shift-planner-orchestrator` | Reads `asset_risk_scores`, sorts by `risk_score` | Shift Brain top-N risk list |

The three reads are not contradictory yet only because they trust the same
underlying table, but the rendering is inconsistent (Asset Hub uses
`current_risk`, predictive uses `risk_score`, Analytics uses freshly LLM-derived
narrative). Once we rebuild the model in Phase 5a (composite score with
6 factors and structured contributions), the scatter becomes critical.

**Canonical source proposal**: `v_risk_truth` (latest score per asset with structured factors)

```sql
CREATE OR REPLACE VIEW v_risk_truth AS
SELECT DISTINCT ON (rs.asset_name, rs.hive_id)
  n.id                AS asset_id,           -- canonical uuid via asset_nodes
  rs.hive_id,
  rs.asset_name,
  rs.risk_score,                              -- 0..1
  rs.risk_level,                              -- 'low'|'medium'|'high'|'critical'
  rs.health_score,
  rs.mtbf_days,
  rs.days_until_failure,
  rs.top_factors,                             -- JSONB, structured per Phase 5a
  rs.components,
  rs.model_version,
  rs.generated_at
FROM asset_risk_scores rs
LEFT JOIN asset_nodes n
       ON n.hive_id = rs.hive_id
      AND (n.tag = rs.asset_name OR n.name = rs.asset_name)
ORDER BY rs.asset_name, rs.hive_id, rs.generated_at DESC;
```

Owner skill: predictive-analytics. Freshness: daily 13:00 PHT (set by `risk_scoring_cron`).

### D3. PM compliance per asset

Recomputed in 4+ places with slightly different math.

| Source | Math | Used in |
|---|---|---|
| `analytics-orchestrator` Python phase | full per-discipline rollup | analytics.html descriptive phase |
| `shift-planner-orchestrator` TS | pm_assets where last_anchor_date null or older than 30 days | shift-brain.html PMs Due section |
| hive.html JS | computes due-soon and overdue from pm_scope_items + pm_completions | hive board PM Health card |
| `predictive.html` JS | reads pm_assets with derived overdue flag | risk score factor |
| `validate_pm.py` reference | due_count = period_days / freq_days (per data-engineer skill) | validator's reference |

The data-engineer skill explicitly warns that mixing all-time completions with
period-scoped scheduled counts inflates compliance. Each surface has its own
risk of making this mistake.

**Canonical source proposal**: `v_pm_compliance_truth`

```sql
CREATE OR REPLACE VIEW v_pm_compliance_truth AS
SELECT
  pa.hive_id,
  pa.id                                                    AS pm_asset_id,
  pa.asset_name,
  pa.tag_id,
  pa.category,
  pa.criticality,
  pa.last_anchor_date,
  -- Days since last completion across all scope items for this asset
  (now()::date - max(pc.completed_at)::date)               AS days_since_last_completion,
  count(pc.id)                                             AS lifetime_completions,
  -- Period-scoped fields ready for analytics math
  count(pc.id) FILTER (WHERE pc.completed_at >= now() - interval '30 days')   AS completions_30d,
  count(pc.id) FILTER (WHERE pc.completed_at >= now() - interval '90 days')   AS completions_90d,
  -- Due flag based on category default frequency
  CASE
    WHEN pa.last_anchor_date IS NULL THEN true
    WHEN pa.last_anchor_date < now()::date - interval '30 days' THEN true
    ELSE false
  END                                                      AS is_due
FROM pm_assets pa
LEFT JOIN pm_completions pc ON pc.asset_id = pa.id AND pc.hive_id = pa.hive_id
GROUP BY pa.hive_id, pa.id, pa.asset_name, pa.tag_id, pa.category, pa.criticality, pa.last_anchor_date;
```

Owner skill: maintenance-expert. Freshness: realtime (view).

### D4. Hive KPIs (MTBF, MTTR, OEE, top fault classes)

Computed in different surfaces with no shared math layer.

| Source | Where |
|---|---|
| `analytics-orchestrator` Phase 1 | analytics.html (cached for 12h via hive_analytics_cache) |
| `hive.html` JS | live page math on logbook |
| `asset_brain_overview` aggregate per asset | Asset Hub stats |
| `shift-planner-orchestrator` | shift-brain.html top risk |
| Predictive page Trend | predictive.html third tab |

**Canonical source proposal**: `v_hive_kpi_truth` (1h refresh, cached in hive_analytics_cache, the cache table itself becomes the canonical source via a thin view).

Owner skill: analytics-engineer. Freshness: 1h cache, 12h fallback.

### D5. Audit logs (3 parallel tables)

Three tables logging "something happened":

| Table | Scope |
|---|---|
| `automation_log` | pg_cron + edge function results, job status, batch counts |
| `hive_audit_log` | supervisor moderation actions (approve, kick, mod queue) |
| `cmms_audit_log` | CMMS sync batches per hive |

These are **legitimately different domains** (system events vs. user actions vs.
external sync). They should stay separate but be **registered as canonical
sources** so AI agents know which one to query for which question. A 4th
unified view `v_audit_unified` could be added for cross-cutting queries
("anything happen on hive X in the last 24h?").

Owner skill: data-engineer. Freshness: realtime.

---

## CONVERGENT (single underlying source, multiple readers, just needs a contract)

### C1. Failure history per asset

`logbook` filtered by `asset_ref_id` (legacy) or joined via `pm_completions.asset_id`.

Used by Asset Hub timeline, predictive top-factors, Shift Brain carry-forward,
analytics-orchestrator phase 1, project-progress agent.

Single underlying source (`logbook`), but each consumer writes its own join.
Wrap as `v_failure_history` keyed by canonical asset_id (resolved through
asset_nodes), so agents can query "give me the last 20 events for asset X"
without doing their own join.

Owner skill: maintenance-expert. Freshness: realtime.

### C2. Open work

`logbook` where `status = 'Open'`. Surfaced in 6+ places:

- hive.html Open Work card
- shift handover (with LOTO regex in report-sender.html)
- shift-brain carry-forward filter (`status='Open' AND created_at < now-8h`)
- asset-hub.html (per-asset filter)
- analytics-orchestrator (open count for KPIs)
- project-progress agent (open work scoped to project asset list)

Single source, multiple filters. Wrap as `v_open_work_truth` with derived
columns: `is_loto`, `is_overdue`, `age_hours`, `is_carry_forward`, `asset_id`
(canonical). Filters become column reads, not regex.

Owner skill: knowledge-manager (handover pattern owner). Freshness: realtime.

### C3. Inventory linked to assets

`inventory_items.linked_asset_ids` array (legacy text[]) plus implicit links via
`inventory_transactions` referencing parts pulled for logbook entries.

Asset Hub queries inventory by class. Shift Brain queries inventory at reorder
threshold. Logbook queries on parts pick.

Wrap as `v_asset_parts_truth`: per `asset_id` (canonical), the parts that fit,
their current stock, reorder state.

Owner skill: data-engineer. Freshness: realtime.

### C4. Worker skills

`skill_profiles` + `skill_badges` + `skill_exam_attempts`, plus skill_matrix.html
computes the displayed level live.

`v_worker_skill_truth`: per `(worker_name, discipline)`, current level + last
exam date + badge count. Skill match queries (e.g. for shift assignments) read
this view, not the underlying tables.

Owner skill: maintenance-expert. Freshness: realtime.

### C5. Worker identity / role

`worker_profiles` (auth_uid → display_name) + `hive_members` (per hive role).

Already converged after the C4 auth migration. Just needs a wrapper view so
edge functions don't write the JOIN every time.

`v_worker_truth`: per `(hive_id, worker_name)`, role, status, auth_uid,
display_name, email, joined_at.

Owner skill: multitenant-engineer. Freshness: realtime.

### C6. Knowledge entries (RAG corpus)

5 separate knowledge tables, all with pgvector embeddings:

- `pm_knowledge` (PM templates)
- `bom_knowledge` (BOM standards)
- `calc_knowledge` (engineering calc results)
- `fault_knowledge` (logbook history embedded)
- `skill_knowledge` (skill matrix content)

`semantic-search` edge function queries them via UNION ALL with the subquery
pattern (per ai-engineer skill). Each table is a legitimate distinct
knowledge domain.

Wrap them as `v_knowledge_truth` with `source` discriminator column so semantic
search reads one view, not five. Avoids the UNION ALL gotcha at the call site.

Owner skill: knowledge-manager + ai-engineer. Freshness: realtime.

### C7. Marketplace listings

`marketplace_listings` is already canonical. Wrap as `v_marketplace_listing_truth`
that joins seller verification badges (`marketplace_sellers`) and rolls up
inquiry counts so the buyer-facing surface reads one shape.

Owner skill: marketplace. Freshness: realtime.

### C8. Project state

`projects` + `project_items` + `project_progress_logs` + `project_roles` +
`project_change_orders`. Project Report compiles all 5; hive board pulls
progress; AI assistant pulls scope.

`v_project_truth`: per `project_id`, current state (% complete, days remaining,
SPI/CPI from progress logs, change-order delta, sign-off state).

Owner skill: maintenance-expert (PM strategy section). Freshness: realtime.

### C9. Achievements / XP

3 tables: `achievement_definitions`, `worker_achievements`, `achievement_xp_log`.
Plus a separate `community_xp` tally for community posts/replies.

`v_worker_xp_truth`: per worker, total XP from all sources, level, current tier,
next-tier XP delta, recent unlocks.

Owner skill: community + maintenance-expert. Freshness: realtime.

---

## ALIGNED (already canonical, just register)

### A1. `shift_plans` (shipped Phase 4)

Single source per (hive, shift_date, shift_window). The orchestrator upserts
draft, supervisor publishes. No scatter. Just register.

### A2. `asset_edges` (shipped Phase 0)

Single source for the asset graph. No scatter. Register.

### A3. `community_posts`, `community_replies`, `community_reactions`

Single source each. Realtime + soft-delete + public-flag pattern. Register.
The May 2026 community page work made this clean.

### A4. `engineering_calcs`

Single source for engineering calc history. Each row is a complete snapshot
(inputs + results + narrative JSONB) so agents can re-render without recomputing.
Register.

### A5. `external_sync` (CMMS bridge)

Single source per (system_type, external_id, entity_type). The asset_nodes
side has a `pm_asset_id` and `external_ids` JSONB but the canonical link state
is in `external_sync`. Register.

### A6. `ai_rate_limits` (just shipped with Asset Brain)

Single source per hive for AI call quotas. Register.

---

## The registry table

One Postgres table to hold the contracts. AI agents query this first when
asked about any registered domain.

```sql
CREATE TABLE canonical_sources (
  domain        text PRIMARY KEY,                   -- e.g. 'asset_truth'
  source_kind   text NOT NULL                       -- 'view'|'table'|'rpc'
                CHECK (source_kind IN ('view','table','rpc')),
  source_name   text NOT NULL,                      -- e.g. 'v_asset_truth'
  owner_skill   text NOT NULL,                      -- e.g. 'architect'
  freshness     text NOT NULL,                      -- 'realtime'|'1h_cache'|'daily_13_pht'|...
  contract      jsonb NOT NULL,                     -- declared columns + types
  description   text NOT NULL,                      -- human-readable purpose
  registered_at timestamptz NOT NULL DEFAULT now(),
  last_validated timestamptz                        -- updated by validator on PASS
);

GRANT SELECT ON canonical_sources TO anon, authenticated;
```

Initial rows: D1-D5 (5 drift fixes), C1-C9 (9 contracts), A1-A6 (6 already-clean
registrations). 20 entries total.

---

## The validator: `validate_canonical_sources.py`

Three checks:

1. **Drift detection** — for each domain in `canonical_sources`, scan all edge
   functions and HTML pages for direct queries against the underlying tables.
   If a domain has a canonical view but a consumer reads the underlying table
   directly, FAIL with the exact file:line and the canonical view name to
   substitute.

2. **Contract drift** — compare the live view's column list (introspected via
   `information_schema.columns`) to the contract JSONB. If columns drift, FAIL.

3. **Freshness SLA** — for views with non-realtime freshness, compare the most
   recent `_generated_at` row to the SLA. If stale, WARN.

Adds the validator to `run_platform_checks.py`. New baseline.

---

## The agent contract

One line added to the system prompt of every AI agent in `_shared/ai-chain.ts`
(and to `floating-ai.js` via the orchestrator):

> When asked about a registered domain (asset, risk, PM compliance, hive KPI,
> failure history, open work, worker skill, marketplace, project, achievement),
> read from its canonical source listed in the `canonical_sources` table.
> Do not query underlying tables directly for these concepts.

Plus a deterministic helper in each edge function:

```ts
async function canonicalSourceFor(domain: string): Promise<string> {
  const { data } = await db.from('canonical_sources').select('source_name').eq('domain', domain).maybeSingle();
  return data?.source_name || '';
}
```

---

## Recommended migration order

Priority by pain-now and unlock-value:

1. **D1 asset_truth** — unifies the 3 asset IDs. Unblocks all downstream work because every other domain references "asset". (1 session)
2. **D5 audit logs registration** — no schema change, just register the 3 + add the unified view. Quick win. (0.5 session)
3. **D2 risk_truth + Phase 5a model rebuild** — replaces the predictive.html disease, adds structured top_factors. (1 session)
4. **D3 pm_compliance_truth** — kills the 4-way math drift. (0.5 session)
5. **C1 failure_history**, **C2 open_work** — data-layer wrappers around `logbook`. Once these land, every consumer reads from views. (0.5 session each)
6. **D4 hive_kpi_truth** — wraps the cache, declares freshness SLA. (0.5 session)
7. **C3-C9** — convergent wrappers, one per session in any order.
8. **A1-A6** — registry-only, batch into one session.
9. **The registry table + validator** — built first so the work above can be validated as it lands. (0.5 session)

Total: ~10 sessions over the lifetime of this initiative. The registry +
validator is built first so each subsequent landing can prove correctness.

---

## Open questions before starting

1. **View vs materialized view** for cached truths (D4, D2). Materialized
   gives stable read performance but needs a refresh schedule. Default to
   regular view; promote to materialized when SLA breach observed.

2. **Backwards compatibility** during cutover. When `v_asset_truth` lands,
   should the legacy `assets` and `pm_assets` tables become `WITH UPDATABLE
   VIEW` so old code paths keep working, or do we ship the cutover as a
   coordinated migration of all readers?

3. **Service role vs RLS** on canonical views. Views inherit underlying RLS
   by default. Confirm each view's policy before AI agents read from it via
   service role (which bypasses RLS) vs via authenticated session.

4. **Naming**. `v_*_truth` is opinionated. Alternatives: `canonical_*`,
   `current_*`, or just `v_*`. The `_truth` suffix makes the contract
   intention loud at the call site. Vote your preference.

---

## Appendix A — Analytics Engine display surfaces (added 2026-05-12)

The user's directive: *"also everything in my analytics engine displays"*.
The earlier sections of this audit cover platform-wide silos. This appendix
zooms into a single page — `analytics.html` — and traces every tile rendered
across all 4 phases (30 tiles + 2 role quick-views) to its source today, the
proposed canonical, and the Tier (A–E) recommendation that closes the gap.

**Why this matters.** Analytics is the platform's most-read intelligence
surface. Each tile is a public claim. If the same number (MTBF for asset X,
PM compliance for hive Y) renders differently here than in Predictive,
Asset Hub, Shift Brain, or the AI assistant, the user loses trust in every
surface. The Fuel/Engine/Brain/Dashboard model only holds if **every tile on
this page can be traced to a registered canonical source by id**.

### A.1 Architecture today

```
analytics.html
   │  (one click) refreshAll() → fetch /functions/v1/analytics-orchestrator
   ▼
analytics-orchestrator (edge fn, 752 LOC)
   │
   ├── Postgres RPCs       (canonical, deterministic)
   │     get_mtbf_by_machine, get_mttr_by_machine,
   │     get_failure_frequency, get_downtime_pareto,
   │     get_repeat_failures            ──► v_logbook_truth
   │
   ├── v_pm_compliance_truth read       ──► canonical
   ├── v_logbook_truth read (OEE)       ──► canonical
   ├── v_risk_truth read (Phase 3/4 ctx)──► canonical
   │
   └── python-api /analytics            (silo)
         descriptive.py  → calc_oee / calc_parts_consumption /
                           calc_consequence_distribution / calc_availability
         diagnostic.py   → calc_failure_mode_distribution /
                           calc_pm_failure_correlation /
                           calc_skill_mttr_correlation /
                           calc_parts_availability_impact /
                           calc_repeat_failure_clustering /
                           calc_engineering_validation /
                           calc_rcm_consequence
         predictive.py   → calc_next_failure_dates / calc_pm_due_calendar /
                           calc_parts_stockout / calc_failure_trend /
                           calc_health_scores / calc_anomaly_baseline /
                           calc_parts_consumption_spike
         prescriptive.py → calc_priority_ranking /
                           calc_pm_interval_optimization /
                           calc_technician_assignment /
                           calc_parts_reorder /
                           calc_training_gaps
```

Where the orchestrator already pulls a Postgres RPC or a `v_*_truth` view, the
tile is **canonical**. Where the orchestrator hands raw rows to the Python
API and lets it recompute, the tile is **silo** — Python sees a snapshot,
applies its own logic, and Analytics is the only surface that ever sees the
result. No other surface can read or audit that derivation.

### A.2 Phase 1 — Descriptive (9 tiles)

| # | Tile (function in analytics.html) | Source today | Canonical? | Tier (if not) | Recommended fix |
|---|---|---|---|---|---|
| 1 | OEE — `renderOEE` | `v_logbook_truth` read in orchestrator → Python `calc_oee` | **Partial** — fuel canonical, formula silo | Tier D | Register `oee_iso_22400` formula in `canonical_formulas`; have RPC return identical result so Asset Hub + Reliability Workbench can read OEE without Python. |
| 2 | Availability — `renderAvailability` | Python `calc_availability` from raw logbook | Silo | Tier D | Add `get_availability_by_machine(hive_id, period_days)` RPC; replace Python call. Same window contract as MTBF/MTTR. |
| 3 | MTBF — `renderMTBF` | `get_mtbf_by_machine` RPC | **Canonical** ✓ | — | — |
| 4 | MTTR — `renderMTTR` | `get_mttr_by_machine` RPC | **Canonical** ✓ | — | — |
| 5 | PM Compliance — `renderPMCompliance` | `v_pm_compliance_truth` (hive mode) / Python (solo) | **Canonical** ✓ (with solo-mode allowlist) | — | Long-term: collapse solo branch by relaxing `v_pm_compliance_truth.hive_id IS NOT NULL` to include solo via NULL. |
| 6 | Downtime Pareto — `renderDowntimePareto` | `get_downtime_pareto` RPC | **Canonical** ✓ | — | — |
| 7 | Failure Frequency — `renderFailureFrequency` | `get_failure_frequency` RPC | **Canonical** ✓ | — | — |
| 8 | Repeat Failures — `renderRepeatFailures` | `get_repeat_failures` RPC | **Canonical** ✓ | — | — |
| 9 | Parts Consumption — `renderPartsConsumption` | Python `calc_parts_consumption` from `inventory_transactions` | Silo | Tier D + Tier A | Add `get_parts_consumption(hive_id, period_days)` RPC reading `v_inventory_items_truth` joined to inventory_transactions. Cross-surface with parts-tracker.html which has its own consumption math today. |

**Score**: 6 of 9 canonical. 3 silo tiles (OEE/Availability/Parts Consumption) are Tier D candidates.

### A.3 Phase 2 — Diagnostic (7 tiles)

| # | Tile | Source today | Canonical? | Tier (if not) | Recommended fix |
|---|---|---|---|---|---|
| 1 | RCM Consequence — `renderRCMConsequence` | Python `calc_rcm_consequence` from raw logbook | Silo | Tier D | This is a standards-mapped derivation (SAE JA1011 consequence categories). Belongs in `canonical_formulas` with the JA1011 cite. Add `get_rcm_consequence_distribution(...)` RPC. |
| 2 | Failure Mode Distribution — `renderFailureModeDistribution` | Python `calc_failure_mode_distribution` | Silo | Tier D | ISO 14224 failure taxonomy. Same pattern — register formula, ship RPC. |
| 3 | PM Failure Correlation — `renderPMFailureCorrelation` | Python `calc_pm_failure_correlation` (Spearman) | Silo | Tier D | Statistical method. Register `spearman_pm_failure` formula. RPC could call `corr()` in SQL or stay in Python but **versioned** behind `canonical_formulas.formula_id`. |
| 4 | Skill MTTR Correlation — `renderSkillMTTRCorrelation` | Python `calc_skill_mttr_correlation` | Silo | Tier A + D | Joins MTTR (canonical) to worker skill (silo today). Tier A `v_worker_skill_truth` is the missing fuel; once it lands, this tile can be a SQL join, not a Python recompute. |
| 5 | Parts Availability Impact — `renderPartsAvailabilityImpact` | Python `calc_parts_availability_impact` | Silo | Tier D + Tier A | Joins downtime to parts-out events. Both fuels exist (v_logbook_truth + inventory_transactions). Promote to SQL RPC. |
| 6 | Repeat Failure Clustering — `renderRepeatFailureClustering` | Python `calc_repeat_failure_clustering` | Silo | Tier D | Different from `get_repeat_failures` RPC — this clusters by failure_mode within rolling window. Either rename for clarity or unify into the existing RPC with a `cluster: true` flag. |
| 7 | Engineering Validation — `renderEngineeringValidation` | Python `calc_engineering_validation` | Silo | Tier D | Cross-checks logbook-reported root causes against engineering-design calculator history. Touches a second canonical (`engineering_calc_runs`). Worth its own dedicated RPC. |

**Score**: 0 of 7 canonical. **Diagnostic is the single biggest silo on the platform.** Every Tier 2 tile is a Python-only derivation. This is where Tier D (formula + standards registry) pays off most.

### A.4 Phase 3 — Predictive (7 tiles + 1 inline read)

| # | Tile | Source today | Canonical? | Tier (if not) | Recommended fix |
|---|---|---|---|---|---|
| 0 | (inline) Risk snapshot — top-N at-risk assets injected into Phase 3 context | `v_risk_truth` read in orchestrator | **Canonical** ✓ | — | — |
| 1 | Next Failure Dates — `renderNextFailureDates` | Python `calc_next_failure_dates` (Weibull-style projection) | Silo | Tier C | This is a **brain output**, not a fuel/engine read. Belongs in Tier C `canonical_agent_contracts` with a JSON Schema for the response. Same shape consumed by Predictive page must validate against the same schema. |
| 2 | PM Due Calendar — `renderPMDueCalendar` | Python `calc_pm_due_calendar` reads pm_completions+pm_scope_items | Silo (orchestration), Canonical (fuels) | Tier D | Fuels canonical via `v_pm_compliance_truth`. Just needs `get_pm_due_window(hive_id, days_ahead)` RPC. |
| 3 | Parts Stockout — `renderPartsStockout` | Python `calc_parts_stockout` (consumption rate × on_hand) | Silo | Tier C | Brain output. Schema with: `part_id, days_until_stockout, confidence, basis`. inventory.html consumes the same metric independently today. |
| 4 | Failure Trend — `renderFailureTrend` | Python `calc_failure_trend` (rolling window) | Silo | Tier D | Time series derivation. Could be a SQL window function RPC. |
| 5 | Health Scores — `renderHealthScores` | Python `calc_health_scores` (composite of MTBF/MTTR/PM compliance) | Silo (computed) but consumed by Predictive + Asset Hub | Tier C + Tier D | This is the **most-read derived metric in the platform** (Predictive heatmap reads it from `v_risk_truth`, Asset Hub reads `health_score` column, Analytics recomputes). Critical to register as a formula with a single SQL implementation. |
| 6 | Anomaly Baseline — `renderAnomalyBaseline` | Python `calc_anomaly_baseline` (stddev band around historical) | Silo | Tier C + Tier D | Brain output (statistical baseline). Already partially consumed by `sensor-readings-ingest` quality_flag logic — those two should share the same baseline definition, not derive independently. |
| 7 | Parts Spike — `renderPartsSpike` (calc_parts_consumption_spike) | Python | Silo | Tier C + Tier D | Anomaly-on-consumption. Same pattern as #6. |

**Score**: 1 of 8 canonical (the inline risk snapshot). 7 silo tiles, of which 4 are statistical/predictive brain outputs that belong in Tier C, and 3 are time-series derivations that belong in Tier D.

### A.5 Phase 4 — Prescriptive (6 tiles)

| # | Tile | Source today | Canonical? | Tier (if not) | Recommended fix |
|---|---|---|---|---|---|
| 1 | Action Plan — `renderActionPlan` (AI synthesis) | LLM call inside orchestrator over Phase 1–3 results | **Brain output** — no canonical contract today | Tier C | `canonical_agent_contracts` schema for `analytics_action_plan_v1`: `{ summary, priorities: [{asset, action, why, urgency, eta}] }`. AI prompt is registered, JSON Schema-validated, versioned. Same contract reusable by Shift Brain handover, Hive feed, AMC briefings. |
| 2 | Priority Ranking — `renderPriorityRanking` | Python `calc_priority_ranking` | Silo | Tier C + Tier D | Composite scoring formula. Register in Tier D, output schema in Tier C. |
| 3 | PM Optimization — `renderPMOptimization` (calc_pm_interval_optimization) | Python | Silo | Tier D | RCM-3 interval optimization. Standards-mapped (SAE JA1011 §6) → Tier D registry. |
| 4 | Tech Assignment — `renderTechAssignment` (calc_technician_assignment) | Python | Silo | **Tier A** | Best-tech-for-this-job depends on Tier A `v_worker_skill_truth` + new `v_worker_assignment_truth`. **This is the canonical use case for Tier A.** Without it, Analytics, hive.html, and pm-scheduler each pick "best tech" differently. |
| 5 | Parts Reorder — `renderPartsReorder` (calc_parts_reorder) | Python (joins consumption rate + lead time + safety stock) | Silo | Tier D | Inventory-control formula. Standards: SMRP 4.2 (parts management). Register formula. |
| 6 | Training Gaps — `renderTrainingGaps` (calc_training_gaps) | Python (joins MTTR by discipline to skill matrix) | Silo | **Tier A** | Depends on Tier A `v_worker_skill_truth`. Today reads skill_badges directly + recomputes coverage. Skill Matrix page renders gap from its own logic. Two surfaces, two answers. |

**Score**: 0 of 6 canonical. 2 tiles depend on Tier A (worker_skill / worker_assignment), 4 depend on Tier D (formula registry), 2 also need Tier C (brain output contracts).

### A.6 Role quick-view cards (top of page)

| Card | Surface | Source today | Canonical? |
|---|---|---|---|
| 🔧 Field Tech | PM tasks needing attention + critical parts + next failure risk | Reuses Phase 3/4 tiles | **Inherits** canonicality of tiles above |
| 👷 Supervisor | Worst MTBF/MTTR + PM% + overdue + training gap + AI summary | Reuses Phase 1/3/4 tiles | **Inherits** |

These cards don't introduce new computations — they re-read the cached phase results. So whatever canonicality the underlying tiles achieve, the role views automatically inherit. **This is the right pattern** — additional surfaces should reuse, not recompute.

### A.7 Aggregate scoreboard

| Phase | Tiles | Canonical | Silo | % canonical |
|---|---|---|---|---|
| 1 — Descriptive | 9 | 6 | 3 | 67% |
| 2 — Diagnostic | 7 | 0 | 7 | 0% |
| 3 — Predictive | 8 | 1 | 7 | 13% |
| 4 — Prescriptive | 6 | 0 | 6 | 0% |
| **Total** | **30** | **7** | **23** | **23%** |

**23%** of the platform's most-read intelligence surface is currently
canonical. The other 77% is Python-recomputed each refresh, with no
versioned formula contract and no shared output schema. Any other surface
that wants the same number has to recompute it independently — which is
exactly the "feels off" pattern that triggered this entire initiative.

### A.8 Mapping the gaps to the Tier roadmap

| Tier | Closes for Analytics | Tiles unlocked |
|---|---|---|
| **Tier A** — worker_truth + worker_skill_truth + worker_assignment_truth | Replaces Python skill+assignment recomputes | Skill MTTR Correlation (P2), Tech Assignment (P4), Training Gaps (P4) — **3 tiles** |
| **Tier B** — project_truth + knowledge_truth | (Indirect — feeds AMC briefings card on home, not Analytics tiles directly) | 0 tiles directly |
| **Tier C** — `canonical_agent_contracts` (JSON Schema registry for brain outputs) | Locks down LLM/statistical output shape: action_plan, next_failure_dates, parts_stockout, health_scores, anomaly_baseline, parts_spike, priority_ranking | **7 tiles** |
| **Tier D** — `canonical_formulas` + `canonical_standards` registries | Versions every derivation: OEE, Availability, Parts Consumption, RCM Consequence, Failure Mode Distribution, PM Failure Correlation, Repeat Failure Clustering, Engineering Validation, Parts Availability Impact, PM Due Calendar, Failure Trend, Health Scores, Priority Ranking, PM Optimization, Parts Reorder | **15 tiles** (overlaps Tier C for some) |
| **Tier E** — audit_unified + display_state | (Indirect — better audit trail of when each tile was computed) | 0 tiles directly |

**Shipping all of Tier A + C + D would lift Analytics from 23% to ~95%
canonical** — the only remaining non-canonical tile would be the AI Action
Plan prose itself, which is correctly LLM-derived (not a deterministic
metric) and whose canonicality is its **contract** (Tier C schema), not its
computation.

### A.9 Recommended sequencing

1. **Tier A (worker truths)** — 4.5 h.
   Lift 3 Analytics tiles + canonicalises every "who should do X" decision
   across the platform.

2. **Tier C scaffolding + 3 highest-value brain contracts** — 3 h.
   Schema registry table + JSON Schema validator + the 3 contracts most
   re-used outside Analytics:
   - `analytics_action_plan_v1` (reused by Shift Brain handover, Hive feed)
   - `next_failure_forecast_v1` (reused by Predictive page, Asset Hub trend)
   - `health_score_v1` (reused by Predictive heatmap, Asset Hub, hive map)

3. **Tier D scaffolding + register the 6 ISO 14224 / ISO 22400 / SMRP
   formulas** — 4 h.
   Registry table + the 6 standards-grade formulas (OEE, Availability,
   MTBF, MTTR, PM Compliance, RCM Consequence). MTBF/MTTR/PM Compliance are
   already canonical at the RPC level — registering them just adds the
   `formula_id → standard_cite → SQL implementation` audit row.

4. **Tier D backfill — remaining 9 formulas** — 6 h.
   Lower-priority statistical formulas (Spearman correlations, repeat
   failure clustering, parts reorder logic). Less reused outside Analytics
   so the urgency is lower, but completes the ratchet.

5. **Validator** — `validate_analytics_display_canonicality.py` (new, 67th
   gate after Silo Monitor → 68th). FAILs CI if a new `render*` function in
   analytics.html exists without either:
   - An entry in the canonical_formulas registry (formula_id comment in
     the renderer), or
   - An entry in canonical_agent_contracts (schema_id comment), or
   - An explicit `// canonical-allow: <reason>` comment.

   The validator's existence guarantees that every future tile added to
   Analytics either rides on a registered canonical, or carries an
   allowlist note that's visible in code review.

### A.10 The longer arc

Analytics is the **dashboard layer** in the Fuel → Engine → Brain →
Dashboard → Driver metaphor. By the end of Tiers A + C + D it becomes a
**pure read surface** — every tile shows a registered canonical, no tile
recomputes anything privately. At that point:

- Adding a new analytics tile is a 3-line change: write the renderer,
  reference the formula_id or contract_id, ship.
- The AI assistant ("explain my MTBF") and Analytics ("MTBF chart") and
  Predictive ("MTBF trend") all read the same row from the same RPC. No
  divergence is structurally possible.
- A new platform surface (next quarter's "Reliability Workbench v2") can
  render any Analytics metric without owning any new derivation code.

This is the end state the canonical layers study converges to. The
Analytics Engine displays are both the most demanding and the most-public
test of whether the architecture holds.

---

End of audit.
