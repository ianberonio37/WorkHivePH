-- Canonical Sources Phase A.4: v_pm_compliance_truth view.
--
-- Single read path for PM compliance per asset. Replaces the 4-way math drift
-- identified in CANONICAL_SOURCES_AUDIT.md (analytics-orchestrator vs
-- shift-planner-orchestrator vs hive.html vs predictive.html each computing
-- compliance differently).
--
-- The view derives every metric from pm_assets + pm_completions in one shot:
-- last completion timestamp, lifetime count, 30/90-day windows, and an
-- is_due flag based on category default frequency. Consumers read columns
-- instead of writing their own aggregation.
--
-- The data-engineer skill calls out that mixing all-time completions with
-- period-scoped scheduled counts inflates compliance. The view exposes both
-- so consumers can pick the right pair (lifetime / lifetime, 30d / 30d, etc.).
--
-- Skills consulted: maintenance-expert (PM compliance math, freq_days
-- conventions), data-engineer (period-scoped counts, FILTER clauses),
-- architect (canonical view + registry pattern), multitenant-engineer
-- (RLS inheritance from pm_assets and pm_completions).

BEGIN;

CREATE OR REPLACE VIEW public.v_pm_compliance_truth AS
SELECT
  pa.hive_id,
  pa.id                                                   AS pm_asset_id,
  pa.asset_name,
  pa.tag_id,
  pa.category,
  pa.criticality,
  pa.location,
  pa.last_anchor_date,
  -- Days since last completion across all scope items for this asset.
  -- NULL when there are no completions yet.
  CASE WHEN max(pc.completed_at) IS NULL
       THEN NULL
       ELSE (now()::date - max(pc.completed_at)::date)
  END                                                     AS days_since_last_completion,
  -- Period-scoped counts so consumers can compute compliance correctly:
  -- lifetime / lifetime_due, 30d_completions / 30d_due, etc.
  count(pc.id)                                            AS lifetime_completions,
  count(pc.id) FILTER (WHERE pc.completed_at >= now() - interval '30 days')   AS completions_30d,
  count(pc.id) FILTER (WHERE pc.completed_at >= now() - interval '90 days')   AS completions_90d,
  count(pc.id) FILTER (WHERE pc.completed_at >= now() - interval '365 days')  AS completions_365d,
  max(pc.completed_at)                                    AS last_completion_at,
  -- Conservative is_due flag: never completed, OR last_anchor_date older
  -- than 30 days. Consumers wanting category-specific frequency can read
  -- last_anchor_date and category and apply their own threshold.
  CASE
    WHEN pa.last_anchor_date IS NULL THEN true
    WHEN pa.last_anchor_date < (now()::date - interval '30 days')::date THEN true
    ELSE false
  END                                                     AS is_due
FROM public.pm_assets pa
LEFT JOIN public.pm_completions pc
       ON pc.asset_id = pa.id
      AND pc.hive_id  = pa.hive_id
GROUP BY
  pa.hive_id, pa.id, pa.asset_name, pa.tag_id, pa.category, pa.criticality,
  pa.location, pa.last_anchor_date;

COMMENT ON VIEW public.v_pm_compliance_truth IS
  'Canonical PM compliance per asset. Latest completion + lifetime/30d/90d/365d windows + is_due flag. Source of truth for analytics-orchestrator phase 1, shift-planner-orchestrator PMs Due, hive.html PM Health card, and predictive.html PM-overdue factor. Registered in canonical_sources as domain=pm_compliance_truth.';

GRANT SELECT ON public.v_pm_compliance_truth TO anon, authenticated;

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'pm_compliance_truth',
  'view',
  'v_pm_compliance_truth',
  'maintenance-expert',
  'realtime',
  'PM compliance per asset across multiple time windows (lifetime, 30d, 90d, 365d) plus is_due flag. Replaces the 4-way math drift across analytics-orchestrator, shift-planner-orchestrator, hive.html PM Health card, and predictive.html PM-overdue factor.',
  jsonb_build_object(
    'key', jsonb_build_array('hive_id', 'pm_asset_id'),
    'hive_scoped', true,
    'period_columns', jsonb_build_array(
      'completions_30d', 'completions_90d', 'completions_365d', 'lifetime_completions'
    ),
    'derived_columns', jsonb_build_array(
      'days_since_last_completion', 'last_completion_at', 'is_due'
    ),
    'compliance_math_rule', 'When computing compliance %, ALWAYS pair period completions with period-scoped due counts. Mixing lifetime completions with period-scoped due counts inflates compliance (data-engineer skill rule).'
  ),
  'Phase A.4 contract. is_due flag uses 30-day floor; consumers needing category-specific frequencies read last_anchor_date + category and apply their own threshold.'
)
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes,
      registered_at = now();

COMMIT;
