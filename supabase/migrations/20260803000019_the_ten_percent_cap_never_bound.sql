-- Ian's "they can only send it up to 10%" did not bind on a single real job.
--
-- guard_reward_spend_cap caps a credit payment against `service_requests.budget`, and returns early --
-- "not a service job; nothing to cap against" -- when budget is null. Measured against the actual data:
-- EVERY job with a matched provider has budget = NULL. Seven of seven. So the early return fired every
-- time, and a buyer could have paid for a PHP800 job entirely in credits.
--
-- The guard was not wrong about the rule; it was wrong about where the price lives. `budget` is the
-- CLIENT'S STATED WISH at request time, frequently never filled in. The number both parties actually
-- agreed is service_agreed_base(), which is already what commission bills and what cashback pays on --
-- mint_service_cashback was fixed for exactly this reason: it used to pay cashback on `budget`, "a wish
-- rather than a transaction", so a consumer could earn on a number nobody ever paid.
--
-- This is that same bug on the spend side, and it survived because the cap's failure mode is SILENT. A
-- wrong cap raises; a missing cap simply permits, and permission leaves no trace to notice.
--
-- Base order, most-agreed first: what was actually paid, else the agreed base, else the stated budget.
-- And when NONE of those yield a positive number, the guard now REFUSES instead of waving it through: a
-- job with no established price has no 10% to compute, and "no price yet" must not read as "no limit".

create or replace function public.guard_reward_spend_cap()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_price numeric; v_hive uuid; v_cap numeric; v_bal numeric;
begin
  if new.entry_type <> 'reward_spend' then return new; end if;

  select r.hive_id into v_hive from public.service_requests r where r.id = new.ref_id;
  if not found then return new; end if;            -- not a service job at all (e.g. a listing ref)

  -- THE PRICE, most-agreed first. budget is last because it is a wish; the earlier two are transactions.
  select coalesce(
           (select p.amount_paid from public.service_payments p where p.request_id = new.ref_id),
           nullif(public.service_agreed_base(new.ref_id), 0),
           (select r.budget from public.service_requests r where r.id = new.ref_id)
         ) into v_price;

  if coalesce(v_price, 0) <= 0 then
    raise exception 'This job has no agreed price yet, so there is no 10%% of it to pay in credits. '
                    'Agree a price with the provider first.'
      using errcode = 'check_violation';
  end if;

  v_cap := round(v_price * public.service_knob_pct(v_hive,'reward_spend_cap_pct') / 100.0, 2);
  if abs(new.amount) > v_cap + 0.005 then
    -- The percent SIGN is appended to the value inside to_char, not written as %% in the format string:
    -- PL/pgSQL resolves %%% left-to-right as literal-then-value, which printed "%10 of a purchase".
    raise exception 'Credits may cover at most % of a purchase (PHP% here); this would apply PHP%.',
                    to_char(public.service_knob_pct(v_hive,'reward_spend_cap_pct'),'FM990') || '%',
                    to_char(v_cap,'FM999G999G990'), to_char(abs(new.amount),'FM999G999G990')
      using errcode = 'check_violation';
  end if;

  -- and you cannot spend credits you do not hold
  select coalesce(sum(amount),0) into v_bal from public.service_credit_ledger
   where account_type = new.account_type and account_id = new.account_id;
  if v_bal + new.amount < -0.005 then
    raise exception 'Not enough credits: balance is PHP%, this would spend PHP%.',
                    to_char(v_bal,'FM999G999G990'), to_char(abs(new.amount),'FM999G999G990')
      using errcode = 'check_violation';
  end if;
  return new;
end $function$;

comment on function public.guard_reward_spend_cap() is
  'Caps a credit payment at reward_spend_cap_pct of the job price and at the payer''s balance. The price '
  'is amount_paid, else service_agreed_base, else budget - it capped against budget alone until '
  '20260803000019, and every job with a matched provider had a NULL budget, so the cap silently permitted '
  'everything. A job with no established price is refused rather than uncapped.';
