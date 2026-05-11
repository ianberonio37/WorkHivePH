-- agent_memory retention cron -- closes the L4 INFO ratchet in
-- validate_memory_integrity.py.
--
-- Deletes:
--   * turns older than 90 days  (kind = 'turn',    created_at < now() - '90 days')
--   * summaries older than 180  (kind = 'summary', created_at < now() - '180 days')
--
-- Runs daily at 04:15 UTC -- between the AI eval daily (03:30) and the
-- DB hygiene crons. Wrapped in DO blocks + EXCEPTION so the migration
-- is a no-op on environments without pg_cron (local dev, fresh Supabase).

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule('agent-memory-retention');
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule(
      'agent-memory-retention',
      '15 4 * * *',
      $cron$
      DELETE FROM public.agent_memory
       WHERE kind = 'turn'
         AND created_at < now() - INTERVAL '90 days';
      DELETE FROM public.agent_memory
       WHERE kind = 'summary'
         AND created_at < now() - INTERVAL '180 days';
      $cron$
    );
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;
