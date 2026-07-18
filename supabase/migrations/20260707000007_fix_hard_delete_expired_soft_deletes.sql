-- 20260707000007_fix_hard_delete_expired_soft_deletes.sql
--
-- FIX: hard_delete_expired_soft_deletes() (the daily soft-delete retention cron, pg_cron job 24)
-- FAILED on EVERY run (28 consecutive `ERROR: column "deleted_at" does not exist` in
-- cron.job_run_details, found 2026-07-07 via the unattended-job sweep). It DELETEd from
-- public.logbook and public.community_replies filtering on `deleted_at IS NOT NULL` — but
-- NEITHER table has a `deleted_at` column. Only community_posts carries the deleted_at
-- soft-delete pattern; logbook has only `status` (its delete is a HARD delete — soft-delete is
-- an un-built roadmap gap) and community_replies has no soft-delete column at all. The function's
-- own comment wrongly claimed "logbook has a deleted_at column". So the retention job aborted at
-- the first DELETE and expired soft-deleted community_posts were NEVER hard-deleted.
--
-- Fix: purge only the table that actually has the deleted_at soft-delete column (community_posts),
-- plus the hive-agnostic ai_cost_log telemetry retention. Also fixes a latent counter bug: v_total
-- was overwritten each hive-loop iteration (GET DIAGNOSTICS after a single DELETE) so it only ever
-- returned the LAST hive's count — now it ACCUMULATES across hives. If logbook / community_replies
-- gain a real deleted_at soft-delete later, re-add them here (guarded by the column existing).

CREATE OR REPLACE FUNCTION public.hard_delete_expired_soft_deletes()
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_hive      record;
  v_total     integer := 0;
  v_retention integer;
  v_n         integer;
BEGIN
  FOR v_hive IN
    SELECT h.id, COALESCE(hrc.soft_delete_retention_days, 30) AS keep_days
      FROM public.hives h
      LEFT JOIN public.hive_retention_config hrc ON hrc.hive_id = h.id
  LOOP
    v_retention := v_hive.keep_days;

    -- community_posts is the ONLY hive-scoped table with the deleted_at soft-delete column.
    DELETE FROM public.community_posts
      WHERE hive_id = v_hive.id
        AND deleted_at IS NOT NULL
        AND deleted_at < now() - make_interval(days => v_retention);
    GET DIAGNOSTICS v_n = ROW_COUNT;
    v_total := v_total + v_n;   -- accumulate across hives (was overwritten before)
  END LOOP;

  -- Telemetry retention is hive-agnostic; one pass over the whole ledger.
  DELETE FROM public.ai_cost_log
    WHERE created_at < now() - interval '365 days';

  RETURN v_total;
END;
$function$;
