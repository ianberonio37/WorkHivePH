-- Canonical SMRP PM-compliance RPC — single source of truth (2026-06-10)
-- ============================================================================
-- Problem: "PM compliance" was computed in TWO incompatible ways:
--   - analytics-orchestrator / descriptive.py: SMRP 2.1.1 = completed/scheduled,
--     frequency-aware (the CORRECT value, ~88.5%).
--   - pm-scheduler.html: on-track assets / total assets (a DIFFERENT metric that
--     merely shares the label) — showed 60%, then 0% after the frequency_days
--     fix surfaced all the weekly PMs as due-soon, while the real SMRP value is
--     88.5% (above the 80% Stair-2 gate). The page told the supervisor they were
--     FAILING the maturity gate when they were passing it.
--
-- Fix: ONE canonical SMRP-compliance function both surfaces read, so they can
-- never disagree. Replicates descriptive.py calc_pm_compliance exactly:
--   per scope item: scheduled = max(1, floor(period / frequency_days));
--                   completed = min(completions_in_period, scheduled);
--   per asset:      sum(scheduled), sum(completed), pct = completed/scheduled;
--   overall_pct  =  mean of per-asset pct (matches np.mean in descriptive.py).
-- Reuses the (now-corrected) v_pm_scope_items_truth.frequency_days mapping, so
-- there is a single frequency map for the whole platform.
-- ============================================================================

BEGIN;

-- canonical-allow: computes the SMRP 2.1.1 compliance metric from the canonical
-- v_pm_scope_items_truth (scheduled) + pm_completions ledger (completed). It is
-- the single canonical PM-compliance source; consumed by pm-scheduler.html and
-- analytics-orchestrator. SECURITY DEFINER to read the RLS-protected
-- pm_completions ledger after an explicit hive-membership gate.
CREATE OR REPLACE FUNCTION public.get_pm_compliance_smrp(
  p_hive_id     uuid,
  p_period_days int DEFAULT 90
)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_is_member boolean;
  v_result    jsonb;
BEGIN
  -- ── Hive isolation gate ──────────────────────────────────────────────
  -- authenticated callers MUST be active members; service_role (server-to-
  -- server, e.g. analytics-orchestrator) has no auth.uid() and is trusted.
  -- EXECUTE is granted only to authenticated + service_role (never anon), so
  -- the null-auth.uid() branch is reachable only by service_role.
  IF auth.uid() IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1 FROM public.hive_members
      WHERE hive_id  = p_hive_id
        AND auth_uid = auth.uid()
        AND status   = 'active'
    ) INTO v_is_member;

    IF NOT v_is_member THEN
      RAISE EXCEPTION
        'get_pm_compliance_smrp: caller is not an active member of hive %', p_hive_id
        USING ERRCODE = '42501';  -- insufficient_privilege
    END IF;
  END IF;

  WITH per_item AS (
    SELECT
      s.pm_asset_id,
      s.asset_name,
      GREATEST(1, (p_period_days / s.frequency_days)) AS scheduled,
      LEAST(
        (SELECT count(*) FROM public.pm_completions pc
          WHERE pc.scope_item_id = s.scope_item_id
            AND pc.status        = 'done'
            AND pc.completed_at  >= now() - (p_period_days || ' days')::interval),
        GREATEST(1, (p_period_days / s.frequency_days))
      ) AS completed
    FROM public.v_pm_scope_items_truth s
    WHERE s.hive_id = p_hive_id
  ),
  per_asset AS (
    -- group by pm_asset_id (NOT name): distinct physical assets can share a
    -- model name (AC-001/AC-002/AC-003 = "Atlas Copco GA75+ VSD"); the per-asset
    -- mean must treat them separately to match analytics-orchestrator.
    SELECT
      pm_asset_id,
      max(asset_name) AS asset_name,
      sum(scheduled)::int AS scheduled,
      sum(completed)::int AS completed,
      round(sum(completed)::numeric / NULLIF(sum(scheduled), 0) * 100, 1) AS compliance_pct
    FROM per_item
    GROUP BY pm_asset_id
  )
  SELECT jsonb_build_object(
    'standard',        'SMRP Metric 2.1.1',
    'period_days',     p_period_days,
    'overall_pct',     round(avg(compliance_pct), 1),
    'total_scheduled', COALESCE((SELECT sum(scheduled) FROM per_item), 0),
    'total_completed', COALESCE((SELECT sum(completed) FROM per_item), 0),
    'asset_count',     count(*),
    'compliance_by_asset', COALESCE(jsonb_agg(
        jsonb_build_object(
          'asset_name',     asset_name,
          'scheduled',      scheduled,
          'completed',      completed,
          'compliance_pct', compliance_pct
        ) ORDER BY compliance_pct
      ), '[]'::jsonb)
  ) INTO v_result
  FROM per_asset;

  RETURN COALESCE(v_result, jsonb_build_object(
    'standard','SMRP Metric 2.1.1','period_days',p_period_days,
    'overall_pct',NULL,'total_scheduled',0,'total_completed',0,
    'asset_count',0,'compliance_by_asset','[]'::jsonb,
    'note','No PM scope items found for this hive.'));
END;
$$;

REVOKE ALL ON FUNCTION public.get_pm_compliance_smrp(uuid, int) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_pm_compliance_smrp(uuid, int) TO authenticated, service_role;

COMMENT ON FUNCTION public.get_pm_compliance_smrp(uuid, int) IS
  'Canonical SMRP 2.1.1 PM-compliance (completed/scheduled, frequency-aware via v_pm_scope_items_truth.frequency_days). Single source of truth for pm-scheduler.html + analytics-orchestrator. SECURITY DEFINER + hive-membership gate (authenticated members; service_role server-to-server). Returns {overall_pct, total_scheduled, total_completed, asset_count, compliance_by_asset[]}.';

COMMIT;
