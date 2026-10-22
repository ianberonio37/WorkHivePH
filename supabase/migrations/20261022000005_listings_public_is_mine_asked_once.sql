-- LB2 x BRH-R (2026-10-22): v_marketplace_listings_public asks "is this listing mine" ONCE per statement, as its reader.
--
-- Two earlier decisions disagreed, and query-indexes said so. LB2 (20261020000003) measured is_mine as
-- `l.auth_uid = auth.uid()` so an index could serve it. BRH-R (20261021000006) then made the view run as the person
-- reading it (security_invoker) - auth_uid is the one listing column a person may not read - and asked
-- listing_is_mine(l.id) instead: a SECURITY DEFINER call for every row, the shape LB2 had measured as a scan. The truth
-- view already holds the answer to both: the reader's own listing ids, asked once (`l.id = ANY (ARRAY(SELECT
-- public.my_listing_ids()))`, an InitPlan) - no auth_uid read, and an index lookup on the id. A visitor's set is empty:
-- is_mine false, published rows only, as before. The columns, their order and every other expression are unchanged.

create or replace view public.v_marketplace_listings_public with (security_invoker = true) as
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
    (l.id = ANY (ARRAY( SELECT public.my_listing_ids() AS my_listing_ids))) AS is_mine,
    l.ai_assisted_fields
   FROM marketplace_listings l
     LEFT JOIN marketplace_sellers ms ON ms.worker_name = l.seller_name
  WHERE l.status = 'published'::text OR (l.id = ANY (ARRAY( SELECT public.my_listing_ids() AS my_listing_ids)));
