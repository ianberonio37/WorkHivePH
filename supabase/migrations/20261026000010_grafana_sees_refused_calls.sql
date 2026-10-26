-- 20261026000010_grafana_sees_refused_calls.sql
--
-- THE OPS ALERT COUNTED CRON'S FAILURES, NOT THE FUNCTIONS' (OWN scheduled-work lens, 2026-10-26). Grafana's "Scheduled
-- job failed (24h)" alert reads public.v_cron_health, and cron calls an HTTP job "succeeded" the moment its request is
-- queued - so when production's functions refused the scheduler's bearer for weeks, this alert (had it watched
-- production) would have stayed green. 20261026000008 records each scheduled call and settles its answer in
-- private.scheduled_calls; this view gives the monitoring role that answer, built the way v_cron_health is: owned by
-- postgres so it can read the private table, and granted to grafana_reader ONLY - no anon or authenticated grant, so
-- no client read path exists to it (the leak v_cron_health once had, closed 2026-07-29).

CREATE OR REPLACE VIEW public.v_scheduled_call_health AS
  SELECT c.jobname, c.fn, c.called_at, c.status_code, c.error, c.settled_at
    FROM private.scheduled_calls c;

REVOKE ALL ON public.v_scheduled_call_health FROM PUBLIC, anon, authenticated;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_reader') THEN
    GRANT SELECT ON public.v_scheduled_call_health TO grafana_reader;
  END IF;
END $$;
