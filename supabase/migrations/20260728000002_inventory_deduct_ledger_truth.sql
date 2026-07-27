-- ─────────────────────────────────────────────────────────────────────────────
-- inventory_deduct: record the quantity that actually MOVED, not the one requested.
--
-- FOUND BY THE LG9 PARTS SWEEP (2026-07-28, LOGBOOK_DEEPWALK_EXPANSION_ROADMAP):
-- the balance is clamped -- `v_qty := GREATEST(0, v_qty - p_qty)` -- which is right, stock should
-- never go negative. But the ledger row was written with `qty_change = -p_qty`, the amount the
-- caller ASKED for. Whenever a deduction is clamped, those two disagree and the ledger stops
-- reconciling: consume 5 of a part with 2 on hand and the balance moves by 2 while the ledger
-- claims 5 left the shelf. Proven live by deducting 999,999 from an item holding 0 -- the call
-- succeeded, the balance stayed 0, and inventory_transactions recorded qty_change = -999999
-- against qty_after = 0.
--
-- That matters because this ledger is the audit trail for stock movement, and replaying it (summing
-- qty_change) is how a balance gets verified. A row whose change cannot be reconciled to its own
-- qty_after poisons that replay permanently, and silently -- the same defect class as the rest of
-- this arc: a record that does not match what actually happened.
--
-- The fix is deliberately minimal: keep the clamp, keep every caller's contract (the function still
-- returns the new balance and never raises on over-draw), and record the REAL delta. Callers that
-- want to reject an over-draw can compare their requested qty against the returned balance; nothing
-- here changes when stock is sufficient, which is the overwhelmingly common path.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.inventory_deduct(
  p_item_id text,
  p_qty     numeric,
  p_note    text DEFAULT NULL::text,
  p_job_ref text DEFAULT NULL::text,
  p_type    text DEFAULT 'use'::text,
  p_txn_id  text DEFAULT NULL::text)
RETURNS numeric
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_qty    numeric;
  v_before numeric;
  v_moved  numeric;
  v_hive   uuid;
  v_worker text;
  v_uid    uuid := auth.uid();
BEGIN
  IF p_qty IS NULL OR p_qty < 0 THEN
    RAISE EXCEPTION 'inventory_deduct: qty must be >= 0' USING ERRCODE = '22023';
  END IF;

  -- Lock the item row (closes the concurrent read-modify-write race) + read state.
  SELECT qty_on_hand, hive_id, worker_name
    INTO v_qty, v_hive, v_worker
    FROM public.inventory_items
   WHERE id = p_item_id
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'inventory_deduct: item % not found', p_item_id USING ERRCODE = 'P0002';
  END IF;

  -- Tenancy self-scope (DEFINER bypasses RLS, so we re-check membership here).
  IF v_hive IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.hive_members hm
         WHERE hm.hive_id = v_hive
           AND hm.auth_uid = v_uid
           AND hm.status = 'active'
     ) THEN
    RAISE EXCEPTION 'inventory_deduct: caller is not an active member of the item''s hive'
      USING ERRCODE = '42501';
  END IF;

  v_before := v_qty;
  v_qty    := GREATEST(0, v_qty - p_qty);
  v_moved  := v_before - v_qty;   -- what actually left the shelf, never more than was there

  UPDATE public.inventory_items
     SET qty_on_hand = v_qty, updated_at = now()
   WHERE id = p_item_id;

  INSERT INTO public.inventory_transactions
    (id, item_id, worker_name, hive_id, qty_change, qty_after, type, note, job_ref, auth_uid)
  VALUES
    (COALESCE(p_txn_id, gen_random_uuid()::text), p_item_id, COALESCE(v_worker, 'system'),
     v_hive, -v_moved, v_qty, COALESCE(p_type, 'use'), p_note, p_job_ref, v_uid);

  RETURN v_qty;
END;
$function$;
