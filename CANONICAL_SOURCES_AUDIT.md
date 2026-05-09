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

End of audit.
