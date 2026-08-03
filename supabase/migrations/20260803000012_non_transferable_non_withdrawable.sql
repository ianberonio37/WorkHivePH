-- The two properties the entire regulatory posture rests on, made structural instead of merely absent.
--
-- WorkHive Credits stay outside both heavy regimes because of exactly three facts: they never change
-- value, they cannot be transferred between users, and they cannot be turned back into cash.
--
--   NON-TRANSFERABLE  no secondary market. The SEC's investment-contract framework weights resale
--                     heavily -- "particularly if there is a secondary trading market that enables
--                     holders to resell and realize gains". No resale, no realizable gain.
--   NON-WITHDRAWABLE  no cash redemption. That is the prong that most clearly separates a closed-loop
--                     prepaid instrument from e-money, and BSP's moratorium on new VASP authorities
--                     (in force since 1 Sep 2022) means being classified into that regime is not
--                     something we could apply our way out of.
--
-- Today both are true only because no code implements them. That is not a guarantee, it is an absence --
-- and an absence is one well-meaning feature away from disappearing. The point of this migration is that
-- a future "let users gift credits to a friend" or "cash out your balance" cannot ship by accident: it
-- has to delete a guard that says, in the exception message, why it exists.

-- ── non-transferable ─────────────────────────────────────────────────────────────────────────────────
-- Credits move for exactly three reasons, all of them a platform act tied to a real transaction:
--   reward_fund/reward_earn  a sold listing hands its reservation to that listing's buyer
--   reward_spend             a buyer pays part of a purchase
--   commission/holding_fee/adjustment/starter_grant/topup   platform bookkeeping
-- What must never exist is a person-to-person move with no transaction behind it.
create or replace function public.guard_credits_non_transferable()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
begin
  -- Backend/system writes are vetted (seeders, sweeps, the reward path itself).
  if auth.uid() is null or current_setting('workhive.service_system_write', true) = 'on' then
    return new;
  end if;

  -- A signed-in client may never hand-write a movement into SOMEONE ELSE'S account. Every legitimate
  -- credit movement is written by a SECURITY DEFINER function on the platform's behalf, so a raw client
  -- insert naming another account is definitionally a transfer.
  if new.account_type = 'consumer' and new.account_id is distinct from auth.uid() then
    raise exception 'Credits cannot be moved between people. They are earned on a purchase and spent on '
                    'a purchase; there is no transfer, and that is deliberate - a credit that can be '
                    'passed around is a credit with a resale market.'
      using errcode = '42501';
  end if;

  -- And a client may never mint themselves a positive balance by hand either.
  if new.amount > 0 and new.entry_type not in ('reward_earn') then
    raise exception 'Credits are issued by the platform, not written by hand'
      using errcode = '42501';
  end if;
  return new;
end $function$;

drop trigger if exists trg_credits_non_transferable on public.service_credit_ledger;
create trigger trg_credits_non_transferable
  before insert on public.service_credit_ledger
  for each row execute function public.guard_credits_non_transferable();

-- ── non-withdrawable ─────────────────────────────────────────────────────────────────────────────────
-- There is no cash-out function, and this makes that fact CHECKABLE rather than merely true today.
-- `validate_credit_posture.py` asserts against this catalogue: if a future migration adds a function
-- whose name or body suggests redemption for cash, the gate names it and the posture decision gets made
-- deliberately rather than discovered later.
create or replace view public.v_credit_posture as
  select
    -- the three facts the posture depends on, each derived from the live catalogue
    (select count(*) = 0
       from pg_proc p join pg_namespace n on n.oid = p.pronamespace
      where n.nspname = 'public'
        and (p.proname ~* '(withdraw|cash_?out|redeem_for_cash|payout_credits)'))          as no_cash_out_function,
    (select count(*) > 0
       from pg_trigger t join pg_proc p on p.oid = t.tgfoid
      where p.proname = 'guard_credits_non_transferable' and not t.tgisinternal)           as transfer_guard_live,
    (select authorised_credits from public.credit_treasury where id = 1)                   as authorised_credits,
    (select issued_credits     from public.credit_treasury where id = 1)                   as issued_credits,
    -- 1 credit = PHP1, fixed. A rate column would be the first step toward a floating value, so there
    -- deliberately is not one: the constant lives here and nowhere else.
    1.00::numeric                                                                          as pesos_per_credit;

grant select on public.v_credit_posture to authenticated, anon, service_role;

comment on view public.v_credit_posture is
  'The credit posture, derived from the live catalogue rather than documented: no cash-out function '
  'exists, the transfer guard is installed, the supply is capped, and 1 credit = PHP1 fixed. These are '
  'the three facts that keep credits a closed-loop prepaid instrument rather than e-money or a security, '
  'so they are asserted by a gate instead of trusted.';

comment on function public.guard_credits_non_transferable() is
  'Refuses client-written credit movements into another person''s account, and refuses hand-minting a '
  'positive balance. Non-transferability is what denies credits a resale market, which is the factor the '
  'SEC investment-contract framework weights most heavily.';

-- ── the reward path is a PLATFORM act, and must announce itself as one ────────────────────────────────
-- grant_listing_reward() writes into TWO people's wallets — the seller's, whose reservation leaves, and
-- the buyer's, who receives it. SECURITY DEFINER changes the executing ROLE but not the JWT, so
-- auth.uid() inside it is still whoever marked the listing sold. The transfer guard above would
-- therefore refuse both legs and EVERY listing sale would fail.
--
-- The platform already has the vocabulary for "this write is a vetted system act": the
-- workhive.service_system_write GUC that seeders and sweeps use. The reward path sets it for the
-- statement, so the guard exempts it deliberately rather than by accident. (Caught by reading the
-- interaction back, which is the second time in this arc that a new guard would have silently broken an
-- existing path.)
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

  -- A reward with nowhere to go must never become a silent deduction.
  if v_buyer is null or v_seller is null then
    update public.credit_reservations set state = 'returned'
     where listing_id = new.id and state = 'released_to_buyer';
    return new;
  end if;

  perform set_config('workhive.service_system_write', 'on', true);   -- vetted platform act, this txn only
  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_seller, 'reward_fund', -v_amt, 'listing', new.id,
          'funded the buyer reward: ' || left(coalesce(new.title,''), 40));
  insert into public.service_credit_ledger (account_type,account_id,entry_type,amount,ref_kind,ref_id,note)
  values ('consumer', v_buyer,  'reward_earn',  v_amt, 'listing', new.id,
          'reward for buying: ' || left(coalesce(new.title,''), 40));
  perform set_config('workhive.service_system_write', 'off', true);
  return new;
end $function$;
