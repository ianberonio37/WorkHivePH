-- Q5-b (2026-07-05): RETENTION for embedding_cache — close the unbounded-cache gap.
--
-- GROUNDED (Step 0): embeddings are the silent DB-size driver (measured: 19 vector
-- tables ~62 MB, voice_journal_entries alone 45 MB). Retention splits by table nature:
--   * CANONICAL data (voice_journal/logbook/pm_completions/unified_events) -> the
--     cold-archive pipeline (export-to-Parquet + a DELIBERATELY GATED prune; see
--     tools/cold_archive_prune.py) — never a blind auto-delete.
--   * TRANSIENT data -> a safe auto-prune. analytics_events + agent_memory already have
--     one; embedding_cache did NOT (it has a last_used index but nothing evicts) — a cache
--     that only grows. A cache is safe to prune by definition: a missing entry is just
--     recomputed on next use. This adds the missing LRU age eviction.
--
-- Daily at 04:25 UTC (after agent-memory-retention 04:15). Wrapped in DO/EXCEPTION so it
-- is a no-op where pg_cron is absent (local dev, fresh Supabase).

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule('embedding-cache-retention');
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule(
      'embedding-cache-retention',
      '25 4 * * *',
      $cron$
      -- LRU age eviction: drop cache entries not used in 45 days. Recomputed on demand.
      DELETE FROM public.embedding_cache
       WHERE last_used < now() - INTERVAL '45 days';
      $cron$
    );
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;

-- A callable prune fn so the retention gate + a manual run can exercise the exact policy
-- the cron uses (the cron body isn't introspectable on pg_cron-less envs). SECURITY DEFINER
-- so it can prune under whatever RLS embedding_cache carries. Returns rows deleted.
CREATE OR REPLACE FUNCTION public.prune_embedding_cache(p_max_age_days int DEFAULT 45)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  v_deleted integer;
BEGIN
  DELETE FROM public.embedding_cache
   WHERE last_used < now() - make_interval(days => p_max_age_days);
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  RETURN v_deleted;
END;
$fn$;

GRANT EXECUTE ON FUNCTION public.prune_embedding_cache(int) TO service_role;

COMMENT ON FUNCTION public.prune_embedding_cache(int) IS
  'Q5-b 2026-07-05: LRU age eviction for the embedding_cache (a cache = safe to prune; recomputed on demand). Mirrors the embedding-cache-retention cron policy so it is testable on pg_cron-less envs.';
