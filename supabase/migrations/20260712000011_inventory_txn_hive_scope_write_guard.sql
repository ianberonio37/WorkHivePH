-- =============================================================================
-- Inventory PDDA Arc — X/I keystone: close the cross-hive ledger-tamper hole.
--
-- LIVE-CONFIRMED EXPLOIT (2026-07-12, deep-walk as pabloaguilar / hive c9def338…):
--   `inventory_transactions_write` WITH CHECK was only `auth.uid() IS NOT NULL`
--   — no hive scoping and no check that the referenced item belongs to the
--   caller's hive. A worker inserted a ledger row against a FOREIGN hive's item
--   (inv-080ba8064626, hive 46750939…) with qty_after=88888; the SECURITY DEFINER
--   AFTER-INSERT trigger `inventory_sync_balance_from_ledger()` then blindly
--   mirrored 88888 onto that foreign item's stored qty_on_hand (78 → 88888).
--   = cross-tenant stock corruption + ledger poisoning (BOLA class), the write-path
--     twin of the realtime cross-tenant leak + the supervisor-approval backstop.
--
-- FIX (belt-and-suspenders, mirrors 20260707000000 approval backstop + Marketplace
--      seller-trust guard — see security & multitenant-engineer skills):
--   1. WITH CHECK: the referenced inventory_item must live in a hive the caller is
--      an ACTIVE member of (membership-join, not a raw hive_id check), AND the txn's
--      hive_id must equal the item's hive_id (blocks a valid-own-hive_id + foreign
--      item_id spoof). Solo path: item.hive_id IS NULL AND item.auth_uid = caller.
--   2. USING (UPDATE/DELETE): same hive-membership scope — drop the blanket
--      `auth_uid IS NULL` branch that let any authed user tamper/delete another
--      hive's (seeded, null-attributed) ledger rows.
--   3. Trigger hive-guard: the DEFINER sync trigger only mirrors onto an item in
--      the SAME hive as the txn — defense in depth even if a row ever slips past RLS.
--   4. Non-negative ledger CHECK: qty_after (a running BALANCE) can never be < 0,
--      closing arbitrary in-hive negative-stock tamper via a direct txn insert.
--
-- Service-role/seeder/edge-fn writers (auth.uid() IS NULL) BYPASSRLS, so the RLS
-- clauses do not affect them; they still satisfy the CHECK (qty_after is a balance ≥ 0)
-- and the trigger hive-guard (0 hive-mismatch rows exist). Verified pre-fix:
-- 0 neg qty_after · 0 null-hive · 0 orphan · 0 hive-mismatch txns → no legit row breaks.
-- =============================================================================

-- 1 + 2 -----------------------------------------------------------------------
DROP POLICY IF EXISTS "inventory_transactions_write" ON public.inventory_transactions;
CREATE POLICY "inventory_transactions_write" ON public.inventory_transactions
  AS PERMISSIVE FOR ALL TO public
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.inventory_items ii
      WHERE ii.id = inventory_transactions.item_id
        AND (
          (ii.hive_id IS NULL AND ii.auth_uid = auth.uid())
          OR ii.hive_id IN (
            SELECT hm.hive_id FROM public.hive_members hm
            WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
          )
        )
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND (auth_uid = auth.uid() OR auth_uid IS NULL)   -- attribution unchanged (DI ratchet owns strictness)
    AND EXISTS (
      SELECT 1 FROM public.inventory_items ii
      WHERE ii.id = inventory_transactions.item_id
        AND ii.hive_id IS NOT DISTINCT FROM inventory_transactions.hive_id  -- txn hive must match item hive
        AND (
          (ii.hive_id IS NULL AND ii.auth_uid = auth.uid())
          OR ii.hive_id IN (
            SELECT hm.hive_id FROM public.hive_members hm
            WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
          )
        )
    )
  );

-- 3 ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.inventory_sync_balance_from_ledger()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
  -- Mirror the ledger's newest running total onto the stored balance. Idempotent
  -- w.r.t. producers that already set qty_on_hand; a backstop when they did not.
  -- Hive-guard (Inventory PDDA): NEVER mirror across hives, even for a row that
  -- somehow bypassed RLS — the balance may only move for an item in the txn's hive.
  UPDATE public.inventory_items
     SET qty_on_hand = NEW.qty_after,
         updated_at  = now()
   WHERE id = NEW.item_id
     AND hive_id IS NOT DISTINCT FROM NEW.hive_id
     AND qty_on_hand IS DISTINCT FROM NEW.qty_after;
  RETURN NEW;
END;
$function$;

-- 4 ---------------------------------------------------------------------------
ALTER TABLE public.inventory_transactions
  DROP CONSTRAINT IF EXISTS inventory_transactions_qty_after_nonneg;
ALTER TABLE public.inventory_transactions
  ADD CONSTRAINT inventory_transactions_qty_after_nonneg CHECK (qty_after >= 0);
