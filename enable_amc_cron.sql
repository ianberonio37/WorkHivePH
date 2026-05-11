-- Autonomous Maintenance Crew (AMC) cron schedule.
--
-- Run this manually in the Supabase SQL editor after the
-- 20260512000002_amc_briefings.sql migration applies. It is NOT included
-- as a migration because pg_cron schedules are environment-specific
-- (the function URL changes between local supabase start and prod).
--
-- 06:00 PHT (UTC+8) = 22:00 UTC of the PREVIOUS day. Cron uses UTC.
--
-- The schedule does two things sequentially every day:
--   1. amc_expire_stale() - flip any 'pending' briefings older than expires_at
--      to 'expired' so the supervisor's alert-hub feed stays clean.
--   2. POST to scheduled-agents with { report_type: 'amc_brief' } - this
--      fans out to amc-orchestrator per active hive.
--
-- Adjust the URL to match your Supabase project before running.

-- Step 1: expire stale briefings just before generating a new one (05:55 PHT).
SELECT cron.schedule(
  'amc-expire-stale-0555pht',
  '55 21 * * *',  -- 21:55 UTC = 05:55 PHT next day
  $$ SELECT public.amc_expire_stale(); $$
);

-- Step 2: generate today's brief at 06:00 PHT.
-- amc-orchestrator in drain mode (no hive_id) walks every hive with an
-- active member and inserts one brief per hive for today's shift_date.
-- The UNIQUE INDEX on (hive_id, shift_date) makes the call idempotent.
SELECT cron.schedule(
  'amc-brief-0600pht',
  '0 22 * * *',   -- 22:00 UTC = 06:00 PHT next day
  $$
  SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/amc-orchestrator',
    headers := jsonb_build_object(
      'Content-Type',  'application/json',
      'Authorization', 'Bearer ' || current_setting('app.service_role_key', true)
    ),
    body    := '{}'::jsonb
  );
  $$
);

-- To inspect:  SELECT * FROM cron.job WHERE jobname LIKE 'amc%';
-- To remove:   SELECT cron.unschedule('amc-brief-0600pht');
--              SELECT cron.unschedule('amc-expire-stale-0555pht');
