-- 20260731000021_voucher_budget_cap.sql
--
-- P6. THE ONE UNBACKED CREDIT PATH, and until now nothing PREVENTED it.
--
-- Credits enter three ways and they are not equal: `topup` is backed by CASH (a provider paid GCash),
-- `cashback` is backed by REVENUE (and the hive_service_settings CHECK already refuses
-- cashback_pct > commission_pct + listing_fee_pct, so it cannot outrun the take per transaction), and
-- `voucher_grant` is backed by NOTHING. A generous promo and an accident are indistinguishable until the
-- float is gone — which is failure mode 5 of the sustainability study, "the most dangerous one, because it
-- is invisible until it is fatal".
--
-- `validate_credit_solvency.py` DETECTS over-granting (`vouchers <= commission ever earned`). Detection is
-- the right posture for a judgement call like an understated price; it is the WRONG posture for a number the
-- platform controls entirely. Nobody needs to grant more vouchers than the platform has ever earned, so this
-- is refused at write time rather than discovered at reconciliation.
--
-- WHY A TRIGGER AND NOT A CHECK: the rule is about the SUM of a column across the table, which a row-level
-- CHECK cannot see.
create or replace function public.guard_voucher_within_budget()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
DECLARE
  v_granted numeric;
  v_earned  numeric;
BEGIN
  IF new.entry_type <> 'voucher_grant' THEN
    RETURN new;
  END IF;

  SELECT coalesce(sum(amount), 0) INTO v_granted
    FROM public.service_credit_ledger WHERE entry_type = 'voucher_grant';
  SELECT coalesce(-sum(amount), 0) INTO v_earned
    FROM public.service_credit_ledger WHERE entry_type = 'commission';

  -- The budget is what the platform has actually EARNED. Granting beyond it means funding acquisition out
  -- of other people's prepaid balances, which works right up until they spend them.
  IF v_granted + new.amount > v_earned THEN
    RAISE EXCEPTION
      'Voucher budget exceeded: % already granted + % requested is more than the % earned in commission. '
      'Vouchers are the only credits backed by nothing; the budget is what the platform has earned.',
      round(v_granted, 2), round(new.amount, 2), round(v_earned, 2)
      USING ERRCODE = 'check_violation';
  END IF;

  RETURN new;
END
$$;

drop trigger if exists trg_guard_voucher_within_budget on public.service_credit_ledger;
create trigger trg_guard_voucher_within_budget
  before insert on public.service_credit_ledger
  for each row execute function public.guard_voucher_within_budget();

comment on function public.guard_voucher_within_budget() is
  'Refuses a voucher_grant that would push total vouchers past total commission earned. Vouchers are the '
  'only credits backed by NOTHING, so the platform''s own earnings are the budget. The solvency gate '
  'DETECTS this after the fact; this PREVENTS it, because unlike an understated price it is entirely the '
  'platform''s own decision and needs no human judgement.';
