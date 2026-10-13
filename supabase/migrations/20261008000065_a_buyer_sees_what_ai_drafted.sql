-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- ★ A BUYER SEES WHAT AN AI DRAFTED (marketplace, decided in UFAI §LM.11, 2026-10-08)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- marketplace_listings.ai_assisted_fields records which fields of a listing the seller let the listing assistant draft
-- and kept (marketplace.html writes it on publish). A buyer deciding whether to trust a stranger's words is owed
-- knowing which of them a model wrote - and nothing showed it. The public listing view now carries the field, so the
-- listing's detail sheet can say so under the description. Appended (CREATE OR REPLACE VIEW keeps every column before
-- it); the view stays a definer view with its own owner-or-published filter (20261008000060).
BEGIN;
CREATE OR REPLACE VIEW public.v_marketplace_listings_public AS
SELECT l.id,
    l.hive_id,
    l.seller_name,
    COALESCE(ms.kyb_verified, false) OR COALESCE(ms.cert_verified, false) AS seller_verified,
    COALESCE(ms.total_sales, 0) AS completed_sales,
    ms.rating_avg,
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
    ms.tier AS seller_tier,
    ms.kyb_verified AS seller_kyb_verified,
    ms.total_sales AS seller_total_sales,
    ms.rating_avg AS seller_rating_avg_live,
    ms.rating_count AS seller_rating_count,
    ms.response_rate AS seller_response_rate,
    ms.response_time_h AS seller_response_time_h,
    l.status = 'published'::text AS is_published,
    l.status = 'sold'::text AS is_sold,
    l.status = 'draft'::text AS is_draft,
    l.part_number,
    COALESCE(l.auth_uid = auth.uid(), false) AS is_mine,
    l.ai_assisted_fields
   FROM marketplace_listings l
     LEFT JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name
  WHERE l.status = 'published'::text OR l.auth_uid = auth.uid();
COMMIT;
