-- ============================================================================
-- 10% MEANS 10% — the per-listing cap is removed
--
-- Ian, 2026-08-03: "there should be no capped as long as it should be 10% of
-- the listing price, why you are always dropping some things?"
--
-- He is right on both counts. The rule he stated is a flat 10% of the listing
-- price. The code has been computing min(10% * P, PHP500) since migration
-- 20260803000006 -- so a PHP50,000 listing reserved PHP500 (1%), not PHP5,000,
-- and a PHP1,000,000 listing reserved PHP500 (0.05%). The cap was chosen from
-- a 720-run sweep that measured 4.9x more listings sold at scale, and that
-- measurement was real -- but it was taken under the OLD economy (commission +
-- cashback, both since retired), and more importantly it was never Ian's rule.
-- Optimising a number he did not ask for, and then presenting it back as
-- settled, is the same failure as leaving commission at 5% while the approved
-- plan said "no revenue". Twice now.
--
-- WHAT THE FLAT RULE COSTS, stated plainly so it is a known trade and not a
-- surprise later: the reservation is what bounds the marketplace, because every
-- live listing LOCKS it. At a flat 10% the ceiling is exact and legible:
--
--     10,000,000 credits / 10%  =  PHP100,000,000 of concurrent listed inventory
--
-- Under the cap it was 20,000 concurrent listings of ANY value (PHP10bn of
-- inventory at PHP500k each), which is why the old sweep liked it. The flat
-- rule trades that headroom for proportionality: a provider listing PHP500,000
-- of equipment now commits PHP50,000 in credits, and the buyer of that item
-- receives PHP50,000 in credits rather than PHP500.
--
-- That is a coherent economy -- the commitment scales with the claim on the
-- marketplace, and the reward scales with what the buyer actually spent. To
-- grow past PHP100M of concurrent inventory, the lever is the SUPPLY CAP, which
-- is Ian's to raise, not a ceiling quietly applied per listing.
--
-- The knob is kept and set to NULL = "no cap", rather than deleted, so the
-- column cannot be silently re-populated by an older seed and start binding
-- again without anyone noticing.
-- ============================================================================

-- NULL now means "no cap". Anything already carrying 500 is cleared, or the old
-- ceiling would keep binding for that hive while the default said otherwise.
UPDATE public.hive_service_settings SET reward_max_per_listing = NULL
 WHERE reward_max_per_listing IS NOT NULL;

ALTER TABLE public.hive_service_settings
  ALTER COLUMN reward_max_per_listing DROP DEFAULT;

COMMENT ON COLUMN public.hive_service_settings.reward_max_per_listing IS
  'NULL = NO CAP, which is the rule: the reservation is a flat 10% of the listing price (Ian, '
  '2026-08-03). A non-NULL value re-introduces a per-listing ceiling and makes the reservation '
  'sublinear -- do not set one without an explicit decision.';

-- ── the reservation is now a pure percentage ────────────────────────────────
CREATE OR REPLACE FUNCTION public.listing_reservation_amount(p_hive uuid, p_price numeric)
 RETURNS numeric
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
  -- 10% of the listing price, full stop. service_knob_pct returns a WHOLE PERCENT (10.00 = 10%),
  -- matching commission_pct, so it divides by 100 here; reading it as a fraction would reserve TEN
  -- TIMES the price. The floor stays because reward_min_per_listing is 0 and a negative reservation
  -- is meaningless; the CEILING is gone (mig 35).
  select greatest(
           round(coalesce(p_price, 0) * public.service_knob_pct(p_hive, 'reward_pct') / 100.0, 2),
           coalesce(public.service_knob(p_hive, 'reward_min_per_listing'), 0)::numeric
         );
$function$;

-- ── service_knob must stop inventing a 500 that no longer exists ────────────
-- The fallback is what actually governs, because ZERO hives hold a settings row -- this is exactly
-- what made the commission knob a no-op for weeks. Returning NULL here is correct and the callers
-- coalesce it; a fallback of 500 would silently restore the cap the moment anyone read the knob.
CREATE OR REPLACE FUNCTION public.service_knob(p_hive uuid, p_key text)
 RETURNS integer
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
  SELECT COALESCE(
    (SELECT CASE p_key
              WHEN 'instant_ttl_seconds'      THEN s.instant_ttl_seconds
              WHEN 'quote_ttl_seconds'        THEN s.quote_ttl_seconds
              WHEN 'broadcast_radius_start_m' THEN s.broadcast_radius_start_m
              WHEN 'broadcast_radius_max_m'   THEN s.broadcast_radius_max_m
              WHEN 'broadcast_widen_rounds'   THEN s.broadcast_widen_rounds
              WHEN 'tier_silver_sales'        THEN s.tier_silver_sales
              WHEN 'tier_gold_sales'          THEN s.tier_gold_sales
              WHEN 'min_list_balance'         THEN s.min_list_balance
              WHEN 'reward_max_per_listing'   THEN s.reward_max_per_listing
              WHEN 'reward_min_per_listing'   THEN s.reward_min_per_listing
              WHEN 'starter_grant'            THEN s.starter_grant
              WHEN 'completion_window_days'   THEN s.completion_window_days
            END
       FROM public.hive_service_settings s WHERE s.hive_id = p_hive),
    CASE p_key
      WHEN 'instant_ttl_seconds'      THEN 120
      WHEN 'quote_ttl_seconds'        THEN 86400
      WHEN 'broadcast_radius_start_m' THEN 15000
      WHEN 'broadcast_radius_max_m'   THEN 100000
      WHEN 'broadcast_widen_rounds'   THEN 3
      WHEN 'tier_silver_sales'        THEN 11
      WHEN 'tier_gold_sales'          THEN 51
      WHEN 'min_list_balance'         THEN 200
      -- reward_max_per_listing: NO FALLBACK. NULL = no cap (mig 35, Ian's rule).
      WHEN 'reward_min_per_listing'   THEN 0
      WHEN 'starter_grant'            THEN 500
      WHEN 'completion_window_days'   THEN 3
    END);
$function$;
