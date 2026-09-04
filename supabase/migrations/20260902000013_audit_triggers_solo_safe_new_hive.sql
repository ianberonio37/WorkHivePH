-- VEHICLE SEED VM7 (2026-09-02): THREE more audit triggers aborted SOLO edits.
--
-- The 000008/000009 class was enumerated on prosrc ~ OLD.hive_id - too narrow: these three key
-- the insert on NEW.hive_id, and their existing 'hive_id IS NULL' clauses guard only the ACTOR
-- lookup (the fallback-guards-the-decoration shape), so the sweep read them as safe. Probed live
-- as a solo user: schedule amendment (VM7 staging), closed-entry amendment, and status-decision
-- updates ALL aborted on hive_audit_log.hive_id NOT NULL. audit_pm_completion_amendment probed
-- OK and is untouched. Fix: the same early return the delete-audit siblings got.

CREATE OR REPLACE FUNCTION public.audit_pm_scope_item_schedule_change()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
  v_was   integer;
  v_now   integer;
BEGIN
  -- SOLO lane (2026-09-02, VM7 walk): hive_audit_log.hive_id is NOT NULL and its audience
  -- is the hive. A hive-less row has neither; without this early return the audit INSERT
  -- ABORTS the user's own edit (proven live per-fn in rolled-back probes).
  IF NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;

  IF NEW.frequency   IS NOT DISTINCT FROM OLD.frequency
     AND NEW.anchor_date IS NOT DISTINCT FROM OLD.anchor_date
     AND NEW.item_text   IS NOT DISTINCT FROM OLD.item_text THEN
    RETURN NEW;
  END IF;

  -- Same mapping v_pm_scope_items_truth uses, so the recorded days match the schedule that results.
  v_was := CASE lower(btrim(COALESCE(OLD.frequency, '')))
             WHEN 'daily' THEN 1 WHEN 'weekly' THEN 7
             WHEN 'biweekly' THEN 14 WHEN 'fortnightly' THEN 14
             WHEN 'monthly' THEN 30 WHEN 'quarterly' THEN 90
             WHEN 'semi-annual' THEN 180 WHEN 'semiannual' THEN 180 WHEN 'semi annual' THEN 180
             WHEN 'annual' THEN 365 WHEN 'yearly' THEN 365 ELSE 30 END;
  v_now := CASE lower(btrim(COALESCE(NEW.frequency, '')))
             WHEN 'daily' THEN 1 WHEN 'weekly' THEN 7
             WHEN 'biweekly' THEN 14 WHEN 'fortnightly' THEN 14
             WHEN 'monthly' THEN 30 WHEN 'quarterly' THEN 90
             WHEN 'semi-annual' THEN 180 WHEN 'semiannual' THEN 180 WHEN 'semi annual' THEN 180
             WHEN 'annual' THEN 365 WHEN 'yearly' THEN 365 ELSE 30 END;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND (NEW.hive_id IS NULL OR hm.hive_id = NEW.hive_id)
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, 'unknown'),
    'amend_pm_schedule',
    'pm_scope_items',
    NEW.id::text,
    COALESCE(NEW.item_text, '(unnamed task)'),
    jsonb_build_object(
      'frequency_was',      OLD.frequency,
      'frequency_now',      NEW.frequency,
      -- The number the word resolves to: "Weekly -> Annual" is meaningless without "7 -> 365".
      'frequency_days_was', v_was,
      'frequency_days_now', v_now,
      'days_shifted',       v_now - v_was,
      'anchor_was',         OLD.anchor_date,
      'anchor_now',         NEW.anchor_date,
      'item_text_was',      CASE WHEN NEW.item_text IS DISTINCT FROM OLD.item_text
                                 THEN OLD.item_text END,
      'source',             'db_trigger'
    )
  );

  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.audit_logbook_post_close_amendment()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
BEGIN
  -- SOLO lane (2026-09-02, VM7 walk): hive_audit_log.hive_id is NOT NULL and its audience
  -- is the hive. A hive-less row has neither; without this early return the audit INSERT
  -- ABORTS the user's own edit (proven live per-fn in rolled-back probes).
  IF NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;

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

CREATE OR REPLACE FUNCTION public.audit_asset_approval_decision()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor text;
BEGIN
  -- SOLO lane (2026-09-02, VM7 walk): hive_audit_log.hive_id is NOT NULL and its audience
  -- is the hive. A hive-less row has neither; without this early return the audit INSERT
  -- ABORTS the user's own edit (proven live per-fn in rolled-back probes).
  IF NEW.hive_id IS NULL THEN
    RETURN NEW;
  END IF;

  -- Only the moment a submission is DECIDED.
  IF NEW.status IS NOT DISTINCT FROM OLD.status
     OR NEW.status NOT IN ('approved', 'rejected') THEN
    RETURN NEW;
  END IF;

  -- The deciding identity, resolved server-side. approved_by is a client-supplied TEXT name and
  -- cannot be trusted to say who actually performed the write.
  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND (NEW.hive_id IS NULL OR hm.hive_id = NEW.hive_id)
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    NEW.hive_id,
    COALESCE(v_actor, 'unknown'),
    CASE WHEN NEW.status = 'approved' THEN 'approve_asset_node' ELSE 'reject_asset_node' END,
    'asset_nodes',
    NEW.id::text,
    COALESCE(NEW.tag, NEW.name, '(unnamed asset)'),
    jsonb_build_object(
      'status_was',       OLD.status,
      'status_now',       NEW.status,
      'rejection_reason', NEW.rejection_reason,
      'submitted_by',     NEW.submitted_by,
      -- Recorded separately from `actor` so a mismatch between the claimed approver and the
      -- identity that actually wrote is visible rather than silently reconciled.
      'approved_by_claimed', NEW.approved_by,
      'decided_by',       v_actor,
      'source',           'db_trigger'
    )
  );

  RETURN NEW;
END;
$function$;
