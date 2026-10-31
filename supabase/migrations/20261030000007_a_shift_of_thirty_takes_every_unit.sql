-- HS W2 (2026-10-30, tools/prove_hive_scale_burst.mjs inventory_transactions): thirty members each take one unit of the
-- same part. The deduct RPC locks the part's row and the balance is derived from the ledger chain - but the chain is
-- ordered by created_at, and a defaulted created_at is the TRANSACTION START, not the moment the lock was won. Measured:
-- at once, 29 deducts -> ledger -29, shelf 100 -> 83; one after another, 83 -> 61 against -29. Stamped at the write now.
-- Rewritten from the live definition with exactly this one addition.

CREATE OR REPLACE FUNCTION public.tg_inventory_txn_chain_qty_after()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'public', 'extensions', 'pg_temp'
AS $function$
DECLARE
  v_prev numeric;
BEGIN
  -- ★THE LEDGER'S ORDER IS THE ORDER THE SHELF WAS TOUCHED (HS W2, 2026-10-30). A defaulted created_at is now(), the
  -- moment the TRANSACTION began - but the writers (inventory_deduct / _restock / _adjust) take the part's row lock first
  -- and run in lock order, which a shift of thirty does not start in. A later writer then chained from a row that was not
  -- the latest and put a teammate's unit back: 29 members took one each, the ledger kept 29 rows, the shelf fell by 17.
  -- The moment the row is actually written, under the lock, is clock_timestamp(). A row that brings its own time (an
  -- offline replay) keeps it; the late-row branch below already handles those.
  IF NEW.created_at = now() THEN
    NEW.created_at := clock_timestamp();
  END IF;
  -- 'adjustment' rows carry an absolute physical count: qty_after IS the intent, qty_change is the
  -- derived delta. Only relative movements have a qty_after that can be recomputed from the chain.
  IF NEW.type NOT IN ('restock', 'use', 'add') OR NEW.qty_change IS NULL THEN
    RETURN NEW;
  END IF;

  -- BACKDATED INSERTS ARE HISTORY, NOT MOVEMENT. A seeder replaying a year of stock writes rows whose
  -- created_at is older than rows already present. Deriving those would chain a 2026-06 row off a 2026-08
  -- one and rewrite the past to match the future. If anything newer already exists for this item, leave
  -- the row exactly as the writer meant it — normalisation is for the LIVE tail only.
  IF EXISTS (SELECT 1 FROM public.inventory_transactions t
              WHERE t.item_id = NEW.item_id
                AND t.hive_id IS NOT DISTINCT FROM NEW.hive_id
                AND t.id <> NEW.id
                AND (t.created_at, t.id) > (COALESCE(NEW.created_at, now()), NEW.id)) THEN
    RETURN NEW;
  END IF;

  -- The predecessor is per ITEM and per HIVE: a shared item id must never chain across tenants.
  SELECT t.qty_after INTO v_prev
    FROM public.inventory_transactions t
   WHERE t.item_id = NEW.item_id
     AND t.hive_id IS NOT DISTINCT FROM NEW.hive_id
     AND t.id <> NEW.id
     -- ORDER BY THE SAME KEY THE GATE READS. validate_inventory_ledger_reconciled walks the chain with
     -- `lag(qty_after) OVER (PARTITION BY item_id ORDER BY created_at, id)`, so the predecessor is the row
     -- immediately before this one in (created_at, id). A bare `created_at <= NEW.created_at` is NOT that:
     -- a bulk insert inside ONE transaction fixes now(), so siblings TIE on created_at (the MR4 shape), and
     -- picking the greatest id among the ties can chain a row off a sibling the gate places AFTER it -
     -- which reads as a broken chain even though every number was computed. Compare the full key.
     AND (t.created_at, t.id) < (COALESCE(NEW.created_at, now()), NEW.id)
   ORDER BY t.created_at DESC, t.id DESC
   LIMIT 1;

  -- No predecessor: this is the item's opening row and qty_after defines the starting balance.
  IF v_prev IS NULL THEN
    RETURN NEW;
  END IF;

  NEW.qty_after := v_prev + NEW.qty_change;
  RETURN NEW;
END;
$function$;
