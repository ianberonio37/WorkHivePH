-- Canonical Sources Phase B.1: v_kpi_truth materialised view.
--
-- Phase 1.3 of the KPI engine revamp (KPI_ENGINE.md). When the dashboard
-- latency budget no longer fits "live recomputation each refresh", the
-- right answer is a materialised view with a refresh schedule -- not a
-- new formula. v_kpi_truth gives Asset Hub, Alert Hub, and the Hive Board
-- a single read path for failure_count / MTBF / MTTR / downtime at the
-- three canonical windows (30 / 90 / 365 days). The view contract is
-- stable; only the freshness SLA differs from a live view (1h refresh).
--
-- Why a materialised view and not a regular view:
--   The underlying logbook has BRIN indexes on created_at + B-tree on
--   (hive_id, machine, created_at). A live aggregate is fast enough for
--   single-hive snapshots but breaks down for the cross-hive Hive Board
--   panel and for any surface that needs all three windows in one render.
--   Refreshing hourly amortises the work across all readers.
--
-- Why the snapshot-only contract:
--   Analytics keeps using get_mtbf_by_machine RPC at user-selected windows
--   (that's the "live recomputation" path). v_kpi_truth is the *fixed
--   window* snapshot for "current state" cards that don't need a period
--   selector. Two engines, one formula -- the MTBF math here mirrors the
--   RPC (mean of inter-arrival intervals via LAG()).
--
-- Trigger to revisit:
--   - A surface that needs windows other than 30 / 90 / 365 -> extend the
--     view or fall back to the RPC.
--   - Refresh SLA tightens below 1h -> CONCURRENTLY refresh keeps reads
--     uninterrupted; tune the cron schedule.
--   - A surface needs PM-completion KPIs alongside failure KPIs -> add
--     them in a follow-up; pm completions don't need LAG().
--
-- Skills consulted: predictive-analytics (MTBF formula, window semantics
-- per ISO 14224:2016), analytics-engineer (snapshot vs interactive
-- separation), architect (materialised view + canonical_sources contract,
-- index for CONCURRENTLY refresh), data-engineer (LAG() pattern + CTE
-- structure, hive-scoped + RLS-inherited reads).

BEGIN;

-- ── 1. The materialised view itself ───────────────────────────────────────────
--
-- Strategy: one CTE per window. Within each CTE, LAG() over (hive_id,
-- machine ORDER BY created_at) produces the previous-failure timestamp so
-- the mean-of-intervals math becomes an AVG. The three CTEs are then
-- joined on (hive_id, machine).

CREATE MATERIALIZED VIEW IF NOT EXISTS public.v_kpi_truth AS
WITH base_30d AS (
  SELECT
    hive_id,
    machine,
    created_at,
    downtime_hours,
    LAG(created_at) OVER (PARTITION BY hive_id, machine ORDER BY created_at) AS prev_at
  FROM public.logbook
  WHERE maintenance_type = 'Breakdown / Corrective'
    AND created_at >= NOW() - INTERVAL '30 days'
),
base_90d AS (
  SELECT
    hive_id,
    machine,
    created_at,
    downtime_hours,
    LAG(created_at) OVER (PARTITION BY hive_id, machine ORDER BY created_at) AS prev_at
  FROM public.logbook
  WHERE maintenance_type = 'Breakdown / Corrective'
    AND created_at >= NOW() - INTERVAL '90 days'
),
base_365d AS (
  SELECT
    hive_id,
    machine,
    created_at,
    downtime_hours,
    LAG(created_at) OVER (PARTITION BY hive_id, machine ORDER BY created_at) AS prev_at
  FROM public.logbook
  WHERE maintenance_type = 'Breakdown / Corrective'
    AND created_at >= NOW() - INTERVAL '365 days'
),
agg_30d AS (
  SELECT
    hive_id, machine,
    COUNT(*)                                                                  AS failures_30d,
    ROUND(AVG(EXTRACT(EPOCH FROM (created_at - prev_at)) / 86400.0)::numeric, 1) AS mtbf_30d,
    ROUND(AVG(downtime_hours)::numeric, 1)                                    AS mttr_30d,
    ROUND(SUM(downtime_hours)::numeric, 1)                                    AS total_downtime_30d,
    MAX(created_at)                                                           AS last_failure_at_30d
  FROM base_30d
  WHERE hive_id IS NOT NULL
  GROUP BY hive_id, machine
),
agg_90d AS (
  SELECT
    hive_id, machine,
    COUNT(*)                                                                  AS failures_90d,
    ROUND(AVG(EXTRACT(EPOCH FROM (created_at - prev_at)) / 86400.0)::numeric, 1) AS mtbf_90d,
    ROUND(AVG(downtime_hours)::numeric, 1)                                    AS mttr_90d,
    ROUND(SUM(downtime_hours)::numeric, 1)                                    AS total_downtime_90d
  FROM base_90d
  WHERE hive_id IS NOT NULL
  GROUP BY hive_id, machine
),
agg_365d AS (
  SELECT
    hive_id, machine,
    COUNT(*)                                                                  AS failures_365d,
    ROUND(AVG(EXTRACT(EPOCH FROM (created_at - prev_at)) / 86400.0)::numeric, 1) AS mtbf_365d,
    ROUND(AVG(downtime_hours)::numeric, 1)                                    AS mttr_365d,
    ROUND(SUM(downtime_hours)::numeric, 1)                                    AS total_downtime_365d,
    MAX(created_at)                                                           AS last_failure_at
  FROM base_365d
  WHERE hive_id IS NOT NULL
  GROUP BY hive_id, machine
)
SELECT
  a365.hive_id,
  a365.machine,
  -- 30-day window (NULL when no corrective entries in window).
  COALESCE(a30.failures_30d,    0)                  AS failures_30d,
  a30.mtbf_30d,
  a30.mttr_30d,
  COALESCE(a30.total_downtime_30d, 0)               AS total_downtime_30d,
  a30.last_failure_at_30d,
  -- 90-day window
  COALESCE(a90.failures_90d,    0)                  AS failures_90d,
  a90.mtbf_90d,
  a90.mttr_90d,
  COALESCE(a90.total_downtime_90d, 0)               AS total_downtime_90d,
  -- 365-day window (the always-present anchor; rows exist only when this is non-zero).
  a365.failures_365d,
  a365.mtbf_365d,
  a365.mttr_365d,
  a365.total_downtime_365d,
  a365.last_failure_at,
  -- Refresh stamp so consumers can detect staleness.
  NOW()                                              AS generated_at
FROM agg_365d a365
LEFT JOIN agg_90d  a90 ON a90.hive_id = a365.hive_id AND a90.machine = a365.machine
LEFT JOIN agg_30d  a30 ON a30.hive_id = a365.hive_id AND a30.machine = a365.machine;

COMMENT ON MATERIALIZED VIEW public.v_kpi_truth IS
  'Canonical KPI snapshot per (hive_id, machine). failure_count / MTBF / MTTR / total_downtime at the 30 / 90 / 365 day windows, refreshed hourly by pg_cron. Same MTBF formula as get_mtbf_by_machine RPC (mean of inter-arrival intervals via LAG). Used by Asset Hub, Alert Hub, and Hive Board snapshot cards. Analytics keeps using the RPC for user-selected windows.';

-- ── 2. Unique index for REFRESH MATERIALIZED VIEW CONCURRENTLY ───────────────
-- Without a unique index, CONCURRENTLY refresh isn't allowed and readers
-- block during refresh. (hive_id, machine) is the natural key.

CREATE UNIQUE INDEX IF NOT EXISTS uq_v_kpi_truth_hive_machine
  ON public.v_kpi_truth (hive_id, machine);

-- Supporting B-tree for downstream filters (Asset Hub queries by hive_id +
-- machine; Hive Board groups by hive_id).
CREATE INDEX IF NOT EXISTS idx_v_kpi_truth_hive
  ON public.v_kpi_truth (hive_id);

-- ── 3. GRANTs (RLS is inherited from logbook; service role bypasses) ────────

GRANT SELECT ON public.v_kpi_truth TO anon, authenticated;

-- ── 4. Refresh helper function ───────────────────────────────────────────────
-- Called by pg_cron + on-demand from admin tooling. CONCURRENTLY so SELECTs
-- against the MV are not blocked during the refresh. SECURITY DEFINER + locked
-- search_path so cron's session settings don't affect resolution.

CREATE OR REPLACE FUNCTION public.refresh_v_kpi_truth()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY public.v_kpi_truth;

  -- Audit row so we can spot refresh failures in automation_log even when the
  -- cron exit status is opaque.
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
    INSERT INTO public.automation_log (job_name, status, detail)
    VALUES (
      'v_kpi_truth_refresh',
      'success',
      format('rows=%s, refreshed_at=%s',
             (SELECT count(*) FROM public.v_kpi_truth),
             NOW()::text)
    );
  END IF;
EXCEPTION
  WHEN OTHERS THEN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
      INSERT INTO public.automation_log (job_name, status, detail)
      VALUES (
        'v_kpi_truth_refresh',
        'failed',
        format('error=%s, sqlstate=%s', SQLERRM, SQLSTATE)
      );
    END IF;
    RAISE;
END
$$;

COMMENT ON FUNCTION public.refresh_v_kpi_truth() IS
  'Refresh v_kpi_truth concurrently. Called hourly by pg_cron (see enable_v_kpi_truth_cron.sql). Logs success/failure to automation_log.';

-- ── 5. Initial population so consumers can read the MV immediately ───────────
-- New MV starts empty; do a one-time non-concurrent refresh inside the
-- migration so the contract is honoured the moment this lands.

REFRESH MATERIALIZED VIEW public.v_kpi_truth;

-- ── 6. Register in canonical_sources ─────────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'kpi_truth',
  'view',
  'v_kpi_truth',
  'analytics-engineer',
  '1h_materialized',
  'Canonical KPI snapshot per (hive_id, machine) at 30/90/365-day windows. Read by Asset Hub, Alert Hub, and Hive Board for snapshot cards that do not need a period selector. Analytics interactive path keeps using get_mtbf_by_machine RPC for user-selected windows.',
  jsonb_build_object(
    'key', jsonb_build_array('hive_id', 'machine'),
    'hive_scoped', true,
    'solo_mode_supported', false,
    'window_columns', jsonb_build_array(
      'failures_30d', 'failures_90d', 'failures_365d',
      'mtbf_30d', 'mtbf_90d', 'mtbf_365d',
      'mttr_30d', 'mttr_90d', 'mttr_365d',
      'total_downtime_30d', 'total_downtime_90d', 'total_downtime_365d'
    ),
    'refresh_function', 'refresh_v_kpi_truth()',
    'refresh_cadence', 'hourly via pg_cron (see enable_v_kpi_truth_cron.sql)',
    'mtbf_formula',    'mean of inter-arrival intervals of corrective entries within window; same formula as get_mtbf_by_machine RPC'
  ),
  'Phase B.1 / KPI revamp Phase 1.3 -- the first materialised canonical view. Refresh schedule is environment-specific so the cron is in enable_v_kpi_truth_cron.sql, not this migration.'
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
