-- 20261013000003 - THE HOURLY KPI REFRESH COULD BE TRIGGERED BY ANYONE (layer invariants, cron grant_matches_policy,
-- 2026-10-13).
--
-- refresh_v_kpi_truth() is SECURITY DEFINER and runs REFRESH MATERIALIZED VIEW CONCURRENTLY public.v_kpi_truth, then
-- writes an automation_log row. Its only caller is the pg_cron job v-kpi-truth-refresh-hourly (migration
-- 20260915000001), which runs as the table owner. But EXECUTE was never revoked, so PUBLIC, anon and authenticated
-- could all call it: any visitor could rebuild the platform-wide KPI view on demand, as often as they liked, and add a
-- log row each time. No page, script or edge function calls it (checked: no rpc('refresh_v_kpi_truth') anywhere).
-- The cron job keeps working: it runs as postgres, which owns the function.

revoke execute on function public.refresh_v_kpi_truth() from public, anon, authenticated;
