-- voice_journal_entries retention -- the T117 policy that has never once run.
--
-- WHAT WAS WRONG. voice-handler.js carries `_enforceRetention(db, hiveId, daysToRetain)` and a comment
-- describing a "per-hive configurable retention (default 180 days)". Measured 2026-09-08, the symbol
-- appears exactly TWICE in that file: the definition and the export list. It has no call site anywhere in
-- the repo, so nothing has ever been aged out - while validate_ai_companion_compliance.py passed T117 on
-- every run, because it checked that the NAME was spelled in the file.
--
-- AND IT COULD NOT HAVE BEEN CALLED FROM THERE. That helper deletes every row in a hive older than the
-- cutoff - every worker's entries, not the speaker's own. A browser session holds one worker's identity;
-- asking it to run a hive-wide destructive sweep would need RLS to let any member delete their
-- colleagues' journal rows, which is a hole, not a feature. Retention is a scheduled job or it is
-- nothing. So it is written where it belongs, cloned from this platform's own precedent
-- (20260511000010_agent_memory_retention_cron.sql): a plain SQL cron, no edge function, no key.
--
-- WHAT IT DELETES. Voice journal entries older than 180 days - the default the client comment already
-- named, so this changes no stated policy, it performs the one already written down. Right-to-erasure is
-- a separate path (a worker asking for their own history to go, now wired to run on a confirmed yes) and
-- is unaffected by this.
--
-- Runs daily at 04:45 UTC, after agent-memory-retention (04:15) and before the gateway audit retention
-- (04:30 is taken, so this sits clear of both). Wrapped in DO blocks with EXCEPTION so the migration is a
-- no-op where pg_cron is absent - local dev and a fresh project - exactly as its precedent is.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule('voice-journal-retention');
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule(
      'voice-journal-retention',
      '45 4 * * *',
      $cron$
      DELETE FROM public.voice_journal_entries
       WHERE created_at < now() - INTERVAL '180 days';
      $cron$
    );
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;
