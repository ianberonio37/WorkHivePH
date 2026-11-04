-- ★A PUSH FROM ONE HIVE OPENED IN THE OTHER (2026-11-05, the group-journey walk GJ G-MULTI hand-off 3).
-- A person can belong to two hives (a contractor serving two plants), and every page reads the hive the device last
-- stood in. Supervisor A's "Work order assigned to you" push sent /logbook.html?status=Open with no hive in it, so a
-- contractor last standing in hive B opened B's logbook, where A's job does not exist - the push named a job the page
-- it opened could not show. The same held for an approval decision (/asset-hub.html?node_id=..., /inventory.html).
-- Each push now names its hive (&hive=<id>); the page start-up (utils.js whStartupHive) seats that hive when, and only
-- when, the signed-in account is an active member of it, and says so.

CREATE OR REPLACE FUNCTION public.notify_wo_assigned(p_entry_id text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
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
    '/logbook.html?status=Open&hive=' || v_hive::text
  );
END $function$;

CREATE OR REPLACE FUNCTION public.notify_submission_decided(p_table text, p_item_id text, p_decision text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_hive uuid; v_owner text; v_uid uuid; v_label text; v_by text; v_where text; v_url text;
BEGIN
  IF p_decision NOT IN ('approved', 'rejected') THEN
    RAISE EXCEPTION 'decision must be approved or rejected';
  END IF;

  IF p_table = 'inventory_items' THEN
    SELECT hive_id, worker_name, part_name INTO v_hive, v_owner, v_label
    FROM public.inventory_items WHERE id = p_item_id;
  ELSIF p_table = 'asset_nodes' THEN
    SELECT hive_id, worker_name, COALESCE(name, tag) INTO v_hive, v_owner, v_label
    FROM public.asset_nodes WHERE id::text = p_item_id;
  ELSE
    RAISE EXCEPTION 'unsupported table %', p_table;
  END IF;

  IF v_hive IS NULL OR v_owner IS NULL THEN RETURN; END IF;

  SELECT hm.worker_name INTO v_by
  FROM public.hive_members hm
  WHERE hm.hive_id = v_hive
    AND hm.worker_name IN (SELECT public.auth_worker_names())
    AND hm.role = 'supervisor' AND hm.status = 'active'
  LIMIT 1;
  IF v_by IS NULL THEN
    RAISE EXCEPTION 'only an active supervisor of the item''s hive may notify';
  END IF;

  SELECT auth_uid INTO v_uid FROM public.hive_members
  WHERE hive_id = v_hive AND worker_name = v_owner AND auth_uid IS NOT NULL
  LIMIT 1;
  IF v_uid IS NULL THEN RETURN; END IF;  -- legacy member with no auth link: nothing to push

  IF p_table = 'inventory_items' THEN
    v_where := 'Inventory';
    v_url := '/inventory.html?hive=' || v_hive::text;
  ELSE
    v_where := 'Asset Hub';
    v_url := '/asset-hub.html?node_id=' || p_item_id || '&hive=' || v_hive::text;
  END IF;

  PERFORM public.enqueue_user_push(
    ARRAY[v_uid],
    CASE WHEN p_decision = 'approved' THEN 'Submission approved' ELSE 'Submission needs changes' END,
    v_label || CASE WHEN p_decision = 'approved'
      THEN ' was approved by ' || v_by || ' and published to the hive.'
      ELSE ' was rejected by ' || v_by || ': open ' || v_where || ' to see why, fix it, and resubmit.' END,
    v_url
  );
END $function$;
