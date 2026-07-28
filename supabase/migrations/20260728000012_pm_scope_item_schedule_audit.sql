-- ─────────────────────────────────────────────────────────────────────────────
-- Changing a scope item's FREQUENCY rewrites an asset's whole schedule. Record it.
--
-- PMK3 SWEEP (PM deepwalk, 2026-07-28). The class says: for a record that drives a regulated
-- number, every path that can change it must leave a trace at the DATABASE. pm_completions got its
-- trigger in PM11 (a silent 400-day back-date) and pm_assets got one for deletion in PM12 (a worker
-- destroying 31 completion records). pm_scope_items had none — and PM8 established that the
-- frequency WORD is the scheduler:
--
--   v_pm_scope_items_truth derives frequency_days from it by CASE, and next_due_date from
--   last_completed_at + frequency_days. So editing 'Weekly' to 'Annual' does not just relabel a
--   badge — it moves next_due_date out by 358 days, clears the item's overdue flag, changes the
--   scheduled count get_pm_compliance_smrp divides by, and changes what counts as on-time.
--
-- One edit, nothing recorded, and the asset's compliance history is re-based. That is the same
-- shape as the back-dated completion, reached through the schedule instead of the record.
--
-- SCOPE: fires only on a change that alters what the schedule MEANS — frequency, anchor_date, or
-- item_text (the task a technician is being asked to perform). Fixing a typo in a description is
-- still recorded because item_text IS the instruction; there is no free-text field here that is
-- merely a note, unlike the logbook's notes column.
--
-- Records frequency_days on BOTH sides, derived the same way the view derives it, because "Weekly
-- -> Annual" means nothing to an auditor without "7 -> 365" beside it.
-- ─────────────────────────────────────────────────────────────────────────────

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

DROP TRIGGER IF EXISTS trg_pm_scope_item_schedule_audit ON public.pm_scope_items;
CREATE TRIGGER trg_pm_scope_item_schedule_audit
  AFTER UPDATE ON public.pm_scope_items
  FOR EACH ROW
  EXECUTE FUNCTION public.audit_pm_scope_item_schedule_change();
