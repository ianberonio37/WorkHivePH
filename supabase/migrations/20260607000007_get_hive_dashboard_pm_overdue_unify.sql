-- get_hive_dashboard pm_overdue_count UNIFY — kill the 2-view "Overdue" drift.
-- ============================================================================
-- The home (index.html) "PM Overdue" tile links straight to pm-scheduler.html,
-- so the two MUST agree. They did not:
--
--   home tile (this RPC)   read v_pm_compliance_truth.is_due  → 26
--   pm-scheduler #stat-overdue  reads v_pm_scope_items_truth.is_overdue → 4
--   (same hive, same minute — a user clicking "26 PM Overdue" landed on "4")
--
-- v_pm_compliance_truth.is_due is a COARSE per-asset "not anchored in 30 days"
-- proxy: it flags a Yearly PM completed 40 days ago as overdue, which inflated
-- the count (26 vs the true 4) and mis-classified long-frequency PMs. The
-- canonical, frequency-aware signal is v_pm_scope_items_truth.is_overdue
-- (next_due_date = COALESCE(last_completion, anchor, created) + frequency_days;
-- Monthly=30 / Quarterly=90 / Semi-Annual=180 / Yearly=365).
--
-- pm-scheduler #stat-overdue counts ASSETS with ≥1 overdue scope item
-- (getAssetOverallStatus rolls scope items up to the asset). To match it
-- exactly, pm_overdue_count now counts DISTINCT pm_asset_id with is_overdue.
--
-- Owner decision 2026-06-07: UNIFY on the frequency-aware view + fix the
-- dashboard (the 26→4 drop is a correction — 26 was inflated). hive.html's
-- #pulse-pm-overdue counts scope ITEMS (per-item) and stays as-is: that
-- granularity difference is intentional and already gated direction-only.
--
-- Everything else in this function is unchanged from 20260606000000.
-- Skills consulted: data-engineer (canonical view single-read), maintenance-
-- expert (frequency-aware overdue vs flat-30d), qa-tester (cross-surface KPI
-- parity), multitenant-engineer (membership gate preserved).

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

    -- PM overdue: DISTINCT assets with ≥1 OVERDUE scope item, read from the
    -- frequency-aware canonical per-scope-item view so this matches
    -- pm-scheduler.html #stat-overdue EXACTLY. (Was count(is_due) from
    -- v_pm_compliance_truth — a flat-30-day anchor proxy that over-counted.)
    'pm_overdue_count', (
      SELECT count(DISTINCT pm_asset_id) FROM public.v_pm_scope_items_truth
      WHERE hive_id = p_hive_id AND is_overdue = true
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
  'Home (index.html) board fan-out collapse: returns all 12 canonical home signals in one jsonb round-trip. Membership-gated via auth.uid() (SECURITY DEFINER bypasses RLS). Reads the same v_*_truth views as the client loader so output is parity-equal. pm_overdue_count = DISTINCT assets with an overdue scope item from v_pm_scope_items_truth (frequency-aware), matching pm-scheduler #stat-overdue; unified 2026-06-07 from the old v_pm_compliance_truth.is_due flat-30-day proxy. critical_pm_overdue = top critical asset with an overdue scope item (drives the Today''s-One-Thing nudge). Hive mode only; solo home keeps its legacy path.';

-- Needs auth.uid() for the membership gate, so authenticated-only (anon always fails).
GRANT EXECUTE ON FUNCTION public.get_hive_dashboard(uuid, timestamptz) TO authenticated;

COMMIT;
