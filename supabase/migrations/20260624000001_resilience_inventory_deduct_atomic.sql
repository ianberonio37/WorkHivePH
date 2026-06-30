-- ============================================================================
-- Arc S (Resilience / DR) — C-lens: atomic inventory deduction (no partial-write)
-- ============================================================================
-- logbook.html deducts a used part in TWO sequential client writes:
--   UPDATE inventory_items SET qty_on_hand = qty_on_hand - n   (the balance)
--   INSERT inventory_transactions (...)                        (the audit record)
-- If the UPDATE succeeds but the INSERT fails (network blip mid-pair), the balance
-- changes with NO transaction record: the audit trail is corrupt and the deduction
-- is unreconcilable. This is the one genuine partial-write CORRUPTION path in the
-- C-lens sweep (the pm/project/cmms multi-writes are recoverable mirrors that
-- already surface their failure; this one silently breaks an invariant).
--
-- inventory_deduct() does both in ONE function call = ONE transaction: a plpgsql
-- function rolls back ALL its statements if any raises, so the balance and the
-- record always agree (atomic, exactly-once on retry when paired with a stable txn id).
--
-- SECURITY DEFINER (the function recomputes qty server-side under a row lock, which
-- also closes the read-modify-write race on concurrent deductions) + the mandatory
-- tenancy self-scope: the caller's auth.uid() must be an ACTIVE member of the item's
-- hive (validate_definer_tenant_gate / Arc G-R). search_path pinned (CVE-2018-1058).
-- auth_uid is stamped from auth.uid() so the INSERT satisfies inventory_transactions
-- RLS write-check. EXECUTE revoked from PUBLIC+anon, granted to authenticated+service_role.
--
-- Forward-only. Idempotent (CREATE OR REPLACE + idempotent GRANT/REVOKE).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.inventory_deduct(
  p_item_id text,
  p_qty     numeric,
  p_note    text DEFAULT NULL,
  p_job_ref text DEFAULT NULL,
  p_type    text DEFAULT 'use',
  p_txn_id  text DEFAULT NULL
) RETURNS numeric
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_qty    numeric;
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

  v_qty := GREATEST(0, v_qty - p_qty);

  UPDATE public.inventory_items
     SET qty_on_hand = v_qty, updated_at = now()
   WHERE id = p_item_id;

  INSERT INTO public.inventory_transactions
    (id, item_id, worker_name, hive_id, qty_change, qty_after, type, note, job_ref, auth_uid)
  VALUES
    (COALESCE(p_txn_id, gen_random_uuid()::text), p_item_id, COALESCE(v_worker, 'system'),
     v_hive, -p_qty, v_qty, COALESCE(p_type, 'use'), p_note, p_job_ref, v_uid);

  RETURN v_qty;
END;
$$;

REVOKE ALL ON FUNCTION public.inventory_deduct(text, numeric, text, text, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.inventory_deduct(text, numeric, text, text, text, text) TO authenticated, service_role;
