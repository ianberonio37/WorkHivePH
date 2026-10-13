-- ★EDITING A PART'S QUANTITY MOVED THE STOCK AND WROTE NOTHING TO THE LEDGER (2026-10-08, found authoring the
-- UI-write recipes). inventory.html submitPart's edit path sends qty_on_hand inside the part UPDATE (ocUpdate,
-- the optimistic-concurrency path every loaded part takes, because every loaded part has an updated_at). Use and
-- Restock move stock through inventory_deduct / inventory_restock, which update the balance AND append the
-- inventory_transactions row in one transaction; the edit form did neither half of that - the balance moved and
-- the ledger never heard about it. The ledger is the trail ("stock movements are not audited here because
-- inventory_transactions itself is the trail") and the balance is supposed to equal its newest qty_after, so an
-- edited count was an untraceable movement AND a reconciliation break.
--
-- inventory_adjust is the edit form's equivalent of restock/deduct: ONE transaction that writes the 'adjustment'
-- ledger row and moves the balance. The row goes in FIRST and inventory_sync_balance_from_ledger mirrors its
-- qty_after onto qty_on_hand - so guard_staged_stock still sees the pre-adjustment balance and still refuses a
-- count that would eat stock staged for a predicted failure. 'adjustment' carries an ABSOLUTE count, which is
-- why tg_inventory_txn_chain_qty_after leaves it alone.
--
-- SECURITY INVOKER: the caller's authority is exactly what the part UPDATE already required. `FOR UPDATE` applies
-- inventory_items_write's USING clause, so a part the caller may not edit is "not found" here too, and the ledger
-- INSERT passes inventory_transactions_write's WITH CHECK as the caller.
--
-- p_expected_qty is the count the person was looking at when they edited. If the stock moved since (someone used
-- or restocked it), the function refuses rather than overwrite a movement it never saw.

CREATE OR REPLACE FUNCTION public.inventory_adjust(p_item_id text, p_expected_qty numeric, p_new_qty numeric,
                                                   p_note text DEFAULT NULL)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_qty    numeric;
  v_hive   uuid;
  v_owner  text;
  v_actor  text;
  v_after  numeric;
  v_stamp  timestamptz;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Sign in to change stock.' USING ERRCODE = '42501';
  END IF;
  IF p_new_qty IS NULL OR p_new_qty < 0 THEN
    RAISE EXCEPTION 'A quantity on hand must be 0 or more.' USING ERRCODE = '22023';
  END IF;

  SELECT qty_on_hand, hive_id, worker_name INTO v_qty, v_hive, v_owner
    FROM public.inventory_items
   WHERE id = p_item_id
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'not_found');
  END IF;

  IF p_expected_qty IS NOT NULL AND v_qty IS DISTINCT FROM p_expected_qty THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'changed', 'qty_on_hand', v_qty);
  END IF;

  IF v_qty IS NOT DISTINCT FROM p_new_qty THEN
    SELECT updated_at INTO v_stamp FROM public.inventory_items WHERE id = p_item_id;
    RETURN jsonb_build_object('ok', true, 'qty_on_hand', v_qty, 'qty_change', 0, 'updated_at', v_stamp);
  END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.hive_id = v_hive AND hm.auth_uid = auth.uid() AND hm.status = 'active'
   LIMIT 1;

  INSERT INTO public.inventory_transactions
    (item_id, worker_name, hive_id, qty_change, qty_after, type, note, auth_uid)
  VALUES
    (p_item_id, COALESCE(v_actor, v_owner, 'unknown'), v_hive,
     p_new_qty - COALESCE(v_qty, 0), p_new_qty, 'adjustment',
     COALESCE(NULLIF(btrim(p_note), ''), 'Edited via part form'), auth.uid());

  -- The balance is moved by the ledger's own trigger. Confirm it, so a trigger that ever stops mirroring
  -- cannot leave a ledger row the balance disagrees with: the exception rolls the row back too.
  SELECT qty_on_hand, updated_at INTO v_after, v_stamp FROM public.inventory_items WHERE id = p_item_id;
  IF v_after IS DISTINCT FROM p_new_qty THEN
    RAISE EXCEPTION 'The stock count did not move to % (it reads %), so nothing was recorded.', p_new_qty, v_after
      USING ERRCODE = 'P0001';
  END IF;

  RETURN jsonb_build_object('ok', true, 'qty_on_hand', v_after, 'qty_change', p_new_qty - COALESCE(v_qty, 0),
                            'updated_at', v_stamp);
END;
$function$;

COMMENT ON FUNCTION public.inventory_adjust(text, numeric, numeric, text) IS
  'Set a part''s quantity on hand from the part edit form: appends an ''adjustment'' row to inventory_transactions '
  'and moves the balance in ONE transaction (the edit-form sibling of inventory_restock / inventory_deduct). '
  'SECURITY INVOKER - the caller needs the same authority the part UPDATE needs. Returns {ok, qty_on_hand, '
  'qty_change, updated_at} or {ok:false, reason: not_found|changed}.';

REVOKE ALL ON FUNCTION public.inventory_adjust(text, numeric, numeric, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.inventory_adjust(text, numeric, numeric, text) TO authenticated, service_role;
