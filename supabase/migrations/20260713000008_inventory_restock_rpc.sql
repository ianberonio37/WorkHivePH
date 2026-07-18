-- 20260713000008_inventory_restock_rpc.sql
--
-- Inventory RESTOCK lost-update (P6 concurrent-edit) — bug-hunt 2026-07-13, inventory.html.
--
-- submitRestock did `items[idx].qty_on_hand += qty; saveInventory()` — a client read-modify-write
-- that upserts an ABSOLUTE qty_on_hand. Two concurrent restocks each read the same base, add their
-- own amount, and the last upsert overwrites the first (one restock LOST) — the increment twin of the
-- Use lost-update closed by routing submitUse through the atomic `inventory_deduct` RPC (FOR UPDATE).
-- inventory_deduct only DEDUCTS (p_qty >= 0, v_qty - p_qty), so restock needs its own atomic increment.
--
-- FIX: inventory_restock(p_item_id, p_qty, ...) mirrors inventory_deduct — FOR UPDATE row-lock closes
-- the race, re-checks hive membership (DEFINER bypasses RLS), atomically increments qty_on_hand, and
-- writes the inventory_transactions row server-side (type='restock', qty_change=+p_qty, qty_after=new),
-- keeping qty_on_hand == newest txn.qty_after (the DI §10.5 seesaw invariant). RETURNS the new qty.
-- EXECUTE granted to authenticated (a normal member restocks; the membership re-check is the gate).

BEGIN;

CREATE OR REPLACE FUNCTION public.inventory_restock(
  p_item_id text, p_qty numeric, p_note text DEFAULT NULL, p_txn_id text DEFAULT NULL)
  RETURNS numeric
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'pg_catalog', 'public'
AS $fn$
DECLARE
  v_qty numeric; v_hive uuid; v_worker text; v_uid uuid := auth.uid();
BEGIN
  IF p_qty IS NULL OR p_qty <= 0 THEN
    RAISE EXCEPTION 'inventory_restock: qty must be > 0' USING ERRCODE = '22023';
  END IF;
  SELECT qty_on_hand, hive_id, worker_name INTO v_qty, v_hive, v_worker
    FROM public.inventory_items WHERE id = p_item_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'inventory_restock: item % not found', p_item_id USING ERRCODE = 'P0002';
  END IF;
  -- Tenancy self-scope (DEFINER bypasses RLS, so re-check membership here).
  IF v_hive IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id = v_hive AND hm.auth_uid = v_uid AND hm.status = 'active') THEN
    RAISE EXCEPTION 'inventory_restock: caller is not an active member of the item''s hive'
      USING ERRCODE = '42501';
  END IF;
  v_qty := v_qty + p_qty;
  UPDATE public.inventory_items SET qty_on_hand = v_qty, updated_at = now() WHERE id = p_item_id;
  INSERT INTO public.inventory_transactions
    (id, item_id, worker_name, hive_id, qty_change, qty_after, type, note, auth_uid)
  VALUES
    (COALESCE(p_txn_id, gen_random_uuid()::text), p_item_id, COALESCE(v_worker, 'system'),
     v_hive, p_qty, v_qty, 'restock', p_note, v_uid);
  RETURN v_qty;
END; $fn$;

REVOKE ALL ON FUNCTION public.inventory_restock(text, numeric, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.inventory_restock(text, numeric, text, text) TO authenticated, service_role;

COMMIT;
