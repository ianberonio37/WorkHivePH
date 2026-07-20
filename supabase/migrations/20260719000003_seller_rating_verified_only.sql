-- Fix (marketplace trust-integrity sibling of 20260719000002, found live 2026-07-19 P5/P6):
-- FAKE-REVIEW rating inflation/deflation. `update_seller_rating` (AFTER INSERT on marketplace_reviews)
-- recomputed `marketplace_sellers.rating_avg`/`rating_count` as AVG/COUNT over ALL reviews for the
-- seller's listings — with NO `verified_purchase` filter. But `mkt_reviews_insert` RLS lets ANY authed
-- worker insert a review (`reviewer_name = self`) for ANY `listing_id` (no check they bought it), as
-- long as `verified_purchase = false`. So a worker could self-insert 5-star reviews for a target seller
-- to INFLATE their rating (self-dealing for fake reputation), or — since `marketplace_reviews` is empty
-- today while 14 sellers carry seeded ratings on marketplace_sellers — a single unverified review would
-- OVERWRITE a seeded rating (a one-review recompute = deflation griefing too). The whole marketplace
-- runs on the seller trust signal (rating shown in search / community / seller profile / schema.org
-- AggregateRating), so a forgeable aggregate is a real integrity hole.
--
-- FIX: only VERIFIED-PURCHASE reviews move the stored trust rating.
--   (1) an unverified review (the only kind a client can insert) returns early → the stored rating is
--       untouched (closes BOTH inflation and deflation), and
--   (2) the recompute averages `verified_purchase = true` reviews only.
-- A verified review can be created only by an admin / the escrow backend (RLS: non-admin is forced to
-- verified_purchase=false; mkt_reviews_update WITH CHECK blocks a client flipping it true), so a real
-- released order is the only thing that can lift a seller's rating — which is exactly the trust contract.
-- Body preserved verbatim except the two guarded lines. The seller_system_write GUC announcement (which
-- exempts guard_marketplace_seller_trust_columns) is kept.

CREATE OR REPLACE FUNCTION public.update_seller_rating()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_seller_name text;
  v_new_avg     numeric(3,2);
  v_new_count   integer;
BEGIN
  SELECT seller_name INTO v_seller_name FROM public.marketplace_listings WHERE id = NEW.listing_id;
  IF v_seller_name IS NULL THEN RETURN NEW; END IF;
  -- Only a VERIFIED purchase moves the trust rating. A client can only insert verified_purchase=false
  -- reviews (RLS), so this makes client-inserted reviews unable to inflate OR deflate the stored rating.
  IF COALESCE(NEW.verified_purchase, false) = false THEN RETURN NEW; END IF;
  SELECT ROUND(AVG(r.rating::numeric), 2), COUNT(*)::integer
    INTO v_new_avg, v_new_count
    FROM public.marketplace_reviews r
    JOIN public.marketplace_listings l ON r.listing_id = l.id
   WHERE l.seller_name = v_seller_name
     AND r.verified_purchase = true;
  PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce system recompute to the guard
  INSERT INTO public.marketplace_sellers (worker_name, rating_avg, rating_count, updated_at)
  VALUES (v_seller_name, v_new_avg, v_new_count, now())
  ON CONFLICT (worker_name) DO UPDATE SET
    rating_avg = v_new_avg, rating_count = v_new_count, updated_at = now();
  RETURN NEW;
END;
$function$;
