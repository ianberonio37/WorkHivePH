-- COMMISSION DEBITED THE LEDGER AND NEVER TOLD THE TREASURY
-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- Measured 2026-08-05, on the live local database:
--
--     credit_treasury.issued_credits          1500.00
--     sum(service_credit_ledger.amount)       1140.00
--     the gap                                  360.00  = 200 + 80 + 80, the three commission rows
--                                                        to the cent, and nothing else
--
-- Every other path in this schema moves the ledger and the treasury together, because a credit that
-- exists in one and not the other is a credit nobody can account for:
--
--   guard_service_topup_status   perform issue_credits(new.amount)   + a +topup ledger row
--   sweep_listing_holding_fee    perform retire_credits(v_fee)       + a -holding_fee ledger row
--   mint_settlement_commission                 -- nothing --         + a -commission ledger row
--
-- The third is the odd one out. It takes credits off a provider and out of circulation, and
-- `issued_credits` — the number that answers "how many credits exist" — never moves. Transfers are
-- rightly exempt (a reward_spend and its matching reward_earn net to zero and change no supply), but
-- a commission is not a transfer: it has one side. It is destruction, and destruction must be
-- recorded, exactly as the holding fee already does.
--
-- WHY THIS IS DORMANT AND STILL WORTH FIXING NOW. `service_knob_pct(hive,'commission_pct')` defaults
-- to 0, so v_rate <= 0 and no new commission row is minted today — the 360 is historical, from when
-- the rate was hardcoded. But the code path is live: the first hive to set a non-zero commission_pct
-- starts overstating the supply again on its first settlement, silently. And the 360 is wrong right
-- now — `v_credit_posture` publishes issued_credits, so the platform currently states a circulating
-- supply 360 credits larger than the credits that exist, and consumes 360 of the 10,000,000 issuance
-- ceiling on credits that were retired years ago in product time.
--
-- Two changes: pair the write, then reconcile the drift it already caused.

-- ── 1 · pair the write, the same way the holding fee does ──────────────────────────────────────
create or replace function public.mint_settlement_commission()
returns trigger
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $function$
DECLARE
  v_base numeric(12,2);
  v_rate numeric(6,4);
  v_fee  numeric(12,2);
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

  v_fee := round(v_base * v_rate, 2);

  INSERT INTO public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
  VALUES ('provider', new.matched_provider_id, 'commission', -v_fee,
          'service_request', new.id,
          to_char(v_rate * 100, 'FM990.00') || '% commission on a settled job');

  -- A commission has ONE side: the credits leave the provider and leave circulation. Without this the
  -- treasury keeps counting them, and `issued_credits` drifts above the ledger by exactly the total
  -- commission ever charged — which is how the 360 below came to exist.
  PERFORM public.retire_credits(v_fee);

  RETURN new;
END $function$;

-- ── 2 · reconcile the drift the missing pairing already produced ───────────────────────────────
-- Deliberately not a blind `set issued = sum(ledger)`. This lowers issuance by the un-retired
-- commission total and by nothing else, and it refuses to run if that figure does not close the gap
-- exactly — if some OTHER path is also unbalanced, this must fail loudly rather than paper over it.
do $$
declare
  v_issued  numeric;
  v_ledger  numeric;
  v_unpaired numeric;
begin
  select issued_credits into v_issued from public.credit_treasury where id = 1;
  select coalesce(sum(amount), 0) into v_ledger from public.service_credit_ledger;
  select coalesce(-sum(amount), 0) into v_unpaired
    from public.service_credit_ledger where entry_type = 'commission';

  if v_issued - v_ledger <> v_unpaired then
    raise exception 'the treasury is out by % but un-retired commission is only % — something OTHER '
                    'than commission is unbalanced, and this reconciliation would hide it',
                    v_issued - v_ledger, v_unpaired
      using errcode = 'check_violation';
  end if;

  if v_unpaired > 0 then
    perform public.retire_credits(v_unpaired);
    raise notice 'retired % credits that commission took off the ledger and never off the treasury',
                 v_unpaired;
  end if;
end $$;

comment on function public.mint_settlement_commission() is
  'Charges the hive commission on settlement. Writes BOTH sides: a negative ledger row against the '
  'provider and a matching retire_credits(), because a commission destroys credits rather than moving '
  'them. Mig 53 added the retirement; before it, issued_credits drifted above the ledger by the whole '
  'commission history.';
