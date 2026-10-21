-- BRH-AA (2026-10-21): the database stays inside the free plan's 500 MB - pg_cron's run history is kept for 7 days.
--
-- Ian, 2026-10-21: "you know that my platform always free ... I am not upgrading to pro, can you just be proactive and
-- do appropriately what is needed for my platform."
--
-- Measured on production (read-only, through the Supabase connector): the database is 134 MB of the free plan's 500 MB,
-- and 77 MB of it - 57% - is cron.job_run_details: 443,228 run records since 2026-04-25, none ever removed. Four jobs run
-- every minute (service-broadcast-sweep, service-outbox-drain, service-outbox-reconcile,
-- service-availability-reconcile), so the history grows by about 5,800 rows a day - roughly 350 MB a year, which alone
-- would carry the database past the free limit, where Supabase stops writes. The history is operational only (when each
-- job ran and whether it failed); no person's data is in it, and a week of it is enough to see a job that has stopped.
--
-- A daily job removes run records older than 7 days, and this migration removes the backlog once. The space the rows held
-- is reused by the rows that follow, so the database stops growing on this account.

-- the backlog, once
delete from cron.job_run_details where end_time < now() - interval '7 days';

-- every day at 04:20 UTC, the same rule (cron.schedule by name replaces a job of the same name, so a re-run is harmless)
select cron.schedule(
  'cron-history-retention',
  '20 4 * * *',
  $$ delete from cron.job_run_details where end_time < now() - interval '7 days' $$
);
