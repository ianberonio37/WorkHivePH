-- ─── v_marketplace_orders_truth: expose reviewed_at ─────────────────────────
-- DRIFT fix (2026-06-10 deep-walk triage). marketplace.html reads
-- `reviewed_at` from this view (to gate "Leave a Review" and show "Review
-- submitted Xh ago"), and the write path already UPDATEs marketplace_orders
-- .reviewed_at. The base column exists; the canonical view simply never
-- exposed it -> PostgREST 400 -> the whole order list silently emptied for
-- buyers. Re-create the view identical to 20260520000023 + o.reviewed_at.

DROP VIEW IF EXISTS public.v_marketplace_orders_truth;

CREATE VIEW public.v_marketplace_orders_truth AS
SELECT
  o.id,
  o.listing_id,
  o.hive_id,
  o.buyer_name,
  o.seller_name,
  o.price,
  o.currency,
  o.stripe_session_id,
  o.stripe_payment_id,
  o.stripe_transfer_id,
  o.status,
  o.escrow_release_at,
  o.buyer_confirmed_at,
  o.released_at,
  o.reviewed_at,
  o.created_at,
  o.updated_at,
  -- Bridge to marketplace_listings
  l.title    AS listing_title,
  l.section  AS listing_section,
  l.image_url AS listing_image_url,
  -- Derived status flags
  (o.status = 'pending_payment') AS is_pending_payment,
  (o.status = 'escrow_hold')     AS is_escrow,
  (o.status = 'buyer_confirmed') AS is_buyer_confirmed,
  (o.status = 'released')        AS is_released,
  (o.status = 'refunded')        AS is_refunded,
  (o.status = 'disputed')        AS is_disputed,
  -- Derived: has the buyer left a review yet?
  (o.reviewed_at IS NOT NULL)    AS is_reviewed,
  -- Derived: is the escrow window approaching release?
  CASE WHEN o.escrow_release_at IS NOT NULL
       THEN GREATEST(0, EXTRACT(EPOCH FROM (o.escrow_release_at - now()))/86400.0)::int
       ELSE NULL
  END AS days_until_escrow_release
FROM public.marketplace_orders o
LEFT JOIN public.marketplace_listings l ON l.id = o.listing_id;

GRANT SELECT ON public.v_marketplace_orders_truth TO anon, authenticated;

COMMENT ON VIEW public.v_marketplace_orders_truth IS
  'Canonical marketplace_orders reader. Listing bridge (title/section/image_url) + status flags (incl is_reviewed) + reviewed_at + days_until_escrow_release.';

UPDATE public.canonical_sources
   SET contract = jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('listing_title','listing_section','listing_image_url'),
     'derived_columns', jsonb_build_array('is_pending_payment','is_escrow','is_buyer_confirmed','is_released','is_refunded','is_disputed','is_reviewed','days_until_escrow_release')
   ),
   description = 'Canonical marketplace_orders reader. Per-order granularity with listing bridge, derived status flags (incl is_reviewed), reviewed_at, and days_until_escrow_release.'
 WHERE domain = 'marketplace_orders_truth';
