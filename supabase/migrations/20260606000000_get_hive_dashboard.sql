-- get_hive_dashboard(hive_id) — fan-out collapse for the home (index.html) board.
-- ============================================================================
-- The authenticated home load fires 11 separate PostgREST reads against the
-- canonical truth views (open-jobs detail + count, risk detail + count,
-- low-stock, PM-overdue, closed-today, pm-done-today, and the three
-- "Today's One Thing" probes: AMC / sensor anomaly / signature alert).
-- This RPC returns all 11 signals in ONE round-trip as a single jsonb object.
--
-- WHY IT IS PARITY-SAFE: every sub-select reads the EXACT SAME canonical view
-- (v_logbook_truth / v_risk_truth / v_inventory_items_truth /
-- v_pm_compliance_truth / pm_completions / v_amc_truth / v_sensor_truth /
-- v_alert_truth) with the same filters the client used, so the numbers are
-- identical by construction. tests/journey-home-fanout-parity.spec.ts proves
-- RPC output == the separate canonical queries.
--
-- HIVE ISOLATION (critical): SECURITY DEFINER bypasses RLS, so this function
-- MUST verify the caller is an active member of p_hive_id via auth.uid()
-- before returning anything — otherwise any authenticated user could read any
-- hive's dashboard by passing its UUID. Canonical membership-join pattern from
-- the multitenant-engineer skill.
--
-- SCOPE: hive mode only. Solo (no-hive) home keeps its existing worker_name
-- scoped query path — that path is only ~4 calls and uses a different scope
-- column, so it stays as-is. The client calls this RPC only when HIVE_ID is set
-- and falls back to the legacy multi-query path on any error.
--
-- p_day_start: the client passes its LOCAL midnight (the worker's "today"),
-- so "Hive Activity Today" counts keep their existing semantics and match the
-- old code exactly. Defaults to UTC midnight when omitted.

BEGIN;

-- canonical-allow: read-optimization transport that bundles already-canonical
-- v_*_truth signals into one round-trip; it is NOT a new canonical source, so
-- it is anchored here rather than registered in canonical_sources.
CREATE OR REPLACE FUNCTION public.get_hive_dashboard(
  p_hive_id   uuid,
  p_day_start timestamptz DEFAULT date_trunc('day', now())
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

  -- ── Consolidated board payload (mirrors index.html dashboard loader) ──
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
    -- (.filter(qty_on_hand <= 0)) from this array — same as the old
    -- invRaw.filter(is_low_stock) path, so behavior is parity-equal.
    'low_stock_items', COALESCE((
      SELECT jsonb_agg(i) FROM (
        SELECT part_name, qty_on_hand, reorder_point
        FROM public.v_inventory_items_truth
        WHERE hive_id = p_hive_id AND is_low_stock = true
        LIMIT 100
      ) i
    ), '[]'::jsonb),

    -- PM overdue: count of is_due rows from the canonical compliance view
    'pm_overdue_count', (
      SELECT count(*) FROM public.v_pm_compliance_truth
      WHERE hive_id = p_hive_id AND is_due = true
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
        WHERE hive_id = p_hive_id AND status = 'pending' AND shift_date >= current_date
        ORDER BY shift_date ASC
        LIMIT 1
      ) a
    ),
    'sensor_anomaly', (
      SELECT to_jsonb(s) FROM (
        SELECT asset_id, parameter, quality_flag, recorded_at, is_anomaly
        FROM public.v_sensor_truth
        WHERE hive_id = p_hive_id AND is_anomaly = true
          AND recorded_at >= now() - interval '24 hours'
        ORDER BY recorded_at DESC
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
$$;

COMMENT ON FUNCTION public.get_hive_dashboard(uuid, timestamptz) IS
  'Home (index.html) board fan-out collapse: returns all 11 canonical home signals in one jsonb round-trip. Membership-gated via auth.uid() (SECURITY DEFINER bypasses RLS). Reads the same v_*_truth views as the client loader so output is parity-equal. Hive mode only; solo home keeps its legacy path.';

-- Needs auth.uid() for the membership gate, so authenticated-only (anon always fails).
GRANT EXECUTE ON FUNCTION public.get_hive_dashboard(uuid, timestamptz) TO authenticated;

COMMIT;
