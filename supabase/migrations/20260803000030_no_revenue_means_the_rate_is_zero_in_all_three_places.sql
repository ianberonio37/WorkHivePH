-- "No revenue. The platform takes no commission and no spread." — decided in the approved credits plan,
-- never implemented. This implements it, and it takes THREE changes rather than one.
--
-- The commission rate is currently defined in three places, and the one that actually fires is the one a
-- knob change would not have touched:
--
--   1. hive_service_settings.commission_pct  DEFAULT 5.00   -- and ZERO hives have a settings row
--   2. service_knob_pct(...,'commission_pct') fallback 5.00 -- the trigger does not use it for the rate
--   3. mint_settlement_commission's OWN fallback:           -- <<< THIS is what charges every job today
--          WHEN new.segment = 'consumer' THEN 0.100 ELSE 0.050
--
-- Measured before writing this: 3 hives, 0 settings rows. So every settled job has been charged by the
-- hardcoded branch in (3). Setting the knob default to 0 would have changed nothing at all while looking
-- exactly like a fix — the same "one rule, two sources" shape that has already cost this codebase a cap
-- that never bound and a confirm sheet that offered nothing.
--
-- So the rate collapses to ONE source. The trigger asks service_knob_pct and nothing else; a hive that
-- wants to charge sets its own knob, and the platform default is 0.
--
-- CASHBACK COMES ALONG FOR FREE, and that is not a coincidence. hive_service_settings already carries
--     CHECK (cashback_pct <= commission_pct + listing_fee_pct)
-- so with commission and listing fee at 0, cashback is FORCED to 0 by a constraint that has been there
-- all along. The approved plan's "the 1% cashback is REPLACED by the 10% reward" is therefore not a
-- second decision — it is what the schema already implies once revenue is 0.
--
-- HISTORY IS NOT REWRITTEN. The 3 existing commission entries (−PHP360) stay exactly where they are: the
-- ledger is append-only, and a platform that edits its own history to match a new policy is not one whose
-- numbers anyone should trust.

-- ── 1. the platform defaults ─────────────────────────────────────────────────────────────────────────
create or replace function public.service_knob_pct(p_hive uuid, p_key text)
returns numeric
language sql
stable security definer
set search_path to 'pg_catalog', 'public'
as $function$
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
      WHEN 'commission_pct'       THEN 0.00    -- NO REVENUE. The platform takes nothing on a job.
      WHEN 'listing_fee_pct'      THEN 0.00
      WHEN 'cashback_pct'         THEN 0.00    -- retired: the 10% reward is the only reward mechanic
      WHEN 'reward_pct'           THEN 10.00   -- Ian's flat 10%, held in the seller wallet per listing
      WHEN 'reward_spend_cap_pct' THEN 10.00   -- a buyer may pay at most 10% of a purchase in credits
      WHEN 'holding_fee_pct'      THEN 2.00    -- per month, on LIVE listings only (anti-nuisance)
    END);
$function$;

alter table public.hive_service_settings alter column commission_pct set default 0.00;
alter table public.hive_service_settings alter column cashback_pct   set default 0.00;

-- Any hive that already has a row keeps its own choice unless it is still on the old platform rate.
update public.hive_service_settings set commission_pct = 0.00 where commission_pct = 5.00;
update public.hive_service_settings set cashback_pct   = 0.00 where cashback_pct   = 1.00;

-- ── 2. the trigger asks the knob, and stops carrying its own opinion ─────────────────────────────────
create or replace function public.mint_settlement_commission()
returns trigger
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $function$
DECLARE
  v_base numeric(12,2);
  v_rate numeric(6,4);
BEGIN
  IF new.status <> 'settled' OR old.status = 'settled' OR new.matched_provider_id IS NULL THEN
    RETURN new;
  END IF;

  SELECT COALESCE((SELECT p.amount_paid FROM public.service_payments p WHERE p.request_id = new.id),
                  public.service_agreed_base(new.id), 0) INTO v_base;

  -- ONE SOURCE. This used to fall back to a hardcoded 10%/5% by segment whenever a hive had no settings
  -- row - which is every hive - so the knob was decorative and the constant was the policy. Now the knob
  -- IS the policy, and its platform default is 0.
  v_rate := public.service_knob_pct(new.hive_id, 'commission_pct') / 100.0;

  IF v_rate <= 0 OR v_base <= 0 THEN
    RETURN new;                     -- nothing to charge; do not mint a zero row
  END IF;

  INSERT INTO public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  VALUES ('provider', new.matched_provider_id, 'commission', -round(v_base * v_rate, 2),
          'service_request', new.id,
          to_char(v_rate * 100, 'FM990.00') || '% commission on a settled job');
  RETURN new;
END $function$;

comment on function public.mint_settlement_commission() is
  'Charges the hive''s commission_pct on settlement. The platform default is 0 - WorkHive takes no '
  'commission and no spread - and the rate now comes from service_knob_pct ALONE. It previously carried '
  'its own hardcoded 10%/5%-by-segment fallback that fired whenever a hive had no settings row, which was '
  'every hive, so the knob was decorative and the constant was the real policy.';

comment on function public.service_knob_pct(uuid, text) is
  'Per-hive percentage knobs with platform defaults. commission_pct and cashback_pct default to 0: the '
  'platform earns nothing on a job, and the 10% listing reward is the only reward a buyer meets. A hive '
  'may still set its own, and hive_service_settings CHECKs cashback_pct <= commission_pct + '
  'listing_fee_pct, so cashback cannot outrun a take that no longer exists.';
