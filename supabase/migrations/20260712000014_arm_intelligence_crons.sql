-- 20260712000014_arm_intelligence_crons.sql
-- Asset/Alert/Shift PDDA arc (2026-07-12) — Ext-3 (cron-honesty) keystone F12/F13.
--
-- The AMC daily brief (amc-orchestrator) + its stale-expiry, and the failure-signature scan,
-- were armed ONLY by the manual repo-root script enable_amc_cron.sql (hard-coded PROD URL).
-- So on every fresh/local environment they NEVER run: alert-hub shows "None today" with no
-- signal the automation is unarmed (F12), and failure-signature-scan claims a daily cron in
-- its header while none exists, so pattern alerts age silently as "active" (F13).
--
-- This arms all three with the PORTABLE URL + bearer pattern already used by the other jobs
-- (20260510000008_cron_portable_urls.sql: current_setting('app.supabase_functions_url')) so
-- they schedule identically on local + prod. Idempotent (unschedule-then-schedule; pg_cron is
-- last-writer-wins per job_name). No-op on environments without pg_cron (local Supabase by
-- default has it; the guard keeps CI green either way). Verified by validate_cron_honesty.py,
-- which asserts every edge fn claiming a cron trigger actually has a matching cron.job.
--
-- Schedules (unchanged from enable_amc_cron.sql; UTC → PHT):
--   amc-expire-stale-0555pht   '55 21 * * *'  (21:55 UTC = 05:55 PHT) → amc_expire_stale()
--   amc-brief-0600pht          '0 22 * * *'   (22:00 UTC = 06:00 PHT) → /amc-orchestrator (drain)
--   failure-signature-scan-daily '0 21 * * *' (21:00 UTC = 05:00 PHT) → /failure-signature-scan (drain)

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    -- idempotent: drop any prior definition of these three jobs first
    PERFORM cron.unschedule('amc-expire-stale-0555pht');
    PERFORM cron.unschedule('amc-brief-0600pht');
    PERFORM cron.unschedule('failure-signature-scan-daily');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- 1. Expire stale pending briefings just before the new one is generated (05:55 PHT).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('amc-expire-stale-0555pht', '55 21 * * *',
      'SELECT public.amc_expire_stale();');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- 2. Generate the AMC daily brief per active hive (06:00 PHT). Drain mode (no hive_id).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('amc-brief-0600pht', '0 22 * * *',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/amc-orchestrator'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- 3. Refresh failure-signature alerts daily (05:00 PHT) so pattern alerts don't age as "active".
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule('failure-signature-scan-daily', '0 21 * * *',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/failure-signature-scan'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key''), ''Content-Type'', ''application/json''), body := ''{}''::jsonb);');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
