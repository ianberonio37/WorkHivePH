-- 20260717000004_marketplace_sellers_authuid_hardening.sql
--
-- Arc R (Z / A01) — the second half of Ian's "harden the over-exposures" (2026-07-17). The
-- marketplace_sellers cross-hive ROW read is by-design (bazaar seller directory), but the internal
-- `auth_uid` UUID was needlessly readable cross-hive (a marketplace-identity ↔ auth-identity
-- correlation primitive). Only ONE client path read it cross-hive — marketplace-seller-profile's
-- reputation lookup — so we resolve auth_uid SERVER-SIDE and remove it from the client surface.
--
-- 1. get_seller_community_reputation(worker, hive): a DEFINER wrapper that resolves the seller's
--    auth_uid server-side (gated to ACTUAL sellers), then returns the same cross-hive reputation
--    aggregation as get_community_reputation_by_auth — so the client never needs auth_uid.
-- 2. v_marketplace_sellers_truth recreated WITHOUT auth_uid (it was the only cross-hive exposure).
-- 3. REVOKE SELECT(auth_uid) on the base from anon/authenticated. RLS policies reference auth_uid
--    server-side (auth_uid = auth.uid() on insert/update/delete) — column-SELECT revoke does NOT
--    affect policy evaluation or INSERT/UPDATE, so seller-profile writes (auth_uid := session id)
--    are unaffected. Only client READS of the column are removed.

BEGIN;

-- 1. server-side-resolve reputation RPC (client never handles auth_uid) --------------------------
CREATE OR REPLACE FUNCTION public.get_seller_community_reputation(p_worker_name text, p_hive_id uuid)
  RETURNS TABLE(auth_uid uuid, xp_total bigint, public_posts bigint, safety_public_posts bigint, public_reactions_received bigint, hives_contributed bigint, is_voice_of_hive boolean, trust_tier text, last_active_at timestamp with time zone)
  LANGUAGE plpgsql
  STABLE SECURITY DEFINER
  SET search_path TO ''
AS $function$
DECLARE v_auth_uid uuid;
BEGIN
  IF auth.uid() IS NULL THEN RETURN; END IF;
  -- only an ACTUAL seller (opted into the public marketplace directory) has cross-hive reputation.
  SELECT ms.auth_uid INTO v_auth_uid
  FROM public.marketplace_sellers ms
  WHERE ms.worker_name = p_worker_name AND ms.hive_id = p_hive_id
  LIMIT 1;
  IF v_auth_uid IS NULL THEN RETURN; END IF;
  RETURN QUERY SELECT * FROM public.get_community_reputation_by_auth(v_auth_uid);
END;
$function$;

REVOKE ALL ON FUNCTION public.get_seller_community_reputation(text, uuid) FROM public, anon;
GRANT EXECUTE ON FUNCTION public.get_seller_community_reputation(text, uuid) TO authenticated, service_role;

-- 2. drop auth_uid from the truth view (security_invoker preserved) ------------------------------
DROP VIEW IF EXISTS public.v_marketplace_sellers_truth;
CREATE VIEW public.v_marketplace_sellers_truth
  WITH (security_invoker = on) AS
 SELECT s.id,
    s.worker_name,
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
   FROM public.marketplace_sellers s
     LEFT JOIN LATERAL ( SELECT count(*) AS n,
            max(l.created_at) AS last_at
           FROM public.marketplace_listings l
          WHERE l.seller_name = s.worker_name AND l.status = 'published'::text) active_listings ON true
     LEFT JOIN LATERAL ( SELECT count(*) AS n,
            max(o.created_at) AS last_at
           FROM public.marketplace_orders o
          WHERE o.seller_name = s.worker_name) total_orders ON true;

GRANT SELECT ON public.v_marketplace_sellers_truth TO anon, authenticated, service_role;

-- 3. remove auth_uid from the client-readable column set (policies + writes unaffected) ----------
-- A bare REVOKE SELECT(col) is a no-op while a TABLE-level SELECT grant exists (it covers all
-- columns). Correct pattern: revoke the table-level SELECT, then GRANT SELECT on the explicit
-- column list MINUS auth_uid. INSERT/UPDATE(auth_uid) stay granted (seller writes auth_uid :=
-- session id); RLS policies reference auth_uid server-side, unaffected by SELECT column grants.
REVOKE SELECT ON public.marketplace_sellers FROM anon, authenticated;
GRANT SELECT (id, worker_name, hive_id, tier, kyb_verified, kyb_verified_at, total_sales,
              rating_avg, rating_count, response_rate, response_time_h, created_at, updated_at,
              messenger_username, certifications, cert_verified, cert_verified_at)
  ON public.marketplace_sellers TO anon, authenticated;

COMMIT;
