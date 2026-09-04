-- Inventory ledger: derive qty_after for RELATIVE movements instead of trusting the client.
--
-- WHY (2026-08-28). trg_inventory_sync_balance mirrors NEW.qty_after onto inventory_items.qty_on_hand.
-- That guarantees the two copies AGREE; it never checks the number is RIGHT. A producer that computes
-- a wrong running total therefore corrupts the stored balance silently and *consistently* -- which is
-- worse than a disagreement, because the disagreement is the only signal anyone can see.
--
-- It happened. One row (restock +4 recorded qty_after 6 on a shelf holding 6) came from inventory.html's
-- fallback lane, chosen by `if (HIVE_ID && navigator.onLine)`. navigator.onLine false-negatives are
-- routine (headless contexts, flaky mobile radios), and when it lies the page takes the client
-- read-modify-write branch while the INSERT still succeeds -- bypassing inventory_restock's atomic
-- FOR UPDATE compute and writing a stale-cache total that this trigger then canonised as the balance.
-- Net effect: 4 restocked units invisible. The shelf had 10, the system said 6.
--
-- The fix normalises rather than rejects. A CHECK or a RAISE would refuse writes from any client still
-- running the old JS during a deploy window (the schedule_items lesson from 2026-08-28: a CHECK rejects
-- an old client's payload, a BEFORE trigger repairs it). For a RELATIVE movement the intent is
-- qty_change, so qty_after is derivable and any client value is redundant. For 'adjustment' the intent
-- is the absolute count from a physical stock-take, so qty_after stays authoritative and is left alone.

-- WHAT THIS DELIBERATELY DOES NOT FIX, measured 2026-08-28. Normalisation covers the LIVE TAIL: a row
-- that is the newest for its item. If a bulk insert writes several rows inside ONE transaction, now() is
-- fixed so they all TIE on created_at (the MR4 shape), and if their ids do not ascend in insert order then
-- a later row can sort BEFORE an earlier one. The earlier-inserted row is then no longer the tail, the
-- backdate guard below refuses to touch it, and whatever the producer supplied survives. That is the
-- correct trade: a BEFORE trigger cannot see rows that do not exist yet, and rewriting a row the gate
-- sorts as history is exactly what the guard exists to prevent. It is also strictly better than before -
-- proven: with two tied rows the tail one is corrected (999 -> 12) while previously BOTH kept 999.
-- A bulk producer must supply a correct running total; every real producer here writes ONE row per call.

CREATE OR REPLACE FUNCTION public.tg_inventory_txn_chain_qty_after()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_prev numeric;
BEGIN
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
$$;

DROP TRIGGER IF EXISTS trg_inventory_txn_chain_qty_after ON public.inventory_transactions;
CREATE TRIGGER trg_inventory_txn_chain_qty_after
  BEFORE INSERT ON public.inventory_transactions
  FOR EACH ROW EXECUTE FUNCTION public.tg_inventory_txn_chain_qty_after();
