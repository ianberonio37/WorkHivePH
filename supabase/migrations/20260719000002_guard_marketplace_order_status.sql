-- Fix (marketplace trust-integrity, found live 2026-07-19 per-page bughunt P5/P6):
-- A FAKE-SALES / SELLER-REPUTATION-INFLATION vector. `trg_seller_tier` bumps
-- `marketplace_sellers.total_sales` (+1, and promotes bronze→silver@11→gold@51) whenever a
-- `marketplace_orders` row transitions `status → 'released'`. But the RLS lets a JWT buyer
-- INSERT an order (`buyer_name IN auth_worker_names()`) naming ANY `seller_name`, then UPDATE
-- its status — with NO state-machine guard — straight from 'pending_payment' to 'released'.
-- Live-proven (rolled back): worker Bryan self-inserted an order (buyer=Bryan, seller=Leandro),
-- UPDATE'd status='released' → Leandro's total_sales 0→1, WITHOUT payment, escrow, or consent.
-- Self-dealing via a 2nd identity inflates one's OWN seller tier = fake trust signal (the whole
-- marketplace runs on seller_verified / rating / sales). The escrow purchase flow isn't wired yet
-- (0 rows, no buyer UI/edge-fn), so this is latent — but exploitable TODAY via direct PostgREST.
--
-- The money-moving / trust-affecting terminal states ('released' = funds to seller = the sales bump,
-- and 'refunded') must be set ONLY by the escrow/payment BACKEND (service-role), a marketplace admin,
-- or a future RPC/edge-fn that ANNOUNCES itself with the `workhive.order_system_write` GUC (mirrors
-- the `workhive.seller_system_write` pattern used by the rating/tier recompute triggers). A raw JWT
-- client may only drive the INTAKE states. Also forbids a client INSERTing an order already past the
-- entry state (can't create a born-'released' order). Closes the total_sales inflation at its source:
-- the bump can now fire only from a backend-authorized release.

CREATE OR REPLACE FUNCTION public.guard_marketplace_order_status()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
  -- service-role / backend writes (no JWT: seeders, escrow edge fns) are already vetted — allow.
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  -- marketplace admins may drive any transition (dispute resolution, manual release/refund).
  IF public.is_marketplace_admin() THEN RETURN NEW; END IF;
  -- a future release/refund RPC or edge fn announces itself for the duration of its transaction.
  IF current_setting('workhive.order_system_write', true) = 'on' THEN RETURN NEW; END IF;

  -- ---- from here: a raw authenticated (buyer/seller) client ----
  -- A client may NOT create an order already in a privileged/terminal state.
  IF TG_OP = 'INSERT' AND NEW.status <> 'pending_payment' THEN
    RAISE EXCEPTION 'Not allowed: a new order must start as pending_payment (status % is set by the escrow system)', NEW.status
      USING ERRCODE = 'check_violation';
  END IF;

  -- The trust-bearing terminal states are backend-only. 'released' fires the total_sales / tier bump;
  -- 'refunded' reverses a payment — neither may be self-assigned by a buyer or seller.
  IF TG_OP = 'UPDATE' AND NEW.status IN ('released', 'refunded') AND NEW.status IS DISTINCT FROM OLD.status THEN
    RAISE EXCEPTION 'Not allowed: order status % is set by the WorkHive escrow system, not by a buyer or seller', NEW.status
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guard_marketplace_order_status ON public.marketplace_orders;
CREATE TRIGGER trg_guard_marketplace_order_status
  BEFORE INSERT OR UPDATE OF status ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.guard_marketplace_order_status();
