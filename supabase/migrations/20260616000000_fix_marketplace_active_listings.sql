-- Fix the marketplace seller "active listings" DEAD NERVE (discovered by the
-- §13 E2E data-lineage sweep, 2026-06-16).
--
-- BUG: v_marketplace_sellers_truth.active_listings_count counted
--   marketplace_listings WHERE status = 'active'
-- but 'active' is NOT in the marketplace_listings.status CHECK enum
--   {draft, published, sold, removed}
-- and the app's own read paths (marketplace.html, 3 places) show live listings
-- with status = 'published'. The listing lifecycle is draft -> published ->
-- sold. So 'active' is never written -> active_listings_count (and
-- last_listed_at) were PERMANENTLY 0 for every seller, regardless of how many
-- live listings they had. A terminus that can never reflect its input.
--
-- FIX: count status = 'published' (the live "visible/active" state, matching
-- the app + the CHECK enum). This is a forward migration (immutability: the
-- original 20260510000005 migration is never edited). CREATE OR REPLACE keeps
-- the column list/order identical.
--
-- Crystallized by tools/validate_lineage_status_drift.py (the status-enum-drift
-- class validator); once this lands, remove the marketplace allowlist entry
-- there so the check becomes a hard assertion again.
--
-- Skills: data-engineer (view<->source enum contract), analytics-engineer
-- (KPI source filter), marketplace (listing lifecycle).

BEGIN;

CREATE OR REPLACE VIEW public.v_marketplace_sellers_truth AS
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
    s.stripe_account_id,
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

COMMIT;
