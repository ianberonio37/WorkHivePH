-- PM compliance named the model and never the machine.
--
-- WHAT IS WRONG. `get_pm_compliance_smrp` emits one entry per asset as
-- {asset_name, scheduled, completed, compliance_pct} - and an asset's NAME is its model, not its
-- identity. On a plant floor the identity is the TAG: the code stencilled on the nameplate that a
-- technician reads off the machine.
--
-- MEASURED on the live database (2026-09-15):
--
--   distinct asset_name in v_pm_scope_items_truth       51
--   distinct pm_asset_id                               100
--   (hive, asset_name) groups covering MORE than one asset   24
--
-- So on average a name covers two machines, and in 24 measured cases a single name in a single hive
-- covers several. analytics.html records what that looks like in its own comment: the RPC returns
-- "Yaskawa A1000 2/5 40%" twice and "Cleaver-Brooks CB-700-200 9/17 52.9%" twice - two different
-- machines sharing a model name, with nothing in the payload to tell them apart.
--
-- WHY IT MATTERS MORE THAN A MISSING FIELD. This is the card that turns into crew assignments. Printing
-- two identical lines claims a distinction the page cannot support, so the page currently FOLDS them into
-- one line saying how many assets it covers - which is honest and costs the per-machine reading, the
-- whole point of a per-asset breakdown. A supervisor is told two machines are failing their schedule and
-- cannot be told WHICH two.
--
-- And the tag was never missing from the data: `v_pm_scope_items_truth` has carried `asset_tag` all
-- along. The function simply never selected it. analytics.html:1957-1963 says so at the call site and
-- names the fix: "A tag in the payload is the real fix and that is a migration."
--
-- WHAT CHANGES. `asset_tag` is carried through per_item and per_asset and added to each
-- compliance_by_asset entry. Nothing is removed and no key is renamed, so every existing consumer -
-- analytics.html, pm-scheduler.html, analytics-orchestrator, and the three validators that read this
-- RPC - keeps reading exactly what it reads today; the fold in analytics.html can then key on the tag
-- and show each machine as itself. The hive-isolation gate, the solo lane, the SMRP weighting and the
-- empty-scope fallback are untouched.

CREATE OR REPLACE FUNCTION public.get_pm_compliance_smrp(p_hive_id uuid, p_period_days integer DEFAULT 90)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
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
      s.asset_tag,          -- the machine's identity, as opposed to its model (2026-09-15)
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
      max(asset_tag)  AS asset_tag,
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
          -- Added 2026-09-15: a name is the model, a tag is the machine. 24 (hive, name) groups on this
          -- database cover more than one asset, so a payload keyed on the name alone cannot say WHICH
          -- machine is failing its schedule - on the card that becomes crew assignments.
          'asset_tag',      asset_tag,
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
$function$;
