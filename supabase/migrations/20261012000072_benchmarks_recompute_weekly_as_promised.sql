-- ★"RECALCULATED WEEKLY" WAS A PROMISE NOTHING KEPT (2026-10-12, UFAI edge walk W4232).
--
-- benchmark-compute's own header says "Run weekly via pg_cron", and hive.html's benchmark panel tells the supervisor
-- "Recalculated weekly" - but cron.job had no benchmark entry, and the page's only caller (computeBenchmarkNow) was
-- never wired to a control. Measured: hive_benchmarks last written once (2026-10-07 22:00 UTC), network_benchmarks
-- EMPTY - and the panel hides itself unless both exist, so the comparison never showed at all. The weekly schedule
-- the function and the page both describe, with the same portable URL + bearer every other job uses (the no-hive_id
-- drain path fans out over all hives, service-role only). Sunday 21:30 UTC = Monday 05:30 PHT, before the
-- 06:00 PHT brief. A no-op where pg_cron is absent.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    BEGIN PERFORM cron.unschedule('benchmark-compute-weekly'); EXCEPTION WHEN OTHERS THEN NULL; END;
    PERFORM cron.schedule(
      'benchmark-compute-weekly',
      '30 21 * * 0',
      $job$SELECT net.http_post(url := current_setting('app.supabase_functions_url') || '/benchmark-compute', headers := jsonb_build_object('Authorization', 'Bearer ' || current_setting('app.service_role_key'), 'Content-Type', 'application/json'), body := '{}'::jsonb);$job$
    );
  END IF;
END $$;
