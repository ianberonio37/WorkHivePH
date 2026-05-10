-- ─── v_marketplace_sellers_truth canonical view ──────────────────────────────
-- Truth-scattering fix for the marketplace_sellers hotspot. validate_silo_monitor
-- flagged 8 distinct consumer files reading the underlying table; profile pages
-- and admin lists each fetch sellers and then JOIN listings/orders client-side
-- to display "Joe (Gold) · 12 listings · 47 sold" tiles.
--
-- The view bakes in:
-- 1. active_listings_count — count of marketplace_listings WHERE seller_name=
--    sellers.worker_name AND status='active'. Pages reimplement this with a
--    second query + group-by.
-- 2. last_listed_at / last_order_at — convenience for sorting sellers by
--    activity.
-- 3. is_verified_public — kyb_verified AND cert_verified. The two flags are
--    AND-ed in 4 places with subtly different rules.
-- 4. profile_complete — has both messenger_username AND certifications.

CREATE OR REPLACE VIEW public.v_marketplace_sellers_truth AS
SELECT
  s.id, s.worker_name, s.auth_uid, s.hive_id,
  s.tier, s.kyb_verified, s.kyb_verified_at,
  s.cert_verified, s.cert_verified_at,
  s.total_sales, s.rating_avg, s.rating_count,
  s.response_rate, s.response_time_h,
  s.stripe_account_id, s.messenger_username, s.certifications,
  s.created_at, s.updated_at,
  -- Derived bridges (LATERAL keeps each per-seller subquery scoped + indexable)
  COALESCE(active_listings.n, 0)             AS active_listings_count,
  COALESCE(total_orders.n, 0)                AS total_orders_count,
  active_listings.last_at                    AS last_listed_at,
  total_orders.last_at                       AS last_order_at,
  -- Derived flags consolidate the AND-ed verification rules.
  (s.kyb_verified AND s.cert_verified)                                  AS is_verified_public,
  (s.messenger_username IS NOT NULL AND s.certifications IS NOT NULL)   AS profile_complete
FROM public.marketplace_sellers s
LEFT JOIN LATERAL (
  SELECT count(*) AS n, max(l.created_at) AS last_at
  FROM public.marketplace_listings l
  WHERE l.seller_name = s.worker_name
    AND l.status = 'active'
) active_listings ON TRUE
LEFT JOIN LATERAL (
  SELECT count(*) AS n, max(o.created_at) AS last_at
  FROM public.marketplace_orders o
  WHERE o.seller_name = s.worker_name
) total_orders ON TRUE;

GRANT SELECT ON public.v_marketplace_sellers_truth TO anon, authenticated;

COMMENT ON VIEW public.v_marketplace_sellers_truth IS
  'Canonical marketplace_sellers view: every column + active_listings_count + total_orders_count + last_listed_at + last_order_at + is_verified_public + profile_complete derived columns. Registered in canonical_sources as marketplace_sellers_truth.';

-- ─── Register marketplace_sellers_truth in canonical_sources ──────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('marketplace_sellers_truth', 'view', 'v_marketplace_sellers_truth', 'data-engineer', 'realtime',
   'Canonical marketplace_sellers reader. Carries every seller column plus LATERAL counts (active_listings, total_orders) and last-activity timestamps so profile pages and the admin grid no longer fan out to listings/orders for the same numbers. is_verified_public bakes in the kyb_verified AND cert_verified rule that 4 sites otherwise reimplement.',
   jsonb_build_object(
     'key',          jsonb_build_array('id'),
     'hive_scoped',  false,
     'soft_delete',  false,
     'derived_columns', jsonb_build_array('active_listings_count','total_orders_count','last_listed_at','last_order_at','is_verified_public','profile_complete'),
     'tier_values',  jsonb_build_array('bronze','silver','gold')
   ),
   'hive_id is nullable on marketplace_sellers (sellers can be cross-hive); the view inherits that and consumers should not assume a hive scope.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes;
