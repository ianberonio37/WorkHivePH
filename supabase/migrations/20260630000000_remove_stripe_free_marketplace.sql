-- ============================================================================
-- Remove Stripe entirely — the marketplace is FREE (Ian, 2026-06-30).
--
-- The marketplace was already running PAYMENTS_ENABLED=false (Arc K, 2026-06-22):
-- the live flow is contact-only (browse -> post listing -> watchlist -> Contact-
-- Seller inquiry -> seller reply via phone/email/messenger). The Stripe payment
-- machinery (5 edge fns, Connect onboarding, escrow, webhooks) was dead code.
--
-- This migration removes the Stripe *coupling* from the data layer:
--   · drop the stripe_* columns from marketplace_orders (+ their unique/btree idx)
--   · drop stripe_account_id from marketplace_sellers (Stripe Connect payout acct)
--   · recreate the two truth views without any stripe_* column
--
-- Surgical + on-scope: this de-Stripes; it does NOT redesign the order model.
-- marketplace_orders is empty (0 rows) and its UI is already hidden under the
-- free flow, so the vestigial table/status enum is left untouched. The free flow
-- uses marketplace_inquiries, not orders.
-- ============================================================================

-- The two truth views select the stripe_* columns, so drop them before the ALTERs.
DROP VIEW IF EXISTS public.v_marketplace_orders_truth;
DROP VIEW IF EXISTS public.v_marketplace_sellers_truth;

-- ── marketplace_orders: drop Stripe columns + their index/constraint ──────────
ALTER TABLE public.marketplace_orders
  DROP CONSTRAINT IF EXISTS marketplace_orders_stripe_session_id_key;
DROP INDEX IF EXISTS public.idx_mkt_orders_stripe_session;
ALTER TABLE public.marketplace_orders
  DROP COLUMN IF EXISTS stripe_session_id,
  DROP COLUMN IF EXISTS stripe_payment_id,
  DROP COLUMN IF EXISTS stripe_transfer_id;

-- ── marketplace_sellers: drop the Stripe Connect payout account id ────────────
ALTER TABLE public.marketplace_sellers
  DROP COLUMN IF EXISTS stripe_account_id;

-- ── recreate v_marketplace_orders_truth WITHOUT the stripe_* columns ──────────
-- (identical to the prior definition minus the three stripe_* passthrough cols)
-- security_invoker: the view reads RLS tables (marketplace_orders/listings) and is granted to
-- anon+authenticated, so it MUST respect base-table RLS or it leaks every hive's orders (Arc G).
CREATE VIEW public.v_marketplace_orders_truth
  WITH (security_invoker = on) AS
SELECT o.id,
    o.listing_id,
    o.hive_id,
    o.buyer_name,
    o.seller_name,
    o.price,
    o.currency,
    o.status,
    o.escrow_release_at,
    o.buyer_confirmed_at,
    o.released_at,
    o.reviewed_at,
    o.created_at,
    o.updated_at,
    l.title AS listing_title,
    l.section AS listing_section,
    l.image_url AS listing_image_url,
    o.status = 'pending_payment'::text AS is_pending_payment,
    o.status = 'escrow_hold'::text AS is_escrow,
    o.status = 'buyer_confirmed'::text AS is_buyer_confirmed,
    o.status = 'released'::text AS is_released,
    o.status = 'refunded'::text AS is_refunded,
    o.status = 'disputed'::text AS is_disputed,
    o.reviewed_at IS NOT NULL AS is_reviewed,
        CASE
            WHEN o.escrow_release_at IS NOT NULL THEN GREATEST(0::numeric, EXTRACT(epoch FROM o.escrow_release_at - now()) / 86400.0)::integer
            ELSE NULL::integer
        END AS days_until_escrow_release
   FROM marketplace_orders o
     LEFT JOIN marketplace_listings l ON l.id = o.listing_id;

GRANT SELECT ON public.v_marketplace_orders_truth TO anon, authenticated;

-- ── recreate v_marketplace_sellers_truth WITHOUT stripe_account_id ────────────
-- security_invoker: same reason as the orders view above — reads RLS tables + granted to
-- anon+authenticated, so it must respect base-table RLS (Arc G view-security gate).
CREATE VIEW public.v_marketplace_sellers_truth
  WITH (security_invoker = on) AS
SELECT s.id,
    s.worker_name,
    s.auth_uid,
    s.hive_id,
    s.tier,
    s.kyb_verified,
    s.kyb_verified_at,
    s.cert_verified,
    s.cert_verified_at,
    s.total_sales,
    s.rating_avg,
    s.rating_count,
    s.response_rate,
    s.response_time_h,
    s.messenger_username,
    s.certifications,
    s.created_at,
    s.updated_at,
    COALESCE(active_listings.n, 0::bigint) AS active_listings_count,
    COALESCE(total_orders.n, 0::bigint) AS total_orders_count,
    active_listings.last_at AS last_listed_at,
    total_orders.last_at AS last_order_at,
    s.kyb_verified AND s.cert_verified AS is_verified_public,
    s.messenger_username IS NOT NULL AND s.certifications IS NOT NULL AS profile_complete
   FROM marketplace_sellers s
     LEFT JOIN LATERAL ( SELECT count(*) AS n,
            max(l.created_at) AS last_at
           FROM marketplace_listings l
          WHERE l.seller_name = s.worker_name AND l.status = 'published'::text) active_listings ON true
     LEFT JOIN LATERAL ( SELECT count(*) AS n,
            max(o.created_at) AS last_at
           FROM marketplace_orders o
          WHERE o.seller_name = s.worker_name) total_orders ON true;

GRANT SELECT ON public.v_marketplace_sellers_truth TO anon, authenticated;
