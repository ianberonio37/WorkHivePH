-- 20260730000007_scope_audit_actor_lookup_to_the_rows_hive.sql
--
-- Two audit triggers resolved the acting worker WITHOUT scoping to the hive the audited row belongs to:
--
--     SELECT hm.worker_name INTO v_actor FROM public.hive_members hm
--      WHERE hm.auth_uid = auth.uid()
--      LIMIT 1;                       -- <- any membership, arbitrarily
--
-- `LIMIT 1` with no ORDER BY and no hive predicate picks an arbitrary membership, so a member of two hives
-- could have an amendment in hive A logged under the worker_name they use in hive B. This platform has been
-- bitten by the same shape before ([[feedback_resolving_live_is_not_enough_be_deterministic]] - a limit(1)
-- that picked the wrong hive).
--
-- MEASURED, NOT ASSUMED: it is LATENT, not live. There are 2 multi-hive members today and ZERO of them use a
-- different worker_name across their memberships, so the arbitrary pick currently returns the same string
-- either way. It becomes a real misattribution the first time one person is "Pablo Aguilar" in one hive and
-- "P. Aguilar" in another - which needs no code change to happen.
--
-- The fix is not invented: FIVE sibling audit triggers already carry exactly this predicate
-- (audit_asset_approval_decision, audit_asset_node_delete, audit_pm_asset_delete,
-- audit_pm_scope_item_schedule_change, guard_and_audit_project_removal). The class was hardened on five of
-- seven and these two were missed, which is why the inconsistency itself is the evidence. This copies the
-- neighbouring form verbatim, including the `IS NULL OR` allowance so a hive-less row still resolves an actor.
--
-- Found while sweeping the row-version class of migs 20260730000005/6 across every trigger that combines an
-- authority predicate with a write. That sweep's authority half found three live exploits; this is the
-- attribution half, and it found one latent inconsistency and five functions already correct.
--
-- NOTE ON MY OWN FIRST MEASUREMENT: a regex that matched only `auth_uid = ... AND hm.hive_id` reported all
-- SEVEN as unscoped, because the five correct ones write the predicate in a parenthesised `IS NULL OR` form.
-- Reading each lookup verbatim corrected 7 to 2. A count taken with the wrong instrument is not a count.
--
-- Both definitions were EXTRACTED with pg_get_functiondef and one anchored replacement applied each, the
-- builder asserting the unscoped text appears exactly once per function.

CREATE OR REPLACE FUNCTION public.audit_logbook_post_close_amendment()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
BEGIN
  -- Only rows that were already signed off. Everything else is an ordinary edit.
  IF COALESCE(OLD.status, '') <> 'Closed' THEN
    RETURN NEW;
  END IF;

  -- Ignore no-op updates (a re-save that changed nothing is not an amendment).
  IF NEW IS NOT DISTINCT FROM OLD THEN
    RETURN NEW;
  END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND (NEW.hive_id IS NULL OR hm.hive_id = NEW.hive_id)
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, NEW.worker_name, 'unknown'),
    CASE WHEN COALESCE(NEW.status, '') <> 'Closed'
         THEN 'reopen_closed_logbook_entry'
         ELSE 'amend_closed_logbook_entry' END,
    'logbook',
    NEW.id,
    COALESCE(NEW.machine, '(no machine)'),
    jsonb_build_object(
      'prev_status',    OLD.status,
      'new_status',     NEW.status,
      'closed_at_was',  OLD.closed_at,
      'closed_at_now',  NEW.closed_at,
      'source',         'db_trigger'
    )
  );

  RETURN NEW;
END;
$function$;

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
     AND (NEW.hive_id IS NULL OR hm.hive_id = NEW.hive_id)
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
