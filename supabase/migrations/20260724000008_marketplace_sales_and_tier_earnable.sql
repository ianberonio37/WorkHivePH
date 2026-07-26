-- ============================================================================
-- Marketplace SALES COUNTER + TIER LADDER — give them a producer that can actually fire, and make the
-- tier obey the platform's own thresholds
-- (Marketplace Deepwalk EXPANSION arc, J16/MK1, 2026-07-24)
-- ----------------------------------------------------------------------------
-- THREE MEASURED DEFECTS (walked live, then confirmed in SQL):
--
--  1. total_sales is a BUYER-FACING TRUST CLAIM with nothing behind it. It renders as "16 sales" in
--     the listing detail sheet (marketplace.html) and in the community seller meta (community.html),
--     yet the sellers table claimed 65 sales in total while marketplace_orders held 0 rows. Same
--     class as the unbacked rating fixed in 20260724000007: a number a buyer reads as evidence.
--
--  2. THE LADDER IS DEAD. The only producer of total_sales/tier is update_seller_tier(), a trigger on
--     marketplace_orders firing when status becomes 'released'. Stripe was removed entirely on
--     2026-06-30 and that table was deliberately left vestigial ("de-Stripe is not a redesign of the
--     order model"), so it will never receive a row. No seller can ever advance a tier. That is the
--     "make it EARNABLE, not coming soon" failure: a visible progress ladder with no reachable rung.
--
--  3. THE SEEDED TIERS VIOLATE THE PLATFORM'S OWN RULE. update_seller_tier documents gold at >= 51
--     and silver at >= 11, but the data had gold at 16 sales, silver at 8, and even silver at 0. The
--     badge contradicted the only definition of it that exists in the code.
--
-- THE FIX: in a contact-only marketplace with no payments, the one observable sale event is a seller
--   marking a listing SOLD. So total_sales is RECOMPUTED from marketplace_listings.status = 'sold',
--   and tier is derived from it with the thresholds already documented above (51 / 11). Recompute
--   rather than increment: it is idempotent, it handles a sold listing being reopened or deleted, and
--   it can never drift the way a counter does.
--
-- WHAT THIS DELIBERATELY DOES NOT DO: it does not invent a new meaning for the tier thresholds, and
--   it does not resurrect any payment concept. The vestigial marketplace_orders trigger is left in
--   place, harmless, so nothing is broken if that table is ever revived.
--
-- RESIDUAL, STATED HONESTLY: a seller can still inflate the counter by posting listings and marking
--   them sold. That is inherent to a marketplace with no payment rail to corroborate a sale, and it
--   is bounded (it costs real listings, which are visible and moderated). The stronger signal buyers
--   have is the verified-purchase rating, which cannot be self-assigned at all. total_sales remains
--   system-only via guard_marketplace_seller_trust_columns, so it cannot be written by hand.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.recompute_seller_sales_and_tier(p_seller_name text)
 RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
DECLARE
  v_sold integer;
BEGIN
  IF p_seller_name IS NULL OR btrim(p_seller_name) = '' THEN RETURN; END IF;

  SELECT COUNT(*)::integer INTO v_sold
    FROM public.marketplace_listings
   WHERE seller_name = p_seller_name AND status = 'sold';

  PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce to the trust guard

  UPDATE public.marketplace_sellers
     SET total_sales = v_sold,
         tier = CASE WHEN v_sold >= 51 THEN 'gold'
                     WHEN v_sold >= 11 THEN 'silver'
                     ELSE 'bronze' END,
         updated_at = now()
   WHERE worker_name = p_seller_name
     AND (total_sales IS DISTINCT FROM v_sold
          OR tier IS DISTINCT FROM CASE WHEN v_sold >= 51 THEN 'gold'
                                        WHEN v_sold >= 11 THEN 'silver'
                                        ELSE 'bronze' END);
END;
$function$;

COMMENT ON FUNCTION public.recompute_seller_sales_and_tier(text) IS
  'Recomputes marketplace_sellers.total_sales from listings marked sold and derives tier with the documented 51/gold, 11/silver thresholds. Idempotent by design so a reopened or deleted listing self-corrects. MK1 trust-signal integrity; replaces a producer that could never fire (orders are vestigial since Stripe removal).';


CREATE OR REPLACE FUNCTION public.trg_listing_sold_recompute()
 RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
BEGIN
  -- Recompute for whichever seller(s) this row touched. On an UPDATE that reassigns seller_name
  -- (possible via moderation), BOTH sides need recomputing or the old one keeps a stale count.
  IF TG_OP = 'DELETE' THEN
    PERFORM public.recompute_seller_sales_and_tier(OLD.seller_name);
    RETURN OLD;
  END IF;
  PERFORM public.recompute_seller_sales_and_tier(NEW.seller_name);
  IF TG_OP = 'UPDATE' AND OLD.seller_name IS DISTINCT FROM NEW.seller_name THEN
    PERFORM public.recompute_seller_sales_and_tier(OLD.seller_name);
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_listing_sold_recompute ON public.marketplace_listings;
CREATE TRIGGER trg_listing_sold_recompute
  AFTER INSERT OR DELETE OR UPDATE OF status, seller_name ON public.marketplace_listings
  FOR EACH ROW EXECUTE FUNCTION public.trg_listing_sold_recompute();


-- One-time backfill: every seller recomputed from the real sold-listing record.
DO $backfill$
DECLARE
  r record;
  v_before bigint;
  v_after  bigint;
BEGIN
  SELECT COALESCE(SUM(total_sales), 0) INTO v_before FROM public.marketplace_sellers;
  FOR r IN SELECT worker_name FROM public.marketplace_sellers LOOP
    PERFORM public.recompute_seller_sales_and_tier(r.worker_name);
  END LOOP;
  SELECT COALESCE(SUM(total_sales), 0) INTO v_after FROM public.marketplace_sellers;
  RAISE NOTICE 'marketplace sales backfill: claimed total %, real sold-listing total %', v_before, v_after;
END
$backfill$;

COMMENT ON COLUMN public.marketplace_sellers.total_sales IS
  'Count of this seller''s listings marked sold, maintained by trg_listing_sold_recompute and backfilled 2026-07-24 (previously seeded with no backing: 65 claimed against 0 orders). Drives tier via the 51/gold, 11/silver thresholds. Never self-assignable (guard_marketplace_seller_trust_columns).';
