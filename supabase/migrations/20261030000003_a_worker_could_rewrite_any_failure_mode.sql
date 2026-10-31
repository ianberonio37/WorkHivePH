-- A WORKER COULD REWRITE OR DELETE ANY MEMBER'S FAILURE MODE - AN APPROVED ONE INCLUDED.
--
-- Found 2026-10-30 walking Wave HS lens L2 ("each role sees the actions it may take") on asset-hub.html. The page gives a
-- supervisor Approve and Delete on a pending failure mode and gives a worker no action on anyone's mode ("workers see
-- all rows ... so they can edit their own"). The server held a different line: rcm_fmea_modes_write lets every active
-- member of the hive write every row, and tg_guard_approval protects only the approval columns and the deletion of
-- signed-off work. MEASURED, as Joel Cruz (worker, Batangas Refinery Maintenance), each rolled back:
--   UPDATE another member's APPROVED mode SET severity = 1, failure_mode = ...   -> 1 row   <-- an approved RPN rewritten,
--                                                                                               still marked approved
--   UPDATE another member's PENDING mode                                         -> 1 row
--   DELETE another member's PENDING mode                                         -> 1 row   <-- their analysis gone
--   DELETE another member's APPROVED mode                                        -> refused (the approval guard)
--
-- THE RULE, as the page states it: a supervisor of the hive may change any failure mode; a member may change or remove
-- only one they proposed, and only while it waits for approval - an approved mode is a signed-off record. Ownership is
-- created_by, which the page writes as the member's hive name (there is no auth_uid on this table), checked against the
-- caller's own membership row. A definer function acting for the platform (current_user is not `authenticated`) and a
-- server-side session (no auth.uid()) are not a member editing a row and pass, as on community_posts' guard.

CREATE OR REPLACE FUNCTION public.tg_rcm_fmea_modes_member_scope()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
  v_me text;
BEGIN
  IF auth.uid() IS NULL OR current_user <> 'authenticated' THEN
    RETURN COALESCE(NEW, OLD);
  END IF;
  IF OLD.hive_id IN (SELECT public.user_supervisor_hive_ids()) THEN
    RETURN COALESCE(NEW, OLD);        -- a supervisor of this hive keeps the record
  END IF;
  SELECT hm.worker_name INTO v_me FROM public.hive_members hm
   WHERE hm.hive_id = OLD.hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active' LIMIT 1;
  IF OLD.approved_at IS NOT NULL OR v_me IS NULL OR OLD.created_by IS DISTINCT FROM v_me THEN
    RAISE EXCEPTION 'Only a supervisor, or the member who proposed it while it waits for approval, can change this failure mode.'
      USING ERRCODE = '42501';
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS tg_rcm_fmea_modes_member_scope ON public.rcm_fmea_modes;
CREATE TRIGGER tg_rcm_fmea_modes_member_scope
  BEFORE UPDATE OR DELETE ON public.rcm_fmea_modes
  FOR EACH ROW
  EXECUTE FUNCTION public.tg_rcm_fmea_modes_member_scope();
