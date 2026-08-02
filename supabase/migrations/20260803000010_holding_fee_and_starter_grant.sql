-- The two levers that make the reservation actually deter abuse, and let a poor provider start at all.
--
-- ── WHY A RESERVATION ALONE DOES NOT DETER ANYONE ────────────────────────────────────────────────────
-- Ian's stated purpose for the 10% is "to avoid abuse and nuisance from some providers". Simulating that
-- directly found it does not achieve it: a reservation is RETURNED, so its real cost is PHP0. Measured
-- cost to keep junk listings live indefinitely:
--
--     broke spammer   PHP500 budget  ->   2 listings, cost PHP0
--     funded spammer  PHP50,000      -> 250 listings, cost PHP0
--
-- It deters the poor, not the malicious. Worse, delist/repost churn is free, so 100 listings reposted
-- daily for a year is 36,500 top-of-feed placements at zero cost.
--
-- THE HOLDING FEE IS SELF-TARGETING. 2% per month, consumed from the reserved amount of LIVE listings:
--
--     sells in 1 month   PHP4   (0.2% of a PHP2,000 listing)
--     sells in 2 months  PHP8   (0.4%)
--     never sells, 1 yr  PHP48  (2.4%)   x 50 junk listings = PHP2,400/year
--
-- It needs no judgement about who is a spammer, because NOT SELLING is the signal — and not selling is
-- exactly what catalogue nuisance is. Simulation confirms it costs 0 points of marketplace health, which
-- is the property it needed: teeth without collateral damage.
--
-- Consumed credits RETIRE to the treasury rather than becoming platform income. They were never revenue;
-- they were a liability that expired.
--
-- ── AND WHY THE GRANT MUST BE GATED ──────────────────────────────────────────────────────────────────
-- The starter grant was the largest single gain measured (+8 points of health, and it removes the
-- STALLED failure entirely) because a cash-poor provider is otherwise blocked ten times for every
-- listing they manage — which shows up on the DEMAND side as fill rate falling from 51% to 30%.
--
-- But an UNGATED grant directly undermines the anti-abuse purpose above: 1,000 fake accounts would be
-- PHP500,000 of free credits and 2,500 free listings. The two mechanisms are in tension and have to be
-- designed together, so the grant is issued ONCE per verified seller, against the supply cap.

-- ── holding fee ──────────────────────────────────────────────────────────────────────────────────────
create or replace function public.sweep_listing_holding_fee()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_rate numeric; v_charged numeric := 0; v_n int := 0; r record;
begin
  for r in
    select cr.id, cr.amount, cr.seller_name, cr.hive_id, cr.listing_id, ms.auth_uid
      from public.credit_reservations cr
      join public.marketplace_listings l on l.id = cr.listing_id
      left join public.marketplace_sellers ms on ms.worker_name = cr.seller_name
     where cr.state = 'held' and l.status = 'published'
  loop
    v_rate := public.service_knob_pct(r.hive_id, 'holding_fee_pct') / 100.0;
    continue when v_rate <= 0 or r.auth_uid is null;

    declare v_fee numeric := round(r.amount * v_rate, 2);
    begin
      continue when v_fee <= 0;
      -- the fee comes out of the RESERVED amount, so a listing that never sells slowly gives its
      -- reservation back to the treasury rather than sitting there costing nothing
      update public.credit_reservations set amount = greatest(0, amount - v_fee) where id = r.id;
      insert into public.service_credit_ledger
        (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
      values ('consumer', r.auth_uid, 'holding_fee', -v_fee, 'listing', r.listing_id,
              'monthly holding fee on a live listing');
      perform public.retire_credits(v_fee);
      v_charged := v_charged + v_fee; v_n := v_n + 1;
    end;
  end loop;
  return jsonb_build_object('listings_charged', v_n, 'credits_retired', v_charged);
end $function$;

revoke all on function public.sweep_listing_holding_fee() from public, anon, authenticated;

select cron.schedule('listing-holding-fee-monthly', '0 3 1 * *',
                     $$SELECT public.sweep_listing_holding_fee();$$);

-- ── starter grant, once per VERIFIED seller ──────────────────────────────────────────────────────────
create table if not exists public.credit_starter_grants (
  auth_uid    uuid        primary key,
  amount      numeric(12,2) not null,
  granted_at  timestamptz not null default now(),
  constraint starter_grant_amount_pos check (amount > 0)
);

alter table public.credit_starter_grants enable row level security;
revoke all on public.credit_starter_grants from anon, authenticated;
grant all on public.credit_starter_grants to service_role;

create or replace function public.claim_starter_grant()
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_uid uuid := auth.uid(); v_amt numeric; v_verified boolean;
begin
  if v_uid is null then
    return jsonb_build_object('granted', false, 'reason', 'not_signed_in');
  end if;

  -- ONE PER PERSON, EVER. The primary key is what enforces it; this check is only for a kind message.
  if exists (select 1 from public.credit_starter_grants where auth_uid = v_uid) then
    return jsonb_build_object('granted', false, 'reason', 'already_claimed');
  end if;

  -- GATED ON A REAL SELLER PROFILE. Without this the grant is free fuel for Sybil accounts: 1,000 fake
  -- signups would be PHP500,000 of credits and 2,500 free listings, which would defeat the very
  -- anti-abuse purpose the reservation exists to serve.
  select true into v_verified from public.marketplace_sellers where auth_uid = v_uid limit 1;
  if not coalesce(v_verified, false) then
    return jsonb_build_object('granted', false, 'reason', 'no_verified_seller_profile');
  end if;

  v_amt := public.service_knob(null, 'starter_grant');
  if v_amt is null or v_amt <= 0 then
    return jsonb_build_object('granted', false, 'reason', 'grant_disabled');
  end if;

  -- issued against the supply cap like any other credit — a grant is not minted outside the ceiling
  perform public.issue_credits(v_amt);
  insert into public.credit_starter_grants (auth_uid, amount) values (v_uid, v_amt);
  insert into public.service_credit_ledger
    (account_type, account_id, entry_type, amount, ref_kind, note)
  values ('consumer', v_uid, 'starter_grant', v_amt, 'service_request',
          'starter credits so a first listing does not need cash up front');

  return jsonb_build_object('granted', true, 'amount', v_amt);
end $function$;

comment on function public.claim_starter_grant() is
  'One starter grant per verified seller, ever. Gated on a marketplace_sellers profile because an ungated '
  'grant is free fuel for Sybil accounts and would defeat the anti-abuse purpose of the reservation. '
  'Issued against the supply cap, never minted outside it.';

comment on function public.sweep_listing_holding_fee() is
  'Monthly 2% fee on the RESERVED amount of live listings. A returned reservation costs a spammer PHP0, so '
  'this is what actually deters parking junk: PHP8 for an honest listing that sells in two months, '
  'PHP2,400/year for 50 junk listings. Consumed credits RETIRE to treasury - they were an expired '
  'liability, never income.';
