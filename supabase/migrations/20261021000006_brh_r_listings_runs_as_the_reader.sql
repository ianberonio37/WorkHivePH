-- BRH-R (2026-10-21): v_marketplace_listings_public - the marketplace's own listing grid - runs as the person reading it.
--
-- Supabase's advisor (security_definer_view, ERROR) named it among five views that read their base tables with their
-- OWNER's rights. It read auth_uid twice - to say "is this listing mine" and to admit a seller's own unpublished listings
-- - and auth_uid is the one listing column a person may not read (every listing's owner account; withheld on purpose).
-- Both now ask listing_is_mine(l.id), the existing SECURITY DEFINER helper that answers exactly that, so the view reads no
-- auth_uid; anon may read the public listing columns the view already shows, and the row policy mkt_listings_read
-- (published, or yours, or a marketplace admin) decides the rows, as the view's own filter does. Compared through the API
-- as a visitor (20 rows), a provider (24) and a client (20): identical rows, value for value.
--
-- It follows 20261020000003, which redefines this view: placed earlier, that redefinition would put the owner rights back.

grant select (id, hive_id, seller_name, section, category, title, description, price, condition, location, image_url, status, view_count, created_at, updated_at, part_number, ai_assisted_fields) on public.marketplace_listings to anon;

create or replace view public.v_marketplace_listings_public with (security_invoker = true) as
SELECT l.id,
    l.hive_id,
    l.seller_name,
    (COALESCE(ms.kyb_verified, false) OR COALESCE(ms.cert_verified, false)) AS seller_verified,
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
    (l.status = 'published'::text) AS is_published,
    (l.status = 'sold'::text) AS is_sold,
    (l.status = 'draft'::text) AS is_draft,
    l.part_number,
    COALESCE(public.listing_is_mine(l.id), false) AS is_mine,
    l.ai_assisted_fields
   FROM (marketplace_listings l
     LEFT JOIN marketplace_sellers ms ON ((ms.worker_name = l.seller_name)))
  WHERE ((l.status = 'published'::text) OR public.listing_is_mine(l.id));
