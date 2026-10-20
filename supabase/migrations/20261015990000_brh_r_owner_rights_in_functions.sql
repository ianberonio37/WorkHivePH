-- BRH-R (2026-10-21): the last three SECURITY DEFINER views keep their owner rights inside a function the gates can see.
--
-- Supabase's advisor (security_definer_view, ERROR) named five views; two now run as their reader (20261015980000).
-- These three cannot, each for a measured reason:
--   v_marketplace_sellers_public  publishes per-seller TOTALS (orders, active listings); as invoker each reader's own row
--                                 policies changed the counts (Bryan Garcia's order total read 2 to himself, 0 to anyone
--                                 else) - a public total cannot depend on who asks
--   v_service_job_tracking        a provider's live location for the job's own client and provider
--   v_service_open_broadcasts     open requests near a provider's base location, for that provider
-- The last two filter by the caller (auth.uid(), my_service_provider_ids()) and read location columns no person may read
-- from the table directly.
--
-- Each view's query moves, unchanged, into a SECURITY DEFINER function, and the view (same name, same columns) becomes a
-- security_invoker view over it. What every reader gets is identical (compared through the API as a visitor, a provider
-- and a client); what changes is WHERE the owner rights live: in a function, where definer-doors holds them - a caller
-- check in the body, or a declared public projection - instead of in a view no gate looked at. The functions are granted
-- to exactly the roles the views were.

create or replace function public.marketplace_sellers_public_rows()
returns table ("worker_name" text, "hive_id" uuid, "tier" text, "kyb_verified" boolean, "cert_verified" boolean, "total_sales" integer, "rating_avg" numeric(3,2), "rating_count" integer, "response_rate" numeric(5,2), "response_time_h" numeric(6,1), "active_listings_count" bigint, "total_orders_count" bigint, "last_listed_at" timestamp with time zone, "last_order_at" timestamp with time zone, "is_verified_public" boolean, "profile_complete" boolean, "messenger_username" text, "certifications" text, "kyb_verified_at" timestamp with time zone, "cert_verified_at" timestamp with time zone, "created_at" timestamp with time zone)
language sql
stable
security definer
set search_path = public, extensions, pg_temp
as $fn$
SELECT s.worker_name,
    s.hive_id,
    s.tier,
    s.kyb_verified,
    s.cert_verified,
    s.total_sales,
    s.rating_avg,
    s.rating_count,
    s.response_rate,
    s.response_time_h,
    COALESCE(active_listings.n, (0)::bigint) AS active_listings_count,
    COALESCE(total_orders.n, (0)::bigint) AS total_orders_count,
    active_listings.last_at AS last_listed_at,
    total_orders.last_at AS last_order_at,
    (s.kyb_verified AND s.cert_verified) AS is_verified_public,
    ((s.messenger_username IS NOT NULL) AND (s.certifications IS NOT NULL)) AS profile_complete,
        CASE
            WHEN (auth.uid() IS NOT NULL) THEN s.messenger_username
            ELSE NULL::text
        END AS messenger_username,
        CASE
            WHEN (auth.uid() IS NOT NULL) THEN s.certifications
            ELSE NULL::text
        END AS certifications,
        CASE
            WHEN (auth.uid() IS NOT NULL) THEN s.kyb_verified_at
            ELSE NULL::timestamp with time zone
        END AS kyb_verified_at,
        CASE
            WHEN (auth.uid() IS NOT NULL) THEN s.cert_verified_at
            ELSE NULL::timestamp with time zone
        END AS cert_verified_at,
        CASE
            WHEN (auth.uid() IS NOT NULL) THEN s.created_at
            ELSE NULL::timestamp with time zone
        END AS created_at
   FROM ((marketplace_sellers s
     LEFT JOIN LATERAL ( SELECT count(*) AS n,
            max(l.created_at) AS last_at
           FROM marketplace_listings l
          WHERE ((l.seller_name = s.worker_name) AND (l.status = 'published'::text))) active_listings ON (true))
     LEFT JOIN LATERAL ( SELECT count(*) AS n,
            max(o.created_at) AS last_at
           FROM marketplace_orders o
          WHERE (o.seller_name = s.worker_name)) total_orders ON (true))
  WHERE ((auth.uid() IS NOT NULL) OR seller_has_published_listing(s.worker_name))
$fn$;
revoke all on function public.marketplace_sellers_public_rows() from public, anon, authenticated;
grant execute on function public.marketplace_sellers_public_rows() to anon, authenticated, service_role;

create or replace view public.v_marketplace_sellers_public with (security_invoker = true) as
select r."worker_name"::text as "worker_name",
       r."hive_id"::uuid as "hive_id",
       r."tier"::text as "tier",
       r."kyb_verified"::boolean as "kyb_verified",
       r."cert_verified"::boolean as "cert_verified",
       r."total_sales"::integer as "total_sales",
       r."rating_avg"::numeric(3,2) as "rating_avg",
       r."rating_count"::integer as "rating_count",
       r."response_rate"::numeric(5,2) as "response_rate",
       r."response_time_h"::numeric(6,1) as "response_time_h",
       r."active_listings_count"::bigint as "active_listings_count",
       r."total_orders_count"::bigint as "total_orders_count",
       r."last_listed_at"::timestamp with time zone as "last_listed_at",
       r."last_order_at"::timestamp with time zone as "last_order_at",
       r."is_verified_public"::boolean as "is_verified_public",
       r."profile_complete"::boolean as "profile_complete",
       r."messenger_username"::text as "messenger_username",
       r."certifications"::text as "certifications",
       r."kyb_verified_at"::timestamp with time zone as "kyb_verified_at",
       r."cert_verified_at"::timestamp with time zone as "cert_verified_at",
       r."created_at"::timestamp with time zone as "created_at"
