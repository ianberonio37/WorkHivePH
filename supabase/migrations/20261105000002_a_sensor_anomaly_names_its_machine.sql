-- ★THE HOME SAID "vibration_mm_s flagged anomaly" AND NEVER WHICH MACHINE (2026-11-05, GJ J17 hand-off 3).
-- get_hive_dashboard handed the home's Today card a sensor anomaly as (asset_id, parameter, recorded_at): the card
-- headlined the parameter's code and its button linked to asset-hub.html?id=<asset>, a parameter asset-hub never
-- reads, so it opened the hub's front page. A worker told "a reading is 3-sigma outside the baseline. Inspect." could
-- not tell which machine to walk to. The payload now carries the machine's name, the reading and its unit.

CREATE OR REPLACE FUNCTION public.get_hive_dashboard(p_hive_id uuid, p_day_start timestamp with time zone DEFAULT date_trunc('day'::text, now()))
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_is_member boolean;
  v_result    jsonb;
BEGIN
  -- â”€â”€ Hive isolation gate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  SELECT EXISTS (
    SELECT 1 FROM public.hive_members
    WHERE hive_id  = p_hive_id
      AND auth_uid = auth.uid()
      AND status   = 'active'
  ) INTO v_is_member;

  IF NOT v_is_member THEN
    RAISE EXCEPTION
      'get_hive_dashboard: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';  -- insufficient_privilege
  END IF;

  -- â”€â”€ Consolidated board payload (mirrors index.html dashboard loader) â”€â”€
  SELECT jsonb_build_object(

    -- Open jobs: top-5 detail + true count (count drives the tile)
    'open_jobs', COALESCE((
      SELECT jsonb_agg(j) FROM (
        SELECT id, machine, category, maintenance_type, status, created_at, date
        FROM public.v_logbook_truth
        WHERE hive_id = p_hive_id AND status = 'Open'
        ORDER BY created_at DESC NULLS LAST
        LIMIT 5
      ) j
    ), '[]'::jsonb),
    'open_jobs_count', (
      SELECT count(*) FROM public.v_logbook_truth
      WHERE hive_id = p_hive_id AND status = 'Open'
    ),

    -- Risk alerts: top-5 critical/high detail + true count
    'risks', COALESCE((
      SELECT jsonb_agg(r) FROM (
        SELECT asset_name, risk_level, risk_score, mtbf_days, generated_at
        FROM public.v_risk_truth
        WHERE hive_id = p_hive_id AND risk_level IN ('critical','high')
        ORDER BY risk_score DESC NULLS LAST
        LIMIT 5
      ) r
    ), '[]'::jsonb),
    'risks_count', (
      SELECT count(*) FROM public.v_risk_truth
      WHERE hive_id = p_hive_id AND risk_level IN ('critical','high')
    ),

    -- Low stock: the canonical is_low_stock rows themselves (capped at 100 to
    -- mirror the client's old limit(100) inventory fetch). The client derives
    -- BOTH the tile count (.length) AND the out-of-stock candidate
    -- (.filter(qty_on_hand <= 0)) from this array â€” same as the old
    -- invRaw.filter(is_low_stock) path, so behavior is parity-equal.
    'low_stock_items', COALESCE((
      SELECT jsonb_agg(i) FROM (
        SELECT part_name, qty_on_hand, reorder_point
        FROM public.v_inventory_items_truth
        WHERE hive_id = p_hive_id AND is_low_stock = true
        LIMIT 100
      ) i
    ), '[]'::jsonb),

    -- PM overdue: DISTINCT assets with â‰¥1 OVERDUE scope item, read from the
    -- frequency-aware canonical per-scope-item view so this matches
    -- pm-scheduler.html #stat-overdue EXACTLY. (Was count(is_due) from
    -- v_pm_compliance_truth â€” a flat-30-day anchor proxy that over-counted.)
    'low_stock_count', (
      SELECT count(*) FROM public.v_inventory_items_truth
      WHERE hive_id = p_hive_id AND is_low_stock
    ),

    'pm_overdue_count', (
      SELECT count(DISTINCT pm_asset_id) FROM public.v_pm_scope_items_truth
      WHERE hive_id = p_hive_id AND is_overdue = true
    ),

    -- The denominator for pm_overdue_count. Without it the tile states a bare 28, which a reader
    -- cannot tell from 28-of-500 (a backlog) or 28-of-30 (a stopped PM programme).
    'pm_asset_total', (
      SELECT count(DISTINCT pm_asset_id) FROM public.v_pm_scope_items_truth
      WHERE hive_id = p_hive_id
    ),

    -- Top CRITICAL asset with an overdue scope item (most-overdue first),
    -- drives the home "Critical PM Overdue" Today's-One-Thing nudge. Added
    -- 2026-06-07: the nudge was dead on the RPC path because the client only
    -- had this signal in its legacy pmAssets fallback list.
    'critical_pm_overdue', (
      SELECT to_jsonb(c) FROM (
        SELECT asset_name, asset_tag, pm_asset_id, min(days_until_due) AS worst_days_until_due
        FROM public.v_pm_scope_items_truth
        WHERE hive_id = p_hive_id AND is_overdue = true
          AND lower(asset_criticality) = 'critical'  -- seed casing is title-case ('Critical')
        GROUP BY asset_name, asset_tag, pm_asset_id
        ORDER BY worst_days_until_due ASC
        LIMIT 1
      ) c
    ),

    -- Hive Activity Today
    'closed_today', (
      SELECT count(*) FROM public.v_logbook_truth
      WHERE hive_id = p_hive_id AND status = 'Closed' AND closed_at >= p_day_start
    ),
    'pm_done_today', (
      SELECT count(*) FROM public.pm_completions
      WHERE hive_id = p_hive_id AND status = 'done' AND completed_at >= p_day_start
    ),

    -- Today's One Thing signals (latest single row each, or null)
    'amc_pending', (
      SELECT to_jsonb(a) FROM (
        SELECT amc_id, shift_date, summary, headline, status
        FROM public.v_amc_truth
        WHERE hive_id = p_hive_id AND status = 'pending' AND shift_date >= (now() AT TIME ZONE 'Asia/Manila')::date
        ORDER BY shift_date ASC
        LIMIT 1
      ) a
    ),
    'sensor_anomaly', (
      SELECT to_jsonb(s) FROM (
        SELECT st.asset_id, an.name AS machine, st.parameter, st.value, st.unit,
               st.quality_flag, st.recorded_at, st.is_anomaly
        FROM public.v_sensor_truth st
        LEFT JOIN public.asset_nodes an ON an.id = st.asset_id AND an.deleted_at IS NULL
        WHERE st.hive_id = p_hive_id AND st.is_anomaly = true
          AND st.recorded_at >= now() - interval '24 hours'
        ORDER BY st.recorded_at DESC
        LIMIT 1
      ) s
    ),
    'signature_alert', (
      SELECT to_jsonb(g) FROM (
        SELECT alert_id, machine, title, severity, detected_at
        FROM public.v_alert_truth
        WHERE hive_id = p_hive_id AND alert_kind = 'signature' AND severity = 'critical'
        ORDER BY detected_at DESC
        LIMIT 1
      ) g
    )
  ) INTO v_result;

  RETURN v_result;
END;
$function$;
