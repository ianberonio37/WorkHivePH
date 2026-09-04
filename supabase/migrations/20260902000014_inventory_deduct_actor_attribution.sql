-- Cluster 3 / critic T11 (2026-09-02): AUDIT MISATTRIBUTION in inventory_deduct.
-- The ledger row's worker_name was set to v_worker = inventory_items.worker_name — the item's
-- OWNER/creator — not the person performing the use. So a part pulled by Bryan from an item Leandro
-- registered logged as "Leandro used 1" (reproduced live x2: auth_uid=bryangarcia, name='Leandro
-- Marquez'). auth_uid was already the real actor; only the human-readable name lied — and the ledger
-- is the audit trail a supervisor reads to answer "who took this part". The XP and exam paths already
-- attribute by resolving the actor's name from their auth_uid; the ledger now does the same:
-- worker_name is the ACTOR's active hive_members name, falling back to the item owner only when the
-- actor has no resolvable name in the item's hive (a service/system write). Message/logic otherwise
-- byte-identical to 20260728000002 (the ledger-truth qty_change fix is preserved).
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
SET search_path = public
AS $function$
DECLARE
  v_qty    numeric;
  v_hive   uuid;
  v_worker text;
  v_actor  text;
  v_before numeric;
  v_moved  numeric;
  v_uid    uuid := auth.uid();
BEGIN
  IF p_qty IS NULL OR p_qty < 0 THEN
    RAISE EXCEPTION 'inventory_deduct: qty must be >= 0' USING ERRCODE = '22023';
  END IF;

  SELECT qty_on_hand, hive_id, worker_name
    INTO v_qty, v_hive, v_worker
    FROM public.inventory_items
   WHERE id = p_item_id
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'inventory_deduct: item % not found', p_item_id USING ERRCODE = 'P0002';
  END IF;

  IF v_hive IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.hive_members hm
         WHERE hm.hive_id = v_hive
           AND hm.auth_uid = v_uid
           AND hm.status = 'active'
     ) THEN
    RAISE EXCEPTION 'inventory_deduct: caller is not an active member of the item''s hive'
      USING ERRCODE = '42501';
  END IF;

  -- T11 fix: attribute to the ACTOR, resolved from their auth_uid in the item's hive (the
  -- same JWT->name mapping the XP/exam paths use). Fall back to the item owner only for a
  -- system/service write with no member name (v_uid null or unresolved).
  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.hive_id = v_hive AND hm.auth_uid = v_uid AND hm.status = 'active'
   LIMIT 1;

  v_before := v_qty;
  v_qty    := GREATEST(0, v_qty - p_qty);
  v_moved  := v_before - v_qty;

  UPDATE public.inventory_items
     SET qty_on_hand = v_qty, updated_at = now()
   WHERE id = p_item_id;

  INSERT INTO public.inventory_transactions
    (id, item_id, worker_name, hive_id, qty_change, qty_after, type, note, job_ref, auth_uid)
  VALUES
    (COALESCE(p_txn_id, gen_random_uuid()::text), p_item_id, COALESCE(v_actor, v_worker, 'system'),
     v_hive, -v_moved, v_qty, COALESCE(p_type, 'use'), p_note, p_job_ref, v_uid);

  RETURN v_qty;
END;
$function$;

REVOKE ALL ON FUNCTION public.inventory_deduct(text, numeric, text, text, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.inventory_deduct(text, numeric, text, text, text, text) TO authenticated, service_role;
