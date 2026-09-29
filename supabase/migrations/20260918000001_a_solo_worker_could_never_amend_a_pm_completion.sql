-- A SOLO WORKER COULD NEVER AMEND A PM COMPLETION (2026-09-18, found by W45972)
--
-- WHAT HAPPENS TODAY. audit_pm_completion_amendment() fires on any UPDATE that changes what a PM
-- completion CLAIMS about compliance (completed_at, status, scope_item_id) and writes the before/after
-- into hive_audit_log. It passes NEW.hive_id straight through, and hive_audit_log.hive_id is NOT NULL.
-- So when the completion has no hive, the INSERT raises
--
--     null value in column "hive_id" of relation "hive_audit_log" violates not-null constraint
--
-- and, because the audit is a BEFORE/AFTER trigger on the same statement, THE WHOLE AMENDMENT IS ROLLED
-- BACK. The worker does not get a message about hives; they get a raw constraint violation, and the
-- correction they were making is lost.
--
-- WHY THAT ROW IS NOT CORRUPT. A hive-less PM completion is the SOLO LANE, which this platform supports
-- on purpose: a worker with no hive still gets the tools. Measured on the local corpus: 1 of 1,613
-- completions has hive_id NULL, its pm_asset and its pm_scope_item are BOTH hive-less too, and its
-- worker has 0 active hive memberships. The lineage is consistent all the way down - it is a solo
-- worker's own record, not an orphan to be repaired. Repairing the DATA here would have meant inventing
-- a hive for somebody who does not have one.
--
-- THE TELL, and the reason this is worth a migration rather than a patch. The trigger's OWN actor lookup
-- already handles the null:
--
--     WHERE hm.auth_uid = auth.uid() AND (NEW.hive_id IS NULL OR hm.hive_id = NEW.hive_id)
--
-- The author knew hive_id could be null, guarded the SELECT for it, and then wrote the INSERT as though
-- it could not. One side of a paired fact was defended and the other was not.
--
-- THE FIX. hive_audit_log is, by name and by its RLS, a per-hive log: every policy on it scopes rows to
-- a hive the reader belongs to. A row with no hive has no audience there - the audit exists so a HIVE can
-- see whether a late PM was quietly made to look on-time, and a solo worker has no supervisor for whom
-- that question exists. So the trigger returns early for a hive-less completion instead of fabricating a
-- hive or widening the column. The amendment proceeds; nothing is logged to a hive that is not involved.
--
-- Everything else in the function is unchanged, including the days_moved arithmetic an auditor reads.
-- The body below was diffed against pg_get_functiondef() rather than retyped from the error message: a
-- first pass of this file had the actor fallback as '(unknown actor)' where the shipped function says
-- 'unknown', which a CREATE OR REPLACE would have changed silently. The actor lookup also drops its
-- `NEW.hive_id IS NULL OR` arm, which is now unreachable - the early return above owns that case.
--
-- NOT APPLIED. Migrations are Ian's gate; this file is written and left for him.

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

  -- A hive-less (solo) completion has no hive audit log to be written to, and hive_audit_log.hive_id is
  -- NOT NULL. Amending it is legitimate; auditing it TO A HIVE is not, because there is no hive.
  IF NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND hm.hive_id = NEW.hive_id
   LIMIT 1;

  INSERT INTO public.hive_audit_log (
    hive_id, actor, action, target_type, target_id, target_name, meta
  ) VALUES (
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
