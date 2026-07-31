-- 20260731000013_service_knob_pct.sql
--
-- THE RESOLVER COULD NOT SEE THE NEW KNOBS. 20260731000011 added commission_pct / listing_fee_pct /
-- cashback_pct / min_list_balance as COLUMNS, but service_knob()'s CASE still listed only the original seven
-- keys — so service_knob(hive,'cashback_pct') returned NULL and mint_service_cashback() silently returned 0
-- on a perfectly settled request. Caught by the probe, which expected 20 and got 0.
--
-- Same family as the three unread knobs before it, one layer deeper: there the COLUMN had no consumer, here
-- the RESOLVER had no case. A knob is only real once every layer between the setting and the behaviour can
-- see it.
--
-- A SEPARATE FUNCTION, NOT A WIDENED RETURN TYPE. service_knob() returns integer and its callers do interval
-- arithmetic (`120 * interval '1 second'`), which Postgres defines for integer but NOT for numeric. Widening
-- it to numeric to fit the percentages would have broken the sweep at runtime — the kind of change that looks
-- like a tidy-up and lands as an outage. So the decimal knobs get their own accessor and the integer one is
-- left exactly as the sweep already uses it.

CREATE OR REPLACE FUNCTION public.service_knob_pct(p_hive uuid, p_key text)
RETURNS numeric
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
  SELECT COALESCE(
    (SELECT CASE p_key
              WHEN 'commission_pct'  THEN s.commission_pct
              WHEN 'listing_fee_pct' THEN s.listing_fee_pct
              WHEN 'cashback_pct'    THEN s.cashback_pct
            END
       FROM public.hive_service_settings s WHERE s.hive_id = p_hive),
    -- platform defaults, stated once so the column default and the fallback cannot drift apart
    CASE p_key
      WHEN 'commission_pct'  THEN 5.00
      WHEN 'listing_fee_pct' THEN 0.00
      WHEN 'cashback_pct'    THEN 1.00
    END);
$fn$;

COMMENT ON FUNCTION public.service_knob_pct(uuid, text) IS
  'Effective value of a DECIMAL D9 credit-policy knob for a hive (commission/listing-fee/cashback percent). '
  'Separate from service_knob() because that one returns integer for interval arithmetic and widening it '
  'would break the broadcast sweep. A missing row is not a missing setting.';

-- min_list_balance is a whole number of credits, so it belongs on the INTEGER resolver.
CREATE OR REPLACE FUNCTION public.service_knob(p_hive uuid, p_key text)
RETURNS integer
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
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
      WHEN 'broadcast_radius_start_m' THEN 5000
      WHEN 'broadcast_radius_max_m'   THEN 100000
      WHEN 'broadcast_widen_rounds'   THEN 2
      WHEN 'tier_silver_sales'        THEN 11
      WHEN 'tier_gold_sales'          THEN 51
      WHEN 'min_list_balance'         THEN 0
    END);
$fn$;

-- point the cashback minter at the decimal resolver
CREATE OR REPLACE FUNCTION public.mint_service_cashback(p_request_id uuid)
RETURNS numeric
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
DECLARE
  r        public.service_requests%rowtype;
  v_pct    numeric;
  v_amount numeric;
BEGIN
  SELECT * INTO r FROM public.service_requests WHERE id = p_request_id;
  IF r.id IS NULL OR r.status <> 'settled' OR r.client_auth_uid IS NULL THEN
    RETURN 0;                       -- unknown, unsettled, or no consumer to credit
  END IF;

  v_pct := public.service_knob_pct(r.hive_id, 'cashback_pct');
  IF v_pct IS NULL OR v_pct <= 0 THEN
    RETURN 0;                       -- the hive has cashback switched off
  END IF;

  v_amount := round(coalesce(r.budget, 0) * v_pct / 100.0, 2);
  IF v_amount <= 0 THEN
    RETURN 0;                       -- a zero-value job earns nothing; do not mint dust rows
  END IF;

  INSERT INTO public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  VALUES ('consumer', r.client_auth_uid, 'cashback', v_amount, 'service_request', r.id,
          v_pct || '% cashback on a settled service request')
  ON CONFLICT DO NOTHING;

  RETURN v_amount;
END
$fn$;

REVOKE ALL ON FUNCTION public.mint_service_cashback(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.mint_service_cashback(uuid) TO service_role;
