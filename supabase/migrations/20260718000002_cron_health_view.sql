-- 20260718000002_cron_health_view.sql
--
-- Grafana G4 (other observability, 2026-07-18): make the 16 pg_cron jobs OBSERVABLE.
-- A failing cron is SILENT today (nobody sees cron.job_run_details) — 27 failed runs in
-- the last 7 days were invisible. pg_cron restricts cron.job / cron.job_run_details to the
-- job OWNER, so a plain SELECT grant to the read-only monitoring role still returns 0 rows.
-- This postgres-owned view (security_invoker OFF → runs as its owner, which owns the jobs)
-- exposes the run history so the Grafana Founder-Ops dashboard + a cron-failure alert can
-- surface it. Read-only; grafana_reader is GRANTed SELECT in infra/mcp/grafana/grafana_reader.sql.

DROP VIEW IF EXISTS public.v_cron_health;
CREATE VIEW public.v_cron_health AS
  SELECT j.jobid,
         j.jobname,
         j.schedule,
         j.active,
         d.runid,
         d.status,
         d.start_time,
         d.end_time,
         left(d.return_message, 200) AS return_message
  FROM cron.job j
  LEFT JOIN cron.job_run_details d ON d.jobid = j.jobid;

GRANT SELECT ON public.v_cron_health TO grafana_reader;
