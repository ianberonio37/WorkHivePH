-- get_pm_compliance_smrp: SOLO LANE (VP7's walk, 2026-09-03).
-- The RPC hard-required hive membership, so a signed-in SOLO owner's analytics page got a
-- 42501->403 and the compliance card could never load (the write-only-trap class, on an RPC:
-- the solo lane got PM data everywhere else but no way to ask this question of it).
-- p_hive_id IS NULL now means "the caller's own solo scope": auth required, membership check
-- skipped (identity IS the scope), rows = hive_id IS NULL AND pm_assets.auth_uid = auth.uid().
-- Hive behavior is byte-identical to the previous definition.

CREATE OR REPLACE FUNCTION public.get_pm_compliance_smrp(p_hive_id uuid, p_period_days integer DEFAULT 90)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_is_member boolean;
  v_result    jsonb;
BEGIN
  IF p_hive_id IS NULL THEN
    -- solo lane: the caller asks about their OWN hiveless scope; anon has no scope to ask about
    IF auth.uid() IS NULL THEN
      RAISE EXCEPTION
        'get_pm_compliance_smrp: solo compliance requires a signed-in caller'
        USING ERRCODE = '42501';
    END IF;
  ELSIF auth.uid() IS NOT NULL THEN
    -- Hive isolation gate (authenticated members; service_role server-to-server).
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
    WHERE (p_hive_id IS NOT NULL AND s.hive_id = p_hive_id)
       OR (p_hive_id IS NULL AND s.hive_id IS NULL AND EXISTS (
             SELECT 1 FROM public.pm_assets pa
             WHERE pa.id = s.pm_asset_id AND pa.auth_uid = auth.uid()))
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
    'note','No PM scope items found for this scope.'));
END;
$$;
