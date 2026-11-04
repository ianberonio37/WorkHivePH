-- A supervisor can move a teammate's work order: approve, assign, verify, reject (2026-11-04, Wave GJ, J2 hand-off 2).
--
-- FOUND BY THE GROUP-JOURNEY WALK. Two people, one breakdown: the worker logs it, the supervisor must hand the job to
-- someone. logbook.html's own form says "Workers move their own assigned items forward; supervisors approve, assign,
-- and verify", and tg_guard_approval (20260707000002) reserves exactly those four wo_states for an active supervisor.
-- But logbook's UPDATE policy is owner-only (auth_uid = auth.uid()), so a supervisor could never write any of them on
-- anybody else's entry - the view modal says "Only the person who wrote an entry can edit or delete it", and the
-- seven-state workflow could not be driven by the one role it was built for. The only supervisor path that existed was
-- a departed member's open job (assignDepartedEntry, which the owner-only policy's departed branch allows).
--
-- THE FIX IS A NARROW DOOR, NOT A WIDER POLICY. Widening logbook's UPDATE policy to supervisors would let them rewrite a
-- worker's problem, action and downtime - the worker's own account. This function changes two columns only (wo_state,
-- wo_assigned_to), for an active supervisor of the entry's own hive, into the four supervisor states, with an assignee
-- who is an active member of that hive; it writes the trail line and the assignee's push (notify_wo_assigned).
-- tg_guard_approval still runs on the update (auth.uid() is the caller inside a definer), so the role is checked twice.

CREATE OR REPLACE FUNCTION public.set_logbook_wo(p_entry_id text, p_state text, p_assignee text DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_hive uuid; v_status text; v_deleted timestamptz; v_machine text; v_prev text;
  v_caller text; v_to text;
BEGIN
  IF p_state NOT IN ('approved', 'assigned', 'verified', 'rejected') THEN
    RAISE EXCEPTION 'a supervisor sets approved, assigned, verified or rejected (got %)', coalesce(p_state, 'nothing')
      USING ERRCODE = '22023';
  END IF;

  SELECT hive_id, status, deleted_at, machine, wo_assigned_to INTO v_hive, v_status, v_deleted, v_machine, v_prev
  FROM public.logbook WHERE id = p_entry_id;
  IF v_hive IS NULL OR v_deleted IS NOT NULL THEN
    RAISE EXCEPTION 'that entry is not in a hive you supervise' USING ERRCODE = '42501';
  END IF;

  SELECT hm.worker_name INTO v_caller
  FROM public.hive_members hm
  WHERE hm.hive_id = v_hive AND hm.auth_uid = auth.uid() AND hm.role = 'supervisor' AND hm.status = 'active'
  LIMIT 1;
  IF v_caller IS NULL THEN
    RAISE EXCEPTION 'only an active supervisor of the entry''s hive may move its work order' USING ERRCODE = '42501';
  END IF;

  IF p_state IN ('approved', 'assigned') AND coalesce(v_status, 'Open') <> 'Open' THEN
    RAISE EXCEPTION 'this job is closed - it can be verified or rejected, not assigned' USING ERRCODE = '22023';
  END IF;

  IF p_state = 'assigned' THEN
    IF p_assignee IS NULL OR btrim(p_assignee) = '' THEN
      RAISE EXCEPTION 'say who takes the job' USING ERRCODE = '22023';
    END IF;
    SELECT hm.worker_name INTO v_to
    FROM public.hive_members hm
    WHERE hm.hive_id = v_hive AND hm.status = 'active' AND lower(hm.worker_name) = lower(btrim(p_assignee))
    LIMIT 1;
    IF v_to IS NULL THEN
      RAISE EXCEPTION '% is not an active member of this hive', btrim(p_assignee) USING ERRCODE = '22023';
    END IF;
  END IF;

  UPDATE public.logbook
     SET wo_state = p_state,
         wo_assigned_to = coalesce(v_to, wo_assigned_to),
         updated_at = now()
   WHERE id = p_entry_id;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (v_hive, v_caller, 'set_work_order', 'logbook', p_entry_id, coalesce(v_machine, '(no machine)'),
          jsonb_build_object('state', p_state, 'to', v_to, 'from', v_prev));

  IF v_to IS NOT NULL AND lower(v_to) IS DISTINCT FROM lower(coalesce(v_prev, '')) THEN
    PERFORM public.notify_wo_assigned(p_entry_id);
  END IF;

  RETURN jsonb_build_object('id', p_entry_id, 'wo_state', p_state, 'wo_assigned_to', coalesce(v_to, v_prev));
END $function$;

REVOKE ALL ON FUNCTION public.set_logbook_wo(text, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.set_logbook_wo(text, text, text) TO authenticated;
