-- A deal cannot be re-filed: an order's price and parties, and any inquiry's or order's listing and hive, are fixed once
-- written (2026-10-27).
--
-- Found by the psql probe marketplace*__write_authz_depth once its fixture chose a row the member is a party to: the
-- buyer moved their own inquiry and their own order into another hive, and the database accepted both.
--
-- 1. ORDERS - the guard was there and did not fire. guard_marketplace_order_status refuses a change to buyer, seller,
--    price, currency or hive ("an order's parties and price are immutable", 20260730000006), but its trigger was
--    BEFORE INSERT OR UPDATE OF status - so an UPDATE that sets price or hive_id and leaves status alone never runs it.
--    authenticated holds UPDATE on price, hive_id, listing_id and the names, and the party policy admits the buyer: a
--    buyer could rewrite what they pay. The trigger now fires on every UPDATE; the function is unchanged (it raises only
--    when one of those fields actually changes, or a client sets released/refunded).
-- 2. INQUIRIES AND ORDERS - the listing and the hive. An inquiry or order lives in its LISTING's hive and is about that
--    listing. Nothing fixed either: a party could point their row at another listing or file it under another hive,
--    where it counts toward that hive's seller figures. On a client's INSERT the hive is now taken from the listing (the
--    binder decides, as everywhere else); on a client's UPDATE the listing and the hive cannot change. Service-role
--    and direct sessions (seeders, the escrow functions) state their own fields, as before; a marketplace admin who is
--    not a party may still correct them; the announced system-write setting is honoured for orders.

BEGIN;

DROP TRIGGER IF EXISTS trg_guard_marketplace_order_status ON public.marketplace_orders;
CREATE TRIGGER trg_guard_marketplace_order_status
  BEFORE INSERT OR UPDATE ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.guard_marketplace_order_status();

CREATE OR REPLACE FUNCTION public.guard_deal_listing_and_hive()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;                       -- service role / direct session: states its own
  IF TG_OP = 'INSERT' THEN
    NEW.hive_id := (SELECT l.hive_id FROM public.marketplace_listings l WHERE l.id = NEW.listing_id);
    RETURN NEW;
  END IF;
  IF NEW.listing_id IS DISTINCT FROM OLD.listing_id OR NEW.hive_id IS DISTINCT FROM OLD.hive_id THEN
    IF public.is_marketplace_admin() THEN RETURN NEW; END IF;
    IF TG_TABLE_NAME = 'marketplace_orders'
       AND coalesce(current_setting('workhive.order_system_write', true), '') = 'on' THEN RETURN NEW; END IF;
    RAISE EXCEPTION 'Not allowed: a deal stays on its listing and in its listing''s hive'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION public.guard_deal_listing_and_hive() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_guard_inquiry_listing_and_hive ON public.marketplace_inquiries;
CREATE TRIGGER trg_guard_inquiry_listing_and_hive
  BEFORE INSERT OR UPDATE ON public.marketplace_inquiries
  FOR EACH ROW EXECUTE FUNCTION public.guard_deal_listing_and_hive();

DROP TRIGGER IF EXISTS trg_guard_order_listing_and_hive ON public.marketplace_orders;
CREATE TRIGGER trg_guard_order_listing_and_hive
  BEFORE INSERT OR UPDATE ON public.marketplace_orders
  FOR EACH ROW EXECUTE FUNCTION public.guard_deal_listing_and_hive();

COMMIT;
