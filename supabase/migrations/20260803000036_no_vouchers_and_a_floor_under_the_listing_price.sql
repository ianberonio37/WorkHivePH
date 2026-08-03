-- ============================================================================
-- TWO DECISIONS FROM IAN (2026-08-03): no vouchers, and a minimum listing price
--
-- ── (2) NO VOUCHERS ────────────────────────────────────────────────────────
-- Ian: "on number 2, no vouchers."
--
-- Vouchers minted `voucher_grant` — the ONLY unbacked credits in the economy.
-- Every other credit is bought for a peso; a voucher was minted from nothing,
-- which is why validate_credit_solvency treats them as the live solvency gap
-- and bounds them by everything the platform ever EARNED. With commission now
-- 0, that bound is frozen at PHP360 of historical revenue and can never grow,
-- so the feature was already dead by arithmetic. Retiring it deliberately is
-- better than leaving a money control that is unreachable AND unusable.
--
-- Measured before retiring: 3 voucher rows exist and ZERO voucher_grant /
-- voucher_reimburse ledger entries have ever been written. So nothing is being
-- unwound — no credit in circulation traces to a voucher, and the retirement
-- takes no value from anyone.
--
-- This also RESOLVES the stranded-control finding from be04ecdb: the voucher
-- create/pause UI lives only on the overlay-retired founder console. The answer
-- is not to lift it to a live surface. It is that the capability is retired.
--
-- ── (3) MINIMUM LISTING PRICE = PHP500 ─────────────────────────────────────
-- Ian: "on number 3, we have to decide what is the minimum listing amount."
--
-- Measured by tools/simulate_credit_reserve.py --minimum. The floor is doing
-- three jobs at once and PHP500 is where they agree:
--
--   floor      buyer earns   refused    GMV            note
--   none       PHP0.10       0.0%       PHP98,672,500  a PHP1 listing earns 10 centavos: unusable
--   PHP100     PHP10          0.0%      PHP98,672,500  free, but PHP10 is not persuasive
--   PHP500     PHP50         24.6%      PHP100,443,500 <- GMV goes UP
--   PHP1,000   PHP100        37.5%      PHP97,653,000  starts costing real supply
--   PHP2,000   PHP200        49.5%      PHP96,816,000  excludes a PHP800 bearing
--
-- The counter-intuitive result is the load-bearing one: at PHP500 the floor
-- refuses a QUARTER of listing attempts and GMV RISES. Those attempts were
-- consuming reservation against inventory nobody was going to buy, and the
-- reserve is the binding constraint on the whole marketplace — so refusing them
-- frees capacity for listings that do sell. Above PHP500 the floor starts
-- rejecting genuine trade and GMV falls monotonically.
--
-- And it makes the reward legible: 10% of PHP500 is PHP50, a number a buyer can
-- actually act on. Below that the earn rounds toward noise, which is the same
-- defect as a permanently-zero money tile — technically true, useless to read.
--
-- NOT a spam gate on its own: the 10% lock and the 2%/month holding fee already
-- price squatting (100 listings at the floor lock PHP5,000 and cost PHP120/yr).
-- The floor's job is legibility and reserve efficiency.
-- ============================================================================

-- ── (2) vouchers: refuse new ones, and refuse redemption ───────────────────
UPDATE public.service_vouchers SET active = false WHERE active;

CREATE OR REPLACE FUNCTION public.guard_vouchers_retired()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
  -- Deactivating or deleting an existing row stays allowed: retiring a feature must not also freeze
  -- the rows it left behind. Only bringing a voucher (back) to life is refused.
  IF TG_OP = 'INSERT' OR (TG_OP = 'UPDATE' AND coalesce(NEW.active, false)
                          AND NOT coalesce(OLD.active, false)) THEN
    RAISE EXCEPTION 'Vouchers are retired: they minted the only credits not backed by a peso, and the '
                    'platform takes no revenue to fund them. Credits enter only by purchase.'
      USING errcode = 'check_violation';
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_guard_vouchers_retired ON public.service_vouchers;
CREATE TRIGGER trg_guard_vouchers_retired
  BEFORE INSERT OR UPDATE ON public.service_vouchers
  FOR EACH ROW EXECUTE FUNCTION public.guard_vouchers_retired();

-- The redeem path is the other door. It must refuse for the same reason rather than fail obscurely
-- on an inactive row, so the person is told the feature is gone and not that their code is wrong.
CREATE OR REPLACE FUNCTION public.redeem_service_voucher(p_code text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
  RETURN jsonb_build_object(
    'ok', false,
    'reason', 'Vouchers are retired. Credits are earned by buying — pay a job in full and you receive '
              '10% back in credits.');
END;
$function$;

REVOKE ALL ON FUNCTION public.redeem_service_voucher(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.redeem_service_voucher(text) TO authenticated;

-- ── (3) the minimum listing price ──────────────────────────────────────────
ALTER TABLE public.hive_service_settings
  ADD COLUMN IF NOT EXISTS min_listing_price integer NOT NULL DEFAULT 500;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                  WHERE conrelid = 'public.hive_service_settings'::regclass
                    AND conname  = 'hive_service_settings_min_listing_sane') THEN
    ALTER TABLE public.hive_service_settings
      ADD CONSTRAINT hive_service_settings_min_listing_sane
      CHECK (min_listing_price BETWEEN 0 AND 100000);
  END IF;
END $$;

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
              WHEN 'min_listing_price'        THEN s.min_listing_price
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
      WHEN 'min_listing_price'        THEN 500   -- measured: GMV rises, reward becomes PHP50 (mig 36)
    END);
$function$;

-- Named `guard_listing_meets_minimum` deliberately: Postgres fires triggers in ALPHABETICAL order, so
-- `..._meets_minimum` runs before `..._requires_reservation`. A seller listing below the floor should
-- be told the price is too low, not that their credits are short for a listing they cannot make anyway.
CREATE OR REPLACE FUNCTION public.guard_listing_meets_minimum()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_min integer;
BEGIN
  -- Only polices a listing going LIVE. A draft may be saved at any price while the seller works on it;
  -- refusing mid-draft would lose their typing to a rule about publication.
  IF NEW.status IS DISTINCT FROM 'published' THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM 'published' THEN
    RETURN NEW;   -- already live; editing other fields is not a re-publication
  END IF;

  v_min := public.service_knob(NEW.hive_id, 'min_listing_price');
  IF coalesce(NEW.price, 0) < v_min THEN
    RAISE EXCEPTION 'The lowest price WorkHive lists is PHP%. This one is PHP% — bundle it with '
                    'something, or raise the price.',
                    to_char(v_min, 'FM999G999G990'), to_char(coalesce(NEW.price, 0), 'FM999G999G990')
      USING errcode = 'check_violation';
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_guard_listing_meets_minimum ON public.marketplace_listings;
CREATE TRIGGER trg_guard_listing_meets_minimum
  BEFORE INSERT OR UPDATE ON public.marketplace_listings
  FOR EACH ROW EXECUTE FUNCTION public.guard_listing_meets_minimum();
