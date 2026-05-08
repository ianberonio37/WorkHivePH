-- Activate Shift Brain autonomous shift planner.
--
-- Prerequisites (in this order):
--   1. pg_cron + pg_net extensions are enabled in this Supabase project
--      (already confirmed: the existing risk_scoring_cron migration applied
--      cleanly, which would have failed without them).
--   2. Run STEP A below ONCE with your actual service role key. The key gets
--      stored as a Postgres database setting, NOT in any committed SQL file.
--      Get the key from: Dashboard > Project Settings > API > service_role.
--   3. Run STEP B to register (or re-register) the three schedules. Safe to
--      re-run any time.
--
-- The three schedules fire at the Filipino 3-shift boundaries:
--   06:00 PHT (UTC+8) = 22:00 UTC of the prior day  -> 06-14 morning briefing
--   14:00 PHT          = 06:00 UTC                  -> 14-22 afternoon briefing
--   22:00 PHT          = 14:00 UTC                  -> 22-06 night briefing

-- ===========================================================================
-- STEP A. Store the service role key once. Replace the placeholder below
--         with your actual key, then run THIS BLOCK in the Supabase SQL
--         Editor. The key is stored at the database level and is read at
--         cron run time via current_setting('app.service_role_key').
-- ===========================================================================

-- ALTER DATABASE postgres SET app.service_role_key = 'PASTE_SERVICE_ROLE_KEY_HERE';

-- After running ALTER DATABASE, you must reconnect (the SQL Editor does this
-- automatically on the next query). Verify the key is set with:
-- SHOW app.service_role_key;

-- ===========================================================================
-- STEP B. Register the schedules. Re-running this block is idempotent: prior
--         schedules with the same names are unscheduled first.
-- ===========================================================================

-- B1. Idempotent unschedule of any prior shift-brain-* jobs.
SELECT cron.unschedule(jobname)
FROM cron.job
WHERE jobname IN ('shift-brain-morning', 'shift-brain-afternoon', 'shift-brain-night');

-- B2. 06:00 PHT (= 22:00 UTC) morning briefing.
SELECT cron.schedule(
  'shift-brain-morning',
  '0 22 * * *',
  $$ SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/shift-planner-orchestrator',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || current_setting('app.service_role_key'),
      'Content-Type',  'application/json'
    ),
    body    := '{"shift_window":"06-14"}'::jsonb
  ) $$
);

-- B3. 14:00 PHT (= 06:00 UTC) afternoon briefing.
SELECT cron.schedule(
  'shift-brain-afternoon',
  '0 6 * * *',
  $$ SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/shift-planner-orchestrator',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || current_setting('app.service_role_key'),
      'Content-Type',  'application/json'
    ),
    body    := '{"shift_window":"14-22"}'::jsonb
  ) $$
);

-- B4. 22:00 PHT (= 14:00 UTC) night briefing.
SELECT cron.schedule(
  'shift-brain-night',
  '0 14 * * *',
  $$ SELECT net.http_post(
    url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/shift-planner-orchestrator',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || current_setting('app.service_role_key'),
      'Content-Type',  'application/json'
    ),
    body    := '{"shift_window":"22-06"}'::jsonb
  ) $$
);

-- B5. Verify the schedules registered.
SELECT jobid, jobname, schedule, active
FROM cron.job
WHERE jobname LIKE 'shift-brain-%'
ORDER BY jobname;

-- ===========================================================================
-- OPTIONAL. Trigger an immediate test run (no need to wait for the next shift).
-- ===========================================================================

-- SELECT net.http_post(
--   url     := 'https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/shift-planner-orchestrator',
--   headers := jsonb_build_object(
--     'Authorization', 'Bearer ' || current_setting('app.service_role_key'),
--     'Content-Type',  'application/json'
--   ),
--   body    := '{"shift_window":"06-14"}'::jsonb
-- );

-- Then check shift_plans to see what was generated:
-- SELECT hive_id, shift_window, status, generated_at, briefing
-- FROM shift_plans
-- ORDER BY generated_at DESC
-- LIMIT 10;

-- ===========================================================================
-- INSPECTING RECENT RUNS (debugging)
-- ===========================================================================

-- SELECT jobid, runid, start_time, end_time, status, return_message
-- FROM cron.job_run_details
-- WHERE jobid IN (
--   SELECT jobid FROM cron.job WHERE jobname LIKE 'shift-brain-%'
-- )
-- ORDER BY start_time DESC
-- LIMIT 20;

-- ===========================================================================
-- UNINSTALL
-- ===========================================================================

-- SELECT cron.unschedule('shift-brain-morning');
-- SELECT cron.unschedule('shift-brain-afternoon');
-- SELECT cron.unschedule('shift-brain-night');
-- ALTER DATABASE postgres RESET app.service_role_key;
