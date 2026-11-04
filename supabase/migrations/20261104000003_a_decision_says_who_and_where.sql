-- A submission's decision says who decided, and sends a machine's owner to the machine (2026-11-04, Wave GJ, J9 hand-off 5).
--
-- notify_submission_decided pushes the worker when a supervisor approves or rejects what they submitted. Read across the
-- hand-off (the group-journey walk's U lens: the receiver can tell who did it and where to go), three things were wrong:
--   * the push never said WHO decided - "M-002 was approved and published to the hive." - though only one person could;
--   * an approved MACHINE (asset_nodes) sent the worker to /logbook.html, where nothing about the decision appears;
--   * a rejected MACHINE said "open Inventory to see why" - a page that holds parts, not machines - so the worker was sent
--     to the wrong place to learn why their machine was turned down.
-- Now the body names the supervisor, a part goes to Inventory and a machine to Asset Hub, where the submitter's pending
-- and rejected machines are listed (asset-hub.html's submissions panel), opened on the machine itself.

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
    v_url := '/inventory.html';
  ELSE
    v_where := 'Asset Hub';
    v_url := '/asset-hub.html?node_id=' || p_item_id;
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
