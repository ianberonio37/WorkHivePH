-- T108 (2026-08-25): extinguish the SHARPEST silent-work row — "work order assigned to me".
--
-- THE HOLE: wo_assigned_to renders as a badge on the entry, and NOTHING tells the
-- assignee — they discover their work by scrolling (the silent-work class the
-- someone-to-you registry names first). Same guarded-wrapper pattern as
-- notify_submission_decided (mig 003): the caller cannot pick recipients or write copy.
--
-- Guards:
--   * the entry row resolves hive + assignee SERVER-side from p_entry_id;
--   * the caller must be an ACTIVE MEMBER of that entry's hive (assignment is an edit
--     any member can make in the current model; the notification follows the same rule);
--   * SELF-assignment pushes nothing (you know what you just did);
--   * copy composed here; the deep link lands on the logbook filtered to Open work.
--
-- Reach honesty: wo_assigned_to is FREE TEXT — a name that matches no active member's
-- worker_name resolves to no auth_uid and nothing is sent (the registry's T61/T9 note);
-- push reaches only opt-in subscribers. Both limits are the recorded remainder, not
-- hidden. Re-runnable.

CREATE OR REPLACE FUNCTION public.notify_wo_assigned(p_entry_id text)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_hive uuid; v_assignee text; v_machine text; v_uid uuid; v_caller text;
BEGIN
  SELECT hive_id, wo_assigned_to, machine INTO v_hive, v_assignee, v_machine
  FROM public.logbook WHERE id = p_entry_id;
  IF v_hive IS NULL OR v_assignee IS NULL OR btrim(v_assignee) = '' THEN RETURN; END IF;

  SELECT hm.worker_name INTO v_caller
  FROM public.hive_members hm
  WHERE hm.hive_id = v_hive
    AND hm.worker_name IN (SELECT public.auth_worker_names())
    AND hm.status = 'active'
  LIMIT 1;
  IF v_caller IS NULL THEN
    RAISE EXCEPTION 'only an active member of the entry''s hive may notify';
  END IF;
  IF lower(btrim(v_assignee)) = lower(v_caller) THEN RETURN; END IF;  -- self-assign: no push

  SELECT auth_uid INTO v_uid FROM public.hive_members
  WHERE hive_id = v_hive AND lower(worker_name) = lower(btrim(v_assignee))
    AND status = 'active' AND auth_uid IS NOT NULL
  LIMIT 1;
  IF v_uid IS NULL THEN RETURN; END IF;  -- free-text name with no member match: honest no-op

  PERFORM public.enqueue_user_push(
    ARRAY[v_uid],
    'Work order assigned to you',
    COALESCE(v_machine, 'A job') || ' was assigned to you by ' || v_caller || '. Open the Logbook to see it.',
    '/logbook.html?status=Open'
  );
END $$;

GRANT EXECUTE ON FUNCTION public.notify_wo_assigned(text) TO authenticated;

NOTIFY pgrst, 'reload schema';
