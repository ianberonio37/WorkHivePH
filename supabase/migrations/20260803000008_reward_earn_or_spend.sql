-- Earn OR spend, never both on one job. This is the mechanic that keeps a balance drainable.
--
-- Ian: "when a buyer wants to spend 10% credit, the listing's pending 10% is given to him; but if the
-- buyer chooses to spend his own credits, those 10% credits are retained in the provider wallet."
--
-- WHY EXCLUSIVITY IS LOAD-BEARING. With a 10% reward and a 10% spend cap, allowing both on one job makes
-- the balance a TREADMILL: the buyer spends PHP200 and earns PHP200 on the same PHP2,000 purchase, so
-- their balance never falls. Credits accumulate that can never be drained, and a reward nobody can spend
-- stops being a reward. The exclusivity is what makes the number on screen mean something.
--
-- It also balances the circuit. At reward = spend cap the earn/spend split settles near 50/50, which is
-- what lets circulating credits plateau instead of growing without bound.

alter table public.service_credit_ledger
  drop constraint if exists service_credit_ledger_entry_type_check;
alter table public.service_credit_ledger
  add constraint service_credit_ledger_entry_type_check
  check (entry_type in ('topup','commission','voucher_grant','voucher_reimburse','adjustment','cashback',
                        'reward_earn','reward_spend','starter_grant','holding_fee'));

-- ── the exclusivity guard ────────────────────────────────────────────────────────────────────────────
create or replace function public.guard_reward_exclusive()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_other text;
begin
  if new.entry_type not in ('reward_earn','reward_spend') or new.ref_id is null then
    return new;
  end if;
  v_other := case new.entry_type when 'reward_earn' then 'reward_spend' else 'reward_earn' end;

  if exists (select 1 from public.service_credit_ledger
              where ref_id = new.ref_id and entry_type = v_other) then
    raise exception 'This job already carries a % entry; a buyer either EARNS the reward or SPENDS their '
                    'own credits, never both. Allowing both makes the balance a treadmill that can never '
                    'be drained.', v_other
      using errcode = 'check_violation';
  end if;

  -- and never twice on the same side
  if exists (select 1 from public.service_credit_ledger
              where ref_id = new.ref_id and entry_type = new.entry_type) then
    raise exception 'This job already carries a % entry.', new.entry_type
      using errcode = 'check_violation';
  end if;
  return new;
end $function$;

drop trigger if exists trg_reward_exclusive on public.service_credit_ledger;
create trigger trg_reward_exclusive
  before insert on public.service_credit_ledger
  for each row execute function public.guard_reward_exclusive();

-- ── the spend cap ────────────────────────────────────────────────────────────────────────────────────
-- A buyer may pay at most reward_spend_cap_pct of a purchase in credits. This is the redemption-velocity
-- limiter: it keeps credits a DISCOUNT rather than a currency, which is also what keeps the regulatory
-- posture light.
create or replace function public.guard_reward_spend_cap()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_price numeric; v_hive uuid; v_cap numeric; v_bal numeric;
begin
  if new.entry_type <> 'reward_spend' then return new; end if;

  select r.budget, r.hive_id into v_price, v_hive
    from public.service_requests r where r.id = new.ref_id;
  if v_price is null then return new; end if;      -- not a service job; nothing to cap against

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

drop trigger if exists trg_reward_spend_cap on public.service_credit_ledger;
create trigger trg_reward_spend_cap
  before insert on public.service_credit_ledger
  for each row execute function public.guard_reward_spend_cap();

-- ── a sold listing hands its reservation to the buyer ────────────────────────────────────────────────
-- The reservation was already marked released_to_buyer by the delist/sold trigger; this writes the
-- ledger leg that actually moves the credits, so the seller's held amount becomes the buyer's balance.
create or replace function public.grant_listing_reward()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_amt numeric; v_buyer uuid; v_seller uuid;
begin
  if new.status <> 'sold' or old.status = 'sold' then return new; end if;

  select amount into v_amt from public.credit_reservations
   where listing_id = new.id and state = 'released_to_buyer' order by created_at desc limit 1;
  if v_amt is null or v_amt <= 0 then return new; end if;

  select auth_uid into v_seller from public.marketplace_sellers where worker_name = new.seller_name limit 1;
  select i.buyer_auth_uid into v_buyer
    from public.marketplace_inquiries i where i.id = new.sold_to_inquiry_id;

  -- The seller's credits leave their wallet either way; if we cannot resolve a buyer account the
  -- credits RETURN to the seller rather than vanishing. A reward with nowhere to go must never become
  -- a silent deduction.
  if v_buyer is null then
    update public.credit_reservations set state = 'returned'
     where listing_id = new.id and state = 'released_to_buyer';
    return new;
  end if;

  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_seller, 'reward_spend', -v_amt, 'listing', new.id,
          'listing reward funded: ' || left(new.title, 40));
  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_buyer,  'reward_earn',  v_amt, 'listing', new.id,
          'reward for buying: ' || left(new.title, 40));
  return new;
end $function$;

drop trigger if exists trg_grant_listing_reward on public.marketplace_listings;
create trigger trg_grant_listing_reward
  after update of status on public.marketplace_listings
  for each row execute function public.grant_listing_reward();

comment on function public.guard_reward_exclusive() is
  'A job carries reward_earn OR reward_spend, never both, and never twice. At a 10% reward against a 10% '
  'spend cap, allowing both makes the balance a treadmill: spend 200, earn 200, balance never falls, and '
  'credits pile up that can never be drained.';
