-- The knobs the credit economy runs on, with defaults chosen from simulation rather than instinct.
--
-- Every value below was measured across 200 generated scenarios and a 720-run configuration sweep, and
-- two of them are set AGAINST the first instinct because the simulation contradicted it:
--
--   reward_max_per_listing = 500   the single most effective lever measured. At 20,000 providers listing
--                                  PHP25,000 items, a flat 10% sold 4,077 listings; a PHP500 ceiling sold
--                                  19,994 (4.9x), nearly matching a 5x supply increase without issuing a
--                                  single extra credit. A flat rate locks PHP2,500 per big-ticket listing
--                                  and exhausts the supply long before the marketplace is large.
--
--   reward_min_per_listing = 0     a PHP200 floor was the MOST HARMFUL knob tested: 66% -> 38% healthy,
--                                  and it created a 21% cash-hungry band, because a PHP500 listing would
--                                  reserve PHP200 - 40% of its own value rather than 10%. The floor exists
--                                  so the choice is explicit; the measurement says leave it at zero.
--
--   holding_fee_pct = 2.00         worth 0 points of throughput, and that is the point: it exists so that
--                                  parking junk listings costs something. A returned reservation has a real
--                                  cost of PHP0, so it deters the poor rather than the malicious - a funded
--                                  actor keeps 250 junk listings live for free. At 2%/month an honest
--                                  listing that sells in two months pays PHP8; a spammer holding 50 junk
--                                  listings for a year pays PHP2,400. It only bites listings that DO NOT
--                                  SELL, which is what catalogue nuisance actually is.
--
--   starter_grant = 500            the largest single gain of any knob: +8 points of health, and it removes
--                                  the STALLED failure entirely. Without it a cash-poor provider is blocked
--                                  ten times for every listing they manage, and that shows up on the DEMAND
--                                  side as buyers not served - fill rate falls from 51% to 30% when half of
--                                  providers are credit-starved.
--
-- PERCENT UNITS: service_knob_pct returns WHOLE PERCENTS (10.00 = 10%), matching the existing
-- commission_pct, and every consumer divides by 100. Integer knobs (peso amounts) go through service_knob.

alter table public.hive_service_settings
  add column if not exists reward_pct              numeric(5,2),
  add column if not exists reward_spend_cap_pct    numeric(5,2),
  add column if not exists holding_fee_pct         numeric(5,2),
  add column if not exists reward_max_per_listing  integer,
  add column if not exists reward_min_per_listing  integer,
  add column if not exists starter_grant           integer;

-- Tighten-only floors, in the same spirit as the tier thresholds: a hive may make its own sellers work
-- harder, never easier, so a hive cannot set a reward so large it drains the shared supply, nor a holding
-- fee so punitive it becomes a listing fee by another name.
alter table public.hive_service_settings
  drop constraint if exists hive_reward_pct_sane,
  drop constraint if exists hive_holding_fee_sane,
  drop constraint if exists hive_spend_cap_sane;
alter table public.hive_service_settings
  add constraint hive_reward_pct_sane   check (reward_pct           is null or reward_pct           between 0 and 20),
  add constraint hive_holding_fee_sane  check (holding_fee_pct      is null or holding_fee_pct      between 0 and 5),
  add constraint hive_spend_cap_sane    check (reward_spend_cap_pct is null or reward_spend_cap_pct between 0 and 50);

-- ── percent knobs ────────────────────────────────────────────────────────────────────────────────────
-- Restated in full from pg_get_functiondef; the three existing keys are byte-identical.
CREATE OR REPLACE FUNCTION public.service_knob_pct(p_hive uuid, p_key text)
 RETURNS numeric
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
  SELECT COALESCE(
    (SELECT CASE p_key
              WHEN 'commission_pct'       THEN s.commission_pct
              WHEN 'listing_fee_pct'      THEN s.listing_fee_pct
              WHEN 'cashback_pct'         THEN s.cashback_pct
              WHEN 'reward_pct'           THEN s.reward_pct
              WHEN 'reward_spend_cap_pct' THEN s.reward_spend_cap_pct
              WHEN 'holding_fee_pct'      THEN s.holding_fee_pct
            END
       FROM public.hive_service_settings s WHERE s.hive_id = p_hive),
    -- platform defaults, stated once so the column default and the fallback cannot drift apart
    CASE p_key
      WHEN 'commission_pct'       THEN 5.00
      WHEN 'listing_fee_pct'      THEN 0.00
      WHEN 'cashback_pct'         THEN 1.00
      WHEN 'reward_pct'           THEN 10.00   -- Ian's flat 10%, held in the seller wallet per listing
      WHEN 'reward_spend_cap_pct' THEN 10.00   -- a buyer may pay at most 10% of a purchase in credits
      WHEN 'holding_fee_pct'      THEN 2.00    -- per month, on LIVE listings only (anti-nuisance)
    END);
$function$;

-- ── integer (peso) knobs ─────────────────────────────────────────────────────────────────────────────
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
      WHEN 'reward_max_per_listing'   THEN 500   -- 4.9x throughput at scale vs a flat rate (measured)
      WHEN 'reward_min_per_listing'   THEN 0     -- a PHP200 floor was the most harmful knob tested
      WHEN 'starter_grant'            THEN 500   -- +8 pts health; removes STALLED entirely (measured)
    END);
$function$;

comment on function public.service_knob_pct(uuid, text) is
  'Per-hive percentage knobs, WHOLE PERCENTS (10.00 = 10%). reward_pct 10, spend cap 10, holding fee 2/mo. '
  'Consumers divide by 100 - reading these as fractions would be a 100x error.';
