-- ============================================================================
-- Marketplace REVIEWS — give the rating ladder its missing first rung, without opening a forge
-- (Marketplace Deepwalk EXPANSION arc, MK13, 2026-07-24. Ian chose "build the review flow".)
-- ----------------------------------------------------------------------------
-- WHAT THE DEEPWALK FOUND: marketplace_reviews was SELECT-only in the entire app. No page could write
--   one, so no buyer could review and, because the verified-only rating is COMPUTED from reviews, no
--   seller could ever earn a rating in-product. The MK1 work made the rating honest; the ladder behind
--   it simply had no bottom step. Seeded profiles had reviews only because the seeder uses service-role.
--
-- THE EXISTING POLICY WAS ALREADY HALF-RIGHT: mkt_reviews_insert lets a signed-in worker insert a review
--   AS THEMSELVES with verified_purchase = false, and reserves verified_purchase = true to admins. That
--   is the anti-forge half and it stays exactly as it is.
--
-- WHAT THIS ADDS — the two things that stop an open form from becoming a reputation weapon:
--   1. YOU MUST HAVE CONTACTED THE SELLER. A review requires an existing inquiry from you on that
--      listing. On a contact-only marketplace the inquiry is the only on-platform trace that a real
--      interaction happened, so it is the honest proxy for standing to review. Without it, anyone could
--      review any listing they had never touched.
--   2. YOU CANNOT REVIEW YOUR OWN LISTING. Self-review is the most obvious forge and costs nothing to
--      close here.
--
-- Deliberately NOT added: a one-review-per-listing UNIQUE constraint. A buyer who genuinely deals with
--   the same seller twice may review twice, and the UI dedupes the common accidental case. Adding a
--   hard constraint later is easy; removing one that blocks a legitimate second review is not.
--
-- The rating itself remains verified-only, so an unverified review is SHOWN but does not move the
-- score (20260719000003). That is the point: the flow is open, the score is still earned.
-- ============================================================================

DROP POLICY IF EXISTS mkt_reviews_insert ON public.marketplace_reviews;

CREATE POLICY mkt_reviews_insert ON public.marketplace_reviews
  FOR INSERT TO authenticated
  WITH CHECK (
    public.is_marketplace_admin()
    OR (
      reviewer_name IN (SELECT auth_worker_names())
      AND verified_purchase = false
      -- standing: an inquiry of mine exists on this listing
      AND EXISTS (
        SELECT 1 FROM public.marketplace_inquiries i
         WHERE i.listing_id = marketplace_reviews.listing_id
           AND i.buyer_name IN (SELECT auth_worker_names())
      )
      -- and the listing is not my own
      AND NOT EXISTS (
        SELECT 1 FROM public.marketplace_listings l
         WHERE l.id = marketplace_reviews.listing_id
           AND l.seller_name IN (SELECT auth_worker_names())
      )
    )
  );

COMMENT ON TABLE public.marketplace_reviews IS
  'Buyer reviews. INSERT requires the reviewer to be the signed-in worker, to have an existing inquiry on that listing (the only on-platform trace of a real interaction in a contact-only marketplace), and not to own the listing. verified_purchase stays admin/system-set, and the seller rating is computed over verified reviews ONLY (20260719000003), so an open review form never inflates a score.';
