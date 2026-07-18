-- shift-brain P6 concurrent-edit fix (bug-hunt roadmap, 2026-07-17, found via live probe).
-- shift_plans is HIVE-SHARED (hive_id, no worker scope); its status (draft->published->archived) is
-- updated by `.update({status}).eq('id').eq('hive_id')` with NO forward-only transition guard. Two
-- supervisors racing (one publishes, one archives; or a stale re-publish of an archived plan) could
-- REGRESS the state machine. Add a DB-authoritative forward-only guard: draft(0)->published(1)->
-- archived(2), reject any NEW rank < OLD rank. (updated_at is already touch-triggered.)
CREATE OR REPLACE FUNCTION public.shift_plans_forward_only_status() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE r_old int; r_new int;
BEGIN
  r_old := CASE OLD.status WHEN 'draft' THEN 0 WHEN 'published' THEN 1 WHEN 'archived' THEN 2 ELSE 0 END;
  r_new := CASE NEW.status WHEN 'draft' THEN 0 WHEN 'published' THEN 1 WHEN 'archived' THEN 2 ELSE 0 END;
  IF r_new < r_old THEN
    RAISE EXCEPTION 'shift_plans: cannot regress status % -> % (forward-only draft->published->archived)',
      OLD.status, NEW.status USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS tg_shift_plans_forward_status ON public.shift_plans;
CREATE TRIGGER tg_shift_plans_forward_status
  BEFORE UPDATE OF status ON public.shift_plans
  FOR EACH ROW EXECUTE FUNCTION public.shift_plans_forward_only_status();