from public.marketplace_sellers_public_rows() r;

create or replace function public.service_job_tracking_rows()
returns table ("request_id" uuid, "status" text, "provider_id" uuid, "provider_name" text, "live_lat" double precision, "live_lng" double precision, "request_lat" double precision, "request_lng" double precision, "location_updated_at" timestamp with time zone)
language sql
stable
security definer
set search_path = public, extensions, pg_temp
as $fn$
SELECT r.id AS request_id,
    r.status,
    sp.id AS provider_id,
    sp.display_name AS provider_name,
    st_y((sp.live_location)::geometry) AS live_lat,
    st_x((sp.live_location)::geometry) AS live_lng,
    st_y((r.location)::geometry) AS request_lat,
    st_x((r.location)::geometry) AS request_lng,
    sp.updated_at AS location_updated_at
   FROM (service_requests r
     JOIN service_providers sp ON ((sp.id = r.matched_provider_id)))
  WHERE ((r.status = ANY (ARRAY['en_route'::text, 'on_site'::text, 'in_progress'::text])) AND ((r.client_auth_uid = auth.uid()) OR ((r.hive_id IS NOT NULL) AND (r.hive_id IN ( SELECT hm.hive_id
           FROM hive_members hm
          WHERE ((hm.auth_uid = auth.uid()) AND (hm.status = 'active'::text))))) OR (sp.id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids))))
$fn$;
revoke all on function public.service_job_tracking_rows() from public, anon, authenticated;
grant execute on function public.service_job_tracking_rows() to anon, authenticated, service_role;

create or replace view public.v_service_job_tracking with (security_invoker = true) as
select r."request_id"::uuid as "request_id",
       r."status"::text as "status",
       r."provider_id"::uuid as "provider_id",
       r."provider_name"::text as "provider_name",
       r."live_lat"::double precision as "live_lat",
       r."live_lng"::double precision as "live_lng",
       r."request_lat"::double precision as "request_lat",
       r."request_lng"::double precision as "request_lng",
       r."location_updated_at"::timestamp with time zone as "location_updated_at"
from public.service_job_tracking_rows() r;

create or replace function public.service_open_broadcasts_rows()
returns table ("request_id" uuid, "segment" text, "mode" text, "urgency" text, "budget" numeric(12,2), "catalog_item_id" uuid, "catalog_name" text, "catalog_category" text, "catalog_unit" text, "catalog_rate" numeric(12,2), "custom_scope" text, "area_hint" text, "broadcast_radius_m" integer, "offer_ttl_expires_at" timestamp with time zone, "created_at" timestamp with time zone, "my_provider_id" uuid, "distance_km" numeric, "already_responded" boolean)
language sql
stable
security definer
set search_path = public, extensions, pg_temp
as $fn$
SELECT r.id AS request_id,
    r.segment,
    r.mode,
    r.urgency,
    r.budget,
    r.catalog_item_id,
    c.name AS catalog_name,
    c.category AS catalog_category,
    c.unit AS catalog_unit,
    c.base_rate AS catalog_rate,
    r.custom_scope,
    split_part(COALESCE(r.address, ''::text), ','::text, 1) AS area_hint,
    r.broadcast_radius_m,
    r.offer_ttl_expires_at,
    r.created_at,
    sp.id AS my_provider_id,
    round(((st_distance(r.location, sp.base_location) / (1000.0)::double precision))::numeric, 1) AS distance_km,
    (EXISTS ( SELECT 1
           FROM service_offers o
          WHERE ((o.request_id = r.id) AND (o.provider_id = sp.id)))) AS already_responded
   FROM ((service_requests r
     LEFT JOIN service_catalog c ON ((c.id = r.catalog_item_id)))
     JOIN service_providers sp ON ((sp.id IN ( SELECT my_service_provider_ids() AS my_service_provider_ids))))
  WHERE ((r.status = 'broadcasting'::text) AND (r.client_auth_uid IS DISTINCT FROM auth.uid()) AND ((r.location IS NULL) OR (sp.base_location IS NULL) OR st_dwithin(r.location, sp.base_location, ((r.broadcast_radius_m * 4))::double precision)) AND ((r.catalog_item_id IS NULL) OR (c.category = ANY (sp.categories))))
$fn$;
revoke all on function public.service_open_broadcasts_rows() from public, anon, authenticated;
grant execute on function public.service_open_broadcasts_rows() to anon, authenticated, service_role;

create or replace view public.v_service_open_broadcasts with (security_invoker = true) as
select r."request_id"::uuid as "request_id",
       r."segment"::text as "segment",
       r."mode"::text as "mode",
       r."urgency"::text as "urgency",
       r."budget"::numeric(12,2) as "budget",
       r."catalog_item_id"::uuid as "catalog_item_id",
       r."catalog_name"::text as "catalog_name",
       r."catalog_category"::text as "catalog_category",
       r."catalog_unit"::text as "catalog_unit",
       r."catalog_rate"::numeric(12,2) as "catalog_rate",
       r."custom_scope"::text as "custom_scope",
       r."area_hint"::text as "area_hint",
       r."broadcast_radius_m"::integer as "broadcast_radius_m",
       r."offer_ttl_expires_at"::timestamp with time zone as "offer_ttl_expires_at",
       r."created_at"::timestamp with time zone as "created_at",
       r."my_provider_id"::uuid as "my_provider_id",
       r."distance_km"::numeric as "distance_km",
       r."already_responded"::boolean as "already_responded"
from public.service_open_broadcasts_rows() r;
