-- ─────────────────────────────────────────────────────────────────────────────
-- Make an amendment to a PM completion evident at the DATABASE.
--
-- FOUND BY THE PM11 WALK (2026-07-28, PM_DEEPWALK_EXPANSION_ROADMAP):
-- a technician silently BACK-DATED their own completion by 400 days. One row affected, no error,
-- nothing recorded anywhere. pm_completions carried six triggers and not one of them audits.
--
-- Why completed_at specifically is the field that matters: it drives the compliance window
-- (`completed_at >= now() - period`), the on-time measure (the gap to the previous completion), and
-- `last_completed_at` -> `next_due_date`. So the completion DATE is the single most consequential
-- value on a compliance record, and moving it moves the number a plant and an auditor both read.
-- Back-dating a late PM makes it on-time; forward-dating a missed one makes it done.
--
-- This is the same shape the logbook arc closed with trg_logbook_post_close_audit: a client-written
-- audit row is skipped by any write that does not go through the page, so "evident" has to mean the
-- database recorded it. pm_completions had no client-written audit row either, so here the trigger
-- is not a backstop — it is the only record there has ever been.
--
-- SCOPE. Fires only on a change to a field that alters the compliance record's meaning:
-- completed_at, status, or scope_item_id. An edit to free-text notes is not an amendment of the
-- record and does not need a trail, which keeps the log readable enough to actually be audited.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.audit_pm_completion_amendment()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
BEGIN
  -- Only a change that alters what the record CLAIMS about compliance.
  IF NEW.completed_at IS NOT DISTINCT FROM OLD.completed_at
     AND NEW.status    IS NOT DISTINCT FROM OLD.status
     AND NEW.scope_item_id IS NOT DISTINCT FROM OLD.scope_item_id THEN
    RETURN NEW;
  END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, NEW.worker_name, 'unknown'),
    'amend_pm_completion',
    'pm_completions',
    NEW.id::text,
    COALESCE(NEW.worker_name, '(unknown worker)'),
    jsonb_build_object(
      'completed_at_was', OLD.completed_at,
      'completed_at_now', NEW.completed_at,
      'status_was',       OLD.status,
      'status_now',       NEW.status,
      -- The days moved is the number an auditor actually wants: it says whether a late PM was
      -- quietly made to look on-time.
      'days_moved',       CASE
                            WHEN NEW.completed_at IS DISTINCT FROM OLD.completed_at
                            THEN round(EXTRACT(EPOCH FROM (NEW.completed_at - OLD.completed_at)) / 86400.0, 2)
                            ELSE NULL
                          END,
      'source',           'db_trigger'
    )
  );

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_pm_completion_amendment_audit ON public.pm_completions;
CREATE TRIGGER trg_pm_completion_amendment_audit
  AFTER UPDATE ON public.pm_completions
  FOR EACH ROW
  EXECUTE FUNCTION public.audit_pm_completion_amendment();
