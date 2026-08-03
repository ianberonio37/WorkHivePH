-- ============================================================================
-- SCHEDULE THE COMPLETION SWEEP — a window nothing checks is not a window
--
-- Migration 31 built the objection window and the sweep that closes it. Until
-- something CALLS that sweep, a job marked done still waits forever and the
-- whole mechanism is a function nobody invokes -- the same "built but never
-- called" shape this platform has shipped before (push with no sender, 9 cron
-- targets that did not exist).
--
-- HOURLY, not the 1-minute cadence its sibling uses. The window is measured in
-- DAYS, so minute precision buys nothing and costs 1,440 scans a day; hourly
-- bounds the settle lag to at most an hour past the deadline, which is
-- invisible against a 3-day window. Offset to :07 so it does not pile onto the
-- top-of-hour jobs.
--
-- ONE-TIME BACKLOG, and it is intended. Jobs already sitting in `completed`
-- past their window settle on the first run -- measured before shipping: 1 such
-- job exists, completed 2026-07-29 and waiting ever since, which is precisely
-- the stall this arc exists to end. Recorded here so the first run's non-zero
-- return is read as the backlog draining, not as a bug.
-- ============================================================================

-- Idempotent: re-running a migration must not leave two schedules racing the
-- same sweep. cron.unschedule throws if the job is absent, so guard on catalog.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'service-completion-sweep-hourly') THEN
    PERFORM cron.unschedule('service-completion-sweep-hourly');
  END IF;
END $$;

SELECT cron.schedule('service-completion-sweep-hourly', '7 * * * *',
                     $$SELECT public.sweep_service_completions();$$);
