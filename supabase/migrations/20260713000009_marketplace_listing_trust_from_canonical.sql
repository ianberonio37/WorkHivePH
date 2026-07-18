-- 20260713000009_marketplace_listing_trust_from_canonical.sql
--
-- Marketplace listing TRUST-FORGE (BOLA — buyer deception) — bug-hunt 2026-07-13, marketplace.html P5.
--
-- v_marketplace_listings_truth exposed the buyer-facing trust signals from the LISTING columns
-- (l.seller_verified / l.completed_sales / l.rating_avg), and marketplace.html renders them as a
-- "Verified" badge, a sales-tier badge, and a star rating. But `mkt_listings_update` lets a seller
-- UPDATE their OWN listing (correct, for editing title/price), and RLS WITH CHECK cannot restrict
-- COLUMNS — so a seller could set seller_verified=true / completed_sales=999 / rating_avg=5 and forge
-- all three trust signals to buyers. LIVE-CONFIRMED (rolled back): a Baguio seller self-UPDATE of those
-- three fields succeeded (1 row). Same column-level trust-forge class as marketplace_sellers (fixed by
-- the guard_marketplace_seller_trust_columns trigger); the LISTINGS mirror was missed.
--
-- FIX (single source of truth, neutralizes the deception regardless of a forged l.*): source the three
-- displayed trust fields from the CANONICAL, already-protected marketplace_sellers (ms.*, guarded by
-- trg_guard_seller_trust). A forged listing column no longer reaches the buyer. The client selects the
-- fields by their aliases (seller_verified/completed_sales/rating_avg), so this is transparent — no
-- client change. A seller with no marketplace_sellers profile shows unverified/0-sales/null-rating
-- (HONEST — an unregistered seller is not verified). security_invoker=on is preserved (the platform-wide
-- cross-hive read-leak fix, mig 001). Types match exactly (int/numeric/boolean).

BEGIN;

CREATE OR REPLACE VIEW public.v_marketplace_listings_truth WITH (security_invoker = on) AS
SELECT
    l.id,
    l.hive_id,
    l.seller_name,
    l.seller_contact,
    (COALESCE(ms.kyb_verified, false) OR COALESCE(ms.cert_verified, false)) AS seller_verified,  -- CANONICAL (was l.seller_verified — forgeable)
    COALESCE(ms.total_sales, 0)                                              AS completed_sales,  -- CANONICAL (was l.completed_sales — forgeable)
    ms.rating_avg                                                           AS rating_avg,       -- CANONICAL (was l.rating_avg — forgeable)
    l.section,
    l.category,
    l.title,
    l.description,
    l.price,
    l.condition,
    l.location,
    l.image_url,
    l.status,
    l.view_count,
    l.created_at,
    l.updated_at,
    ms.tier            AS seller_tier,
    ms.kyb_verified    AS seller_kyb_verified,
    ms.total_sales     AS seller_total_sales,
    ms.rating_avg      AS seller_rating_avg_live,
    ms.rating_count    AS seller_rating_count,
    ms.response_rate   AS seller_response_rate,
    ms.response_time_h AS seller_response_time_h,
    (l.status = 'published'::text) AS is_published,
    (l.status = 'sold'::text)      AS is_sold,
    (l.status = 'draft'::text)     AS is_draft,
    l.part_number
FROM marketplace_listings l
     LEFT JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name;

COMMIT;
