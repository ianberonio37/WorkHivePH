-- Every hail opened at 5km and could never reach past 20km, so most of them found nobody.
--
-- The knob defaults were `start 5,000m · max 100,000m · widen_rounds 2`. The max is a red herring: two
-- doublings from 5km reach 20km and the hail then EXPIRES. The 100km ceiling was never once attained.
--
-- Simulated fill rate (share of buyers who find any eligible provider) against the real matching chain —
-- category, radius, certification, availability:
--
--     5km  -> 11%        15km -> 51%        30km -> 83%        50km -> 97%
--
-- So the sequence a client actually experienced was 11% -> 35% -> 65%, then expiry, after waiting three
-- TTLs. Half the market was unreachable no matter how long they waited.
--
-- This matters NOW in a way it did not last month. The radius was INERT until this session: UI hails
-- carried no location, so `accept_service_request`'s `st_dwithin` test was skipped entirely and every
-- provider matched every hail. The map pin fixed that — and the moment the geometry became real, the
-- radius numbers became load-bearing. A setting that had been decorative started deciding who gets work.
--
-- New sequence: 15km -> 30km -> 60km -> 100km (capped), i.e. 51% -> 83% -> 97% -> ~100%, in the SAME
-- three widen rounds and therefore the same six-minute wait as before. Nothing is slower; the reach is
-- simply not throttled to a fifth of the map.
--
-- Why not start even wider: a 5km first round is not wrong in a dense city, it is wrong as a PLATFORM
-- default for provincial Philippine geography, where the nearest calibration specialist may genuinely be
-- 40km away. Per-hive settings still override, so a Manila hive can tighten it back with a settings row.
--
-- Restated in full from `pg_get_functiondef`, not reconstructed from memory: the last time a function was
-- rebuilt here from a partial read it silently dropped three unrelated rules
-- ([[feedback_i_rebuilt_a_guard_from_a_partial_read]]). Only two literals below differ from the live
-- definition.

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
            END
       FROM public.hive_service_settings s WHERE s.hive_id = p_hive),
    CASE p_key
      WHEN 'instant_ttl_seconds'      THEN 120
      WHEN 'quote_ttl_seconds'        THEN 86400
      WHEN 'broadcast_radius_start_m' THEN 15000   -- was 5000: an opening round that reached 11% of buyers
      WHEN 'broadcast_radius_max_m'   THEN 100000
      WHEN 'broadcast_widen_rounds'   THEN 3       -- was 2: capped effective reach at 20km, never the max
      WHEN 'tier_silver_sales'        THEN 11
      WHEN 'tier_gold_sales'          THEN 51
      WHEN 'min_list_balance'         THEN 200
    END);
$function$;

comment on function public.service_knob(uuid, text) is
  'Per-hive service knob with platform defaults. broadcast_radius_start_m is 15,000 and widen_rounds is 3, '
  'giving 15/30/60/100km over the same three rounds as before: simulated fill 51/83/97/~100% versus the '
  'previous 11/35/65% which then expired. The 100km max was unreachable at 2 rounds from a 5km start.';
