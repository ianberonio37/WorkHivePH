-- A COMMISSION TOOK 200 CREDITS FROM A PROVIDER WHO HELD NONE
-- ═══════════════════════════════════════════════════════════════════════════════════════════════
-- Measured 2026-08-05, by tools/verify_money_lifecycle.py :: no_account_is_overdrawn:
--
--   provider 393af1b7 (Pablo Aguilar Mechanical Works)   balance -200.00
--     its only ledger row: commission -200.00  "5% commission — Laser Shaft Alignment ₱4,000"
--
-- The account had never received a credit. The commission simply charged it anyway, and the balance
-- went negative — which in this economy is not a debt, it is an impossibility: credits are minted by
-- verified top-ups and starter grants, they are non-transferable, and there is no cash-out. A
-- negative balance therefore describes 200 credits that were destroyed without ever having existed,
-- and mig 53 (which correctly began retiring commission from the treasury) faithfully retired them
-- too — so the platform's issuance ceiling was consumed by credits nobody was ever issued.
--
-- Every other credit path in this schema already floors. `guard_reward_spend_cap` refuses a spend
-- that would take a balance below zero, in as many words. The bank's own oracle for the dispute path
-- says it out loud: "the buyer is still made whole, the provider floors at 0, and the shortfall is
-- recorded as absorbed". Commission was the one debit with no floor.
--
-- Two changes: floor it going forward, then compensate the row that already went through.

-- ── 1 · a commission may not take more than the provider holds ─────────────────────────────────
create or replace function public.mint_settlement_commission()
returns trigger
language plpgsql
security definer
set search_path to 'public', 'pg_temp'
as $function$
DECLARE
  v_base      numeric(12,2);
  v_rate      numeric(6,4);
  v_fee       numeric(12,2);
  v_balance   numeric(12,2);
  v_charged   numeric(12,2);
  v_absorbed  numeric(12,2);
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

  -- THE FLOOR (mig 54). A provider cannot pay credits they do not hold. Charge what is there, and
  -- record the rest as absorbed by the platform rather than driving the balance negative — a negative
  -- balance here is not a debt, it is credits destroyed that were never issued.
  SELECT COALESCE(SUM(amount), 0) INTO v_balance
    FROM public.service_credit_ledger
   WHERE account_type = 'provider' AND account_id = new.matched_provider_id;

  v_charged  := LEAST(v_fee, GREATEST(v_balance, 0));
  v_absorbed := v_fee - v_charged;

  IF v_charged > 0 THEN
    INSERT INTO public.service_credit_ledger
      (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
    VALUES ('provider', new.matched_provider_id, 'commission', -v_charged,
            'service_request', new.id,
            to_char(v_rate * 100, 'FM990.00') || '% commission on a settled job'
            || CASE WHEN v_absorbed > 0
                    THEN ' (capped at the balance held; ' || to_char(v_absorbed, 'FM999G999G990.00')
                         || ' absorbed by the platform)'
                    ELSE '' END);

    -- A commission has ONE side: the credits leave the provider and leave circulation. Without this the
    -- treasury keeps counting them, and `issued_credits` drifts above the ledger by exactly the total
    -- commission ever charged (mig 53).
    PERFORM public.retire_credits(v_charged);
  END IF;

  RETURN new;
END $function$;

-- ── 2 · compensate the overdraft that already happened ─────────────────────────────────────────
-- An append-only ledger is corrected by a compensating ENTRY, never by deleting history. The
-- original -200 commission row stays exactly where it is; a matching +200 adjustment restores the
-- balance to the zero it should never have gone below, and the credits it re-creates are re-issued
-- so the treasury and the ledger stay equal (the invariant mig 53 restored).
do $$
declare
  r record;
  v_total numeric := 0;
begin
  for r in
    select account_type, account_id, sum(amount) as bal
      from public.service_credit_ledger
     group by account_type, account_id
    having sum(amount) < -0.005
  loop
    insert into public.service_credit_ledger
      (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
    values (r.account_type, r.account_id, 'adjustment', -r.bal, 'correction', null,
            'mig 54: restores a balance driven below zero by a commission charged against credits '
            'this account never held. The original commission row is left in place; this is the '
            'compensating entry.');
    v_total := v_total + (-r.bal);
    raise notice 'compensated % % by %', r.account_type, r.account_id, -r.bal;
  end loop;

  if v_total > 0 then
    -- These credits exist again, so the treasury must say so: mig 53 retired them when the commission
    -- destroyed them, and leaving issuance untouched here would put the ledger back above the treasury.
    perform public.issue_credits(v_total);
  end if;
end $$;

comment on function public.mint_settlement_commission() is
  'Charges the hive commission on settlement. Writes BOTH sides (a negative ledger row plus a matching '
  'retire_credits, mig 53) and FLOORS at the balance the provider actually holds, recording any '
  'shortfall as absorbed by the platform (mig 54) — a provider cannot pay credits they were never '
  'issued, and a negative balance in this economy is destroyed-but-never-minted credit.';
