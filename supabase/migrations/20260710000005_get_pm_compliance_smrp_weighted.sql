-- Analytics Engine arc F1d (2026-07-10): PM Compliance overall_pct = WEIGHTED (SMRP 2.1.1).
--
-- BUG: get_pm_compliance_smrp returned overall_pct = round(avg(compliance_pct)) — the UNWEIGHTED
-- mean of per-asset %, which lets a 1-PM asset count the same as a 20-PM asset. The analytics
-- summary tile then showed the unweighted hero (e.g. Lucena 19.6%) next to the weighted count
-- "21 of 119 PMs on time" (=17.6%) — a self-contradicting tile. SMRP Metric 2.1.1 PM Compliance
-- is completed/scheduled across the whole program (WEIGHTED). journey_trace.py's terminus already
-- asserts overall_pct == round(100·total_completed/total_scheduled, 1) — the RPC just didn't honor it.
--
-- FIX: overall_pct = round(100·Σcompleted/Σscheduled, 1) (weighted), matching descriptive.calc_oee's
-- sibling descriptive.calc_pm_compliance (also switched to the weighted total this arc) and the
-- "N of M PMs on time" count the UI shows beside it. Per-asset compliance_pct + totals unchanged.
--
-- Blast radius (deep-walked): overall_pct consumers = analytics.html (hero/detail/role), analytics-
-- report.html, pm-scheduler.html, analytics-orchestrator (override), the DOM-parity oracle (moves
-- with the value), descriptive.py. NOT consumed by hive_readiness/the maturity-stairway (those read
-- per-asset compliance_pct / is_overdue), so hive progression is unaffected.

CREATE OR REPLACE FUNCTION public.get_pm_compliance_smrp(p_hive_id uuid, p_period_days integer DEFAULT 90)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_is_member boolean;
  v_result    jsonb;
BEGIN
  -- Hive isolation gate (authenticated members; service_role server-to-server).
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
        USING ERRCODE = '42501';
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
    -- WEIGHTED: total completed / total scheduled across the whole PM program (SMRP 2.1.1),
    -- NOT the unweighted mean of per-asset %.
    'overall_pct',     round(100.0 * COALESCE((SELECT sum(completed) FROM per_item), 0)::numeric
                             / NULLIF((SELECT sum(scheduled) FROM per_item), 0), 1),
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
$function$;

COMMENT ON FUNCTION public.get_pm_compliance_smrp(uuid, integer) IS
  'Canonical SMRP 2.1.1 PM-compliance. overall_pct = WEIGHTED total_completed/total_scheduled '
  '(frequency-aware via v_pm_scope_items_truth.frequency_days). Single source of truth for '
  'pm-scheduler.html + analytics-orchestrator. SECURITY DEFINER + hive-membership gate. '
  'Returns {overall_pct, total_scheduled, total_completed, asset_count, compliance_by_asset[]}.';
