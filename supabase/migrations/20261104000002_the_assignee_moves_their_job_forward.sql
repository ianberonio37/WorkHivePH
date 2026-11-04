-- The member a job is assigned to can move it forward: start it, finish it (2026-11-04, Wave GJ, found preparing J9).
--
-- set_logbook_wo (20261104000001) lets a supervisor hand a teammate's job to someone. The form's own words are
-- "Workers move their own assigned items forward; supervisors approve, assign, and verify" - but the assignee of a job
-- somebody else raised is not its author, and logbook's UPDATE policy is the author's alone, so the person the job was
-- handed to could never say they had started it or finished it. The push told them "Open the Logbook to see it" and
-- the job then sat at "assigned" until its author or a supervisor moved it.
--
-- A NARROW DOOR AGAIN: this changes wo_state only, into the two worker states (in_progress, completed), for the active
-- member of the entry's hive whose name the entry is assigned to, on an open entry; the trail line names them. It does
-- not let the assignee rewrite the entry, close it, or re-assign it. tg_guard_approval still runs on the update.

CREATE OR REPLACE FUNCTION public.advance_assigned_wo(p_entry_id text, p_state text)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_hive uuid; v_status text; v_deleted timestamptz; v_machine text; v_to text; v_prev text; v_me text;
BEGIN
  IF p_state NOT IN ('in_progress', 'completed') THEN
    RAISE EXCEPTION 'the person a job is assigned to moves it to in progress or completed (got %)', coalesce(p_state, 'nothing')
      USING ERRCODE = '22023';
  END IF;

  SELECT hive_id, status, deleted_at, machine, wo_assigned_to, wo_state
    INTO v_hive, v_status, v_deleted, v_machine, v_to, v_prev
  FROM public.logbook WHERE id = p_entry_id;
  IF v_hive IS NULL OR v_deleted IS NOT NULL OR v_to IS NULL THEN
    RAISE EXCEPTION 'that job is not assigned to you' USING ERRCODE = '42501';
  END IF;

  SELECT hm.worker_name INTO v_me
  FROM public.hive_members hm
  WHERE hm.hive_id = v_hive AND hm.auth_uid = auth.uid() AND hm.status = 'active'
    AND lower(hm.worker_name) = lower(btrim(v_to))
  LIMIT 1;
  IF v_me IS NULL THEN
    RAISE EXCEPTION 'that job is not assigned to you' USING ERRCODE = '42501';
  END IF;

  IF coalesce(v_status, 'Open') <> 'Open' THEN
    RAISE EXCEPTION 'this job is already closed' USING ERRCODE = '22023';
  END IF;

  UPDATE public.logbook SET wo_state = p_state, updated_at = now() WHERE id = p_entry_id;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (v_hive, v_me, 'advance_work_order', 'logbook', p_entry_id, coalesce(v_machine, '(no machine)'),
          jsonb_build_object('state', p_state, 'from', v_prev));

  RETURN jsonb_build_object('id', p_entry_id, 'wo_state', p_state);
END $function$;

REVOKE ALL ON FUNCTION public.advance_assigned_wo(text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.advance_assigned_wo(text, text) TO authenticated;
