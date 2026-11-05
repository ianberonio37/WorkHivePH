-- ★A PARTY TO A DISPUTE COULD WRITE THE ADMIN'S DECISION (2026-11-05, found reading J27's premise for GJ M9).
--
-- marketplace_disputes' UPDATE policy (mkt_disp_update) lets the buyer who opened a dispute, the listing's seller and the
-- order's parties update the row - with no guard on WHICH columns. So a seller could PATCH their own dispute to
-- status = 'resolved_release', admin_decision = 'Funds released to seller by admin', resolved_at = now(): a decision
-- the admin never made, in the record both parties and the admin read. The policy is right about WHO may touch a
-- dispute (each party has something to say on it); it was silent about WHAT each may say.
--
-- Each column now has one owner, enforced by a BEFORE UPDATE trigger (the service role keeps every column; an admin
-- keeps every column on a dispute they are not a party to):
--   status, admin_decision, admin_decided_at, resolved_at   the marketplace admin - except that the seller's reply moves
--                                                          an 'open' dispute to 'seller_responded'
--   seller_reply (seller_replied_at stamped here)          the listing's seller
--   reason, description, evidence_urls                     the person who opened it, while it is still 'open'
--   order_id, listing_id, seller_name, opened_by           nobody: what a dispute is about never changes
-- A refused change raises 42501 with the sentence the person reads.

CREATE OR REPLACE FUNCTION public.guard_marketplace_dispute_columns()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $$
DECLARE
  v_seller boolean;
  v_party  boolean;
BEGIN
  -- the service role and seeders (no JWT) are vetted backend writes
  IF auth.uid() IS NULL THEN
    RETURN NEW;
  END IF;

  -- what a dispute is about never changes, for anyone - the admin included (the same rule as the order's parties)
  IF NEW.order_id IS DISTINCT FROM OLD.order_id OR NEW.listing_id IS DISTINCT FROM OLD.listing_id
     OR NEW.seller_name IS DISTINCT FROM OLD.seller_name OR NEW.opened_by IS DISTINCT FROM OLD.opened_by THEN
    RAISE EXCEPTION 'A dispute''s order, listing and parties cannot be changed.' USING ERRCODE = '42501';
  END IF;

  v_seller := public.listing_is_mine(OLD.listing_id);
  v_party  := v_seller OR OLD.opened_by_auth_uid = auth.uid() OR (OLD.order_id IS NOT NULL AND public.order_is_mine(OLD.order_id));
  -- an admin decides a dispute they are NOT a party to; on their own they are a buyer or a seller like anyone else
  -- (the order guard's rule, trg_guard_marketplace_order_status)
  IF public.is_marketplace_admin() AND NOT v_party THEN
    RETURN NEW;
  END IF;

  IF NEW.admin_decision IS DISTINCT FROM OLD.admin_decision OR NEW.admin_decided_at IS DISTINCT FROM OLD.admin_decided_at
     OR NEW.resolved_at IS DISTINCT FROM OLD.resolved_at
     OR (NEW.status IS DISTINCT FROM OLD.status
         AND NOT (v_seller AND OLD.status = 'open' AND NEW.status = 'seller_responded'
                  AND NEW.seller_reply IS DISTINCT FROM OLD.seller_reply)) THEN
    RAISE EXCEPTION 'Only a marketplace admin can decide a dispute.' USING ERRCODE = '42501';
  END IF;

  IF NEW.seller_reply IS DISTINCT FROM OLD.seller_reply THEN
    IF NOT v_seller THEN
      RAISE EXCEPTION 'Only the seller can reply to this dispute.' USING ERRCODE = '42501';
    END IF;
    NEW.seller_replied_at := now();
  ELSE
    NEW.seller_replied_at := OLD.seller_replied_at;
  END IF;

  IF (NEW.reason IS DISTINCT FROM OLD.reason OR NEW.description IS DISTINCT FROM OLD.description
      OR NEW.evidence_urls IS DISTINCT FROM OLD.evidence_urls)
     AND NOT (OLD.opened_by_auth_uid = auth.uid() AND OLD.status = 'open') THEN
    RAISE EXCEPTION 'Only the person who opened this dispute can change what it says happened, and only while it is open.' USING ERRCODE = '42501';
  END IF;

  RETURN NEW;
END $$;

-- a trigger's function: nobody calls it; anon is named because Supabase grants it explicitly (definer-doors Y2)
REVOKE ALL ON FUNCTION public.guard_marketplace_dispute_columns() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_guard_marketplace_dispute_columns ON public.marketplace_disputes;
CREATE TRIGGER trg_guard_marketplace_dispute_columns
  BEFORE UPDATE ON public.marketplace_disputes
  FOR EACH ROW EXECUTE FUNCTION public.guard_marketplace_dispute_columns();
