-- ============================================================================
-- Marketplace PUBLIC SELLER PROFILE — make the seller profile anon-readable for SEO,
-- exposing PUBLIC-SAFE COLUMNS ONLY (Marketplace Deepwalk EXPANSION arc, J19/MK7, 2026-07-24)
-- ----------------------------------------------------------------------------
-- THE DEFECT (live-found as P-anon, the persona the prior arc never walked):
--   `marketplace-seller-profile.html` is DESIGNED public — it injects JSON-LD for crawlers, it is
--   linked "View profile ->" from anon-visible listing cards, and it has no signin gate. But its
--   only data source, `v_marketplace_sellers_truth` (security_invoker=on), inherits
--   `mkt_sellers_read USING (auth.uid() IS NOT NULL)` from `marketplace_sellers`. So for ANY
--   anonymous visitor — including Googlebot — the page renders its honest "Seller not found"
--   empty state. Every shared profile link and every crawl of the seller SEO surface was dead.
--
-- THE FIX (Ian's call 2026-07-24: "make it public (SEO) — safe columns only"):
--   A SECURITY DEFINER RPC that returns ONLY public-safe trust columns. It deliberately OMITS:
--     * messenger_username  — contact PII. Contact stays behind sign-in (MK3 disclosure-staging:
--                             the page's contact button is display:none unless this is present,
--                             so anon degrades gracefully to "no contact button" with no code change).
--     * hive_id / auth_uid  — tenant + identity topology (no cross-tenant enumeration from a public page).
--     * order/commercial internals (total_orders_count, last_order_at, profile_complete).
--   Everything returned here is ALREADY public elsewhere on the platform: seller_name,
--   seller_verified, completed_sales and rating_avg ship on every anon-readable listing row in
--   `v_marketplace_listings_truth`. This RPC does not widen the public surface beyond that — it
--   makes the seller PROFILE consistent with the listing grid that already shows those signals.
--
--   DEFINER (not a policy change) so the base-table RLS stays exactly as strict as it is today:
--   authenticated users keep reading the full row via the truth view (incl. messenger_username);
--   anon gets ONLY this projection. Same pattern as get_seller_community_reputation /
--   get_marketplace_trust_badges (public-scoped aggregates via DEFINER).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_marketplace_seller_public(p_worker_name text)
RETURNS TABLE (
  worker_name           text,
  tier                  text,
  kyb_verified          boolean,
  kyb_verified_at       timestamptz,
  cert_verified         boolean,
  cert_verified_at      timestamptz,
  certifications        text,
  total_sales           integer,
  rating_avg            numeric(3,2),
  rating_count          integer,
  response_rate         numeric(5,2),
  response_time_h       numeric(6,1),
  created_at            timestamptz,
  active_listings_count bigint,
  is_verified_public    boolean,
  last_listed_at        timestamptz
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
  -- Public-safe projection ONLY. Never add messenger_username / hive_id / auth_uid here:
  -- this function is granted to `anon`, so every column below is world-readable by design.
  SELECT
    s.worker_name,
    s.tier,
    s.kyb_verified,
    s.kyb_verified_at,
    s.cert_verified,
    s.cert_verified_at,
    s.certifications,
    s.total_sales,
    s.rating_avg,
    s.rating_count,
    s.response_rate,
    s.response_time_h,
    s.created_at,
    s.active_listings_count,
    s.is_verified_public,
    s.last_listed_at
  FROM public.v_marketplace_sellers_truth s
  WHERE s.worker_name = p_worker_name
  LIMIT 1;
$$;

REVOKE ALL ON FUNCTION public.get_marketplace_seller_public(text) FROM public;
GRANT EXECUTE ON FUNCTION public.get_marketplace_seller_public(text) TO anon, authenticated;

COMMENT ON FUNCTION public.get_marketplace_seller_public(text) IS
  'Public-safe seller profile for the anon-visible marketplace seller page + its JSON-LD (SEO). Returns trust/reputation columns only; deliberately OMITS messenger_username (contact stays sign-in gated per MK3 disclosure-staging), hive_id and auth_uid (no tenant/identity topology leak). SECURITY DEFINER so marketplace_sellers RLS stays authenticated-only for the full row. Marketplace Deepwalk EXPANSION arc J19/MK7, 2026-07-24.';
