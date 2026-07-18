-- ============================================================================
-- ARC DI §10.5 ANTI-SEESAW — Inventory stock level: balance vs ledger (2026-07-08)
-- ============================================================================
-- ONE truth (an item's current stock) stored as TWO representations that can drift:
--   inventory_items.qty_on_hand         (the stored BALANCE)
--   inventory_transactions.qty_after    (the LEDGER's running total)
-- Deep-walk probe (2026-07-08) found 25/27 items where qty_on_hand != the ledger's
-- latest qty_after -- a classic "same truth, two copies" seesaw. Root cause was PURELY
-- the seeder (it wrote qty_on_hand as an OPENING balance then walked the ledger FORWARD
-- from it, so latest qty_after = opening + net_change != qty_on_hand; it also stamped
-- each txn with a RANDOM unsorted created_at, so "latest by created_at" didn't even
-- track the running total). The LIVE write paths are already consistent:
--   * inventory_deduct() RPC (20260624000001): UPDATE qty_on_hand=v_qty THEN INSERT
--     txn with qty_after=v_qty, atomically -> balance == qty_after by construction.
--   * inventory.html Use/Restock/Edit: decrements qty_on_hand client-side, then writes
--     a txn whose qty_after = that same new balance.
--
-- DISPOSITION (§10.5 tier-2: TRIGGER-RECONCILE + GATE). qty_on_hand must stay a STORED
-- column (parts can exist with zero transactions; the inventory list / low-stock tile /
-- analytics stockout all read it hot), so we cannot SSOT-derive it away. Instead a trigger
-- keeps the stored balance in LOCKSTEP with the ledger on every movement, and a gate
-- (validate_inventory_ledger_reconciled) asserts 0 drift + 0 broken ledger chains as a
-- down-ratchet. Divergence becomes impossible-then-detectable -> the field is FROZEN;
-- any future desync FAILs CI. Paired with the seeder fix (born-consistent ledger) this
-- kills the seesaw across sessions too (co-landing rule).
--
-- WHY qty_on_hand := NEW.qty_after (sync-to-ledger), NOT qty_on_hand += NEW.qty_change:
-- every existing producer ALSO writes qty_on_hand to that same new-balance value first,
-- so assigning qty_after is a no-op on those paths (NO double-count), while it BACKSTOPS
-- the one genuine corruption path -- a dropped item-UPDATE write (the documented
-- inventory.html:670 PostgREST-400 that once "logged the txn but never decremented
-- stock", and the logbook.html partial-write inventory_deduct() was built to prevent).
-- After this trigger, the ledger INSERT alone guarantees the balance follows.
--
-- The UPDATE touches only qty_on_hand + updated_at, so the BEFORE-UPDATE guards on
-- inventory_items pass through untouched: wh_guard_supervisor_approval trips only on
-- status/approved_*/wo_state transitions (privileged=false here); the text-cap and
-- inline-image-size guards inspect text/photo columns we never write. No recursion
-- (updates inventory_items, never inventory_transactions).
--
-- SECURITY DEFINER so the balance sync cannot be blocked by inventory_items UPDATE RLS
-- even when the client's own update was the thing that was dropped. search_path pinned
-- (CVE-2018-1058). Forward-only, idempotent (CREATE OR REPLACE + DROP TRIGGER IF EXISTS).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.inventory_sync_balance_from_ledger()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  -- Mirror the ledger's newest running total onto the stored balance. qty_after is the
  -- app/RPC-computed balance AFTER this movement, so this is idempotent w.r.t. producers
  -- that already set qty_on_hand (no double-count) and a backstop when they did not.
  UPDATE public.inventory_items
     SET qty_on_hand = NEW.qty_after,
         updated_at  = now()
   WHERE id = NEW.item_id
     AND qty_on_hand IS DISTINCT FROM NEW.qty_after;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_inventory_sync_balance ON public.inventory_transactions;
CREATE TRIGGER trg_inventory_sync_balance
  AFTER INSERT ON public.inventory_transactions
  FOR EACH ROW EXECUTE FUNCTION public.inventory_sync_balance_from_ledger();

-- ── One-time reconcile of any PRE-EXISTING drift ────────────────────────────
-- Set each item's stored balance to its ledger's newest running total (by created_at,
-- id as a stable tie-break). Items with zero transactions keep their opening qty_on_hand
-- (no ledger to reconcile against). Idempotent: re-running is a no-op once 0-drift.
WITH latest AS (
  SELECT DISTINCT ON (item_id) item_id, qty_after
  FROM public.inventory_transactions
  ORDER BY item_id, created_at DESC, id DESC
)
UPDATE public.inventory_items i
   SET qty_on_hand = latest.qty_after,
       updated_at  = now()
  FROM latest
 WHERE latest.item_id = i.id
   AND i.qty_on_hand IS DISTINCT FROM latest.qty_after;
