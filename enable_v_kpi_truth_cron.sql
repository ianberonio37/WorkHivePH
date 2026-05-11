-- v_kpi_truth refresh schedule (Phase 1.3 / Phase B.1).
--
-- Run this manually in the Supabase SQL editor after the
-- 20260512000005_v_kpi_truth.sql migration applies. It is NOT in the
-- migration because pg_cron schedules can be environment-specific
-- (you may want to skip it on local supabase start while developing).
--
-- The schedule refreshes the materialised view every hour, on the hour.
-- public.refresh_v_kpi_truth() runs REFRESH MATERIALIZED VIEW CONCURRENTLY
-- so readers are never blocked during the refresh and writes an
-- automation_log row on success/failure.
--
-- Hourly cadence rationale (KPI_ENGINE.md):
--   - Asset Hub and Alert Hub snapshot cards do not need second-level
--     freshness; a 1-hour lag is invisible to the operator.
--   - The full MTBF / MTTR / downtime rollup across all hives takes
--     non-trivial CPU; doing it once per hour amortises the cost.
--   - If a tighter SLA is needed for a specific surface, that surface
--     can fall back to get_mtbf_by_machine RPC at request time.

SELECT cron.schedule(
  'v-kpi-truth-refresh-hourly',
  '0 * * * *',  -- top of every hour
  $$ SELECT public.refresh_v_kpi_truth(); $$
);

-- To inspect:  SELECT * FROM cron.job WHERE jobname = 'v-kpi-truth-refresh-hourly';
-- To remove:   SELECT cron.unschedule('v-kpi-truth-refresh-hourly');
-- Manual ad-hoc: SELECT public.refresh_v_kpi_truth();
