-- ============================================================================
-- Marketplace TRUST-SIGNAL BACKING — a displayed rating must be EARNED by real verified reviews
-- (Marketplace Deepwalk EXPANSION arc, J15/MK1, 2026-07-24)
-- ----------------------------------------------------------------------------
-- THE DEFECT (measured, not assumed): 13 of 13 sellers carried a rating_avg / rating_count with
--   ZERO verified reviews behind it. The recompute trigger (20260719000003, verified-only) is
--   CORRECT, but it only fires on INSERT into marketplace_reviews - so a value that was seeded or
--   imported without reviews is never revisited and stands forever. A buyer reads "3.9 stars" as
--   evidence; here it was a number with no evidence, which is the exact class MK1 exists to kill.
--   (Same orphan shape as MK9's response_rate: a trust column with no producer keeping it true.)
--
-- THE FIX: recompute every seller from the actual verified-review record, once. A seller with no
--   verified reviews ends at NULL/0, which the UI already renders honestly as "New seller, no
--   ratings yet" (shipped earlier in this arc) rather than inventing a score.
--
-- WHY IT STAYS FIXED: the trigger keeps it current from here, and rating_avg/rating_count remain
--   guarded against self-assignment by guard_marketplace_seller_trust_columns (20260712000001), so
--   a seller still cannot write these values by hand.
-- ============================================================================

DO $backfill$
DECLARE
  v_fixed integer := 0;
BEGIN
  PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce to the trust guard

  WITH verified AS (
    SELECT l.seller_name,
           ROUND(AVG(r.rating::numeric), 2) AS avg_rating,
           COUNT(*)::integer                AS n
      FROM public.marketplace_reviews r
      JOIN public.marketplace_listings l ON l.id = r.listing_id
     WHERE r.verified_purchase
     GROUP BY l.seller_name
  )
  UPDATE public.marketplace_sellers s
     SET rating_avg   = v.avg_rating,
         rating_count = v.n,
         updated_at   = now()
    FROM verified v
   WHERE s.worker_name = v.seller_name
     AND (s.rating_avg IS DISTINCT FROM v.avg_rating OR s.rating_count IS DISTINCT FROM v.n);

  -- Sellers with NO verified reviews must not keep an unearned score.
  UPDATE public.marketplace_sellers s
     SET rating_avg = NULL, rating_count = 0, updated_at = now()
   WHERE (s.rating_avg IS NOT NULL OR COALESCE(s.rating_count, 0) <> 0)
     AND NOT EXISTS (
       SELECT 1 FROM public.marketplace_reviews r
         JOIN public.marketplace_listings l ON l.id = r.listing_id
        WHERE l.seller_name = s.worker_name AND r.verified_purchase);

  GET DIAGNOSTICS v_fixed = ROW_COUNT;
  RAISE NOTICE 'marketplace rating backfill: % seller(s) reset to unrated (no verified reviews)', v_fixed;
END
$backfill$;

COMMENT ON COLUMN public.marketplace_sellers.rating_avg IS
  'Average of VERIFIED-purchase reviews only, maintained by update_seller_rating and backfilled 2026-07-24. NULL means genuinely unrated: the UI shows "New seller, no ratings yet" rather than inventing a score. Never self-assignable (guard_marketplace_seller_trust_columns). MK1 trust-signal integrity.';
