-- T108 (2026-08-25): extinguish ONE silent-work row — "my submission approved/rejected".
--
-- THE HOLE: hive.html's approve/reject called pushNotif(), which renders into the
-- SUPERVISOR'S OWN in-page notification list — the SUBMITTER learned their fate only by
-- revisiting Inventory (a string is not an announcement until it reaches a user). The
-- outbox -> notify-push lane already exists, but enqueue_user_push is deliberately NOT
-- user-callable (a member could push-spam arbitrary members — the definer-cron-helper
-- lesson). So: a GUARDED wrapper the client may call.
--
-- Guards (each one closes an abuse path):
--   * decision vocabulary fixed ('approved'/'rejected') — no arbitrary push content;
--   * the item row resolves hive + submitter SERVER-side — the caller cannot pick
--     recipients or spoof another hive's item;
--   * the caller must be an ACTIVE SUPERVISOR of that item's hive;
--   * body text is composed here, never caller-supplied.
--
-- Reach honesty: push lands only for submitters who enabled alerts (opt-in web push);
-- the rejected-card copy ("Why rejected: ...") remains the always-there surface — this
-- adds the timely nudge, not the only path. Re-runnable (CREATE OR REPLACE + idempotent
-- grant).

CREATE OR REPLACE FUNCTION public.notify_submission_decided(
  p_table text, p_item_id text, p_decision text
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_hive uuid; v_owner text; v_uid uuid; v_label text;
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

  IF NOT EXISTS (
    SELECT 1 FROM public.hive_members hm
    WHERE hm.hive_id = v_hive
      AND hm.worker_name IN (SELECT public.auth_worker_names())
      AND hm.role = 'supervisor' AND hm.status = 'active'
  ) THEN
    RAISE EXCEPTION 'only an active supervisor of the item''s hive may notify';
  END IF;

  SELECT auth_uid INTO v_uid FROM public.hive_members
  WHERE hive_id = v_hive AND worker_name = v_owner AND auth_uid IS NOT NULL
  LIMIT 1;
  IF v_uid IS NULL THEN RETURN; END IF;  -- legacy member with no auth link: nothing to push

  PERFORM public.enqueue_user_push(
    ARRAY[v_uid],
    CASE WHEN p_decision = 'approved' THEN 'Submission approved' ELSE 'Submission needs changes' END,
    v_label || CASE WHEN p_decision = 'approved'
      THEN ' was approved and published to the hive.'
      ELSE ' was rejected: open Inventory to see why, fix it, and resubmit.' END,
    CASE WHEN p_table = 'inventory_items' THEN '/inventory.html' ELSE '/logbook.html' END
  );
END $$;

GRANT EXECUTE ON FUNCTION public.notify_submission_decided(text, text, text) TO authenticated;
