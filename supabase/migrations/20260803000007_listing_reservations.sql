-- The listing reservation: 10% of every listing, held in the seller's wallet until it sells.
--
-- Ian: "the provider wants to list an item, needs credits first to match the listing 10%, so that 10%
-- will be passed on to the buyer" — and its purpose: "to avoid abuse and nuisance from some providers."
--
-- THIS IS NOT THE LISTING FEE THAT WAS REJECTED IN JULY. MARKETPLACE_CREDIT_ECONOMY.md §2 argued against
-- a listing fee on arithmetic: a 5% fee at 20% sell-through really costs 25%, because a fee is consumed
-- whether or not the item sells. A RESERVATION is not consumed — if the listing never sells, the seller
-- keeps every credit. The only cost is working capital, the same shape as holding stock. That single
-- property is the difference between 10% and 25%, so `release_reservation_on_delist` below is not
-- housekeeping: it is what makes the whole instrument defensible.
--
-- RESERVED IS SEPARATE FROM AVAILABLE, and that separation is the point. Without it a seller publishes
-- ten listings against one listing's worth of credits and owes rewards it cannot pay. `available` is
-- therefore derived — bought + received − reserved — never stored, so it cannot drift from the truth.

create table if not exists public.credit_reservations (
  id           uuid        primary key default gen_random_uuid(),
  listing_id   uuid        not null references public.marketplace_listings(id) on delete cascade,
  seller_name  text        not null,
  hive_id      uuid,
  amount       numeric(12,2) not null,
  state        text        not null default 'held',
  released_at  timestamptz,
  created_at   timestamptz not null default now(),
  constraint credit_reservations_amount_pos check (amount > 0),
  constraint credit_reservations_state_ck   check (state in ('held','released_to_buyer','returned')),
  -- one live reservation per listing; a second would double-count the seller's obligation
  constraint credit_reservations_one_live   exclude (listing_id with =) where (state = 'held')
);

create index if not exists credit_reservations_seller on public.credit_reservations (seller_name, state);
create index if not exists credit_reservations_listing on public.credit_reservations (listing_id);

alter table public.credit_reservations enable row level security;

drop policy if exists credit_reservations_read on public.credit_reservations;
create policy credit_reservations_read on public.credit_reservations for select
  using (seller_name in (select public.auth_worker_names()) or public.is_marketplace_admin());

revoke all on public.credit_reservations from anon, authenticated;
grant select on public.credit_reservations to authenticated;
grant all    on public.credit_reservations to service_role;

-- ── the seller's balance, derived ────────────────────────────────────────────────────────────────────
create or replace function public.seller_credit_balance(p_seller text)
returns table (available numeric, reserved numeric, total numeric)
language sql
stable security definer
set search_path to 'pg_catalog', 'public'
as $function$
  -- ONE WALLET PER PERSON, keyed by auth_uid. The first draft joined service_providers on
  -- display_name = seller_name and would have returned ZERO for every seller on the platform: listing
  -- sellers are PEOPLE ('David Velasco') while provider profiles are BUSINESSES ('David Velasco
  -- Electrical Services'). Measured: 13 sellers, 7 providers, ZERO name matches. Two different identity
  -- spaces joined on a string that looks like it should match
  -- ([[feedback_maybesingle_bounced_multihive_users]] is the same mistake on a different pair).
  -- The ledger's `consumer` account type is already auth_uid-keyed, so it IS the person wallet: credits
  -- earned as a buyer and credits spent to list are the same pool, which is what "credits revolve"
  -- means.
  with me as (
    select auth_uid from public.marketplace_sellers where worker_name = p_seller limit 1
  ), led as (
    select coalesce(sum(l.amount), 0) as bal
      from public.service_credit_ledger l, me
     where l.account_type = 'consumer' and l.account_id = me.auth_uid
  ), res as (
    select coalesce(sum(amount), 0) as held
      from public.credit_reservations
     where seller_name = p_seller and state = 'held'
  )
  select (led.bal - res.held)::numeric, res.held::numeric, led.bal::numeric from led, res;
$function$;

-- ── what a listing must reserve ──────────────────────────────────────────────────────────────────────
-- reward_pct of the price, capped by reward_max_per_listing. The CAP is the single most effective knob
-- measured in simulation: at scale it raised throughput 4.9x versus a flat rate, because a flat 10% on a
-- PHP25,000 listing locks up PHP2,500 and exhausts the supply long before the marketplace is large.
-- The FLOOR defaults to 0 deliberately — a PHP200 floor was measured as the most harmful knob tested
-- (66% -> 38% healthy), since it makes a PHP500 listing reserve 40% of its own value.
create or replace function public.listing_reservation_amount(p_hive uuid, p_price numeric)
returns numeric
language sql
stable security definer
set search_path to 'pg_catalog', 'public'
as $function$
  select greatest(
           least(
             -- service_knob_pct returns a WHOLE PERCENT (10.00 = 10%), matching commission_pct, so it
             -- divides by 100 here. Reading it as a fraction would reserve TEN TIMES the price.
             round(coalesce(p_price,0) * public.service_knob_pct(p_hive,'reward_pct') / 100.0, 2),
             public.service_knob(p_hive,'reward_max_per_listing')::numeric
           ),
           public.service_knob(p_hive,'reward_min_per_listing')::numeric
         );
$function$;

-- ── publishing requires the reservation ──────────────────────────────────────────────────────────────
create or replace function public.guard_listing_requires_reservation()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare v_need numeric; v_avail numeric; v_held numeric;
begin
  -- backend/system writes (seeders, sweeps) are vetted, as everywhere else in this schema
  if auth.uid() is null or current_setting('workhive.service_system_write', true) = 'on' then
    return new;
  end if;

  -- only on the transition INTO published; an already-published row being edited keeps its reservation
  if new.status <> 'published' or (TG_OP = 'UPDATE' and old.status = 'published') then
    return new;
  end if;

  v_need := public.listing_reservation_amount(new.hive_id, new.price);
  if v_need <= 0 then return new; end if;

  select available into v_avail from public.seller_credit_balance(new.seller_name);
  select coalesce(sum(amount),0) into v_held
    from public.credit_reservations where listing_id = new.id and state = 'held';

  if v_held >= v_need then return new; end if;      -- already reserved (e.g. a re-publish)

  if coalesce(v_avail,0) < (v_need - v_held) then
    raise exception 'Listing needs % credits held (10%% of the price) and you have % available. '
                    'The credits are not a fee - they come back in full if it does not sell, and go to '
                    'your buyer if it does.',
                    to_char(v_need,'FM999G999G990'), to_char(coalesce(v_avail,0),'FM999G999G990')
      using errcode = 'check_violation',
            hint = 'Top up credits, or delist something to free the credits it is holding.';
  end if;

  insert into public.credit_reservations (listing_id, seller_name, hive_id, amount)
  values (new.id, new.seller_name, new.hive_id, v_need - v_held);
  return new;
end $function$;

drop trigger if exists trg_listing_requires_reservation on public.marketplace_listings;
create trigger trg_listing_requires_reservation
  before insert or update of status, price on public.marketplace_listings
  for each row execute function public.guard_listing_requires_reservation();

-- ── the reservation comes BACK when a listing does not sell ──────────────────────────────────────────
-- THE property that makes this a reservation and not a fee. Without it the effective cost at 20%
-- sell-through is 25% rather than 10%, and the July objection stands.
create or replace function public.release_reservation_on_delist()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
begin
  if new.status = old.status then return new; end if;

  if new.status in ('removed','draft') then
    update public.credit_reservations
       set state = 'returned', released_at = now()
     where listing_id = new.id and state = 'held';

  elsif new.status = 'sold' then
    -- the held credits become the buyer's reward; the ledger leg is written by the reward path
    update public.credit_reservations
       set state = 'released_to_buyer', released_at = now()
     where listing_id = new.id and state = 'held';
  end if;
  return new;
end $function$;

drop trigger if exists trg_release_reservation on public.marketplace_listings;
create trigger trg_release_reservation
  after update of status on public.marketplace_listings
  for each row execute function public.release_reservation_on_delist();

comment on table public.credit_reservations is
  'One live reservation per published listing: 10% of price, held in the seller wallet. RETURNED IN FULL '
  'if the listing is delisted or drafted - that is what makes it a reservation rather than the listing '
  'fee rejected in July, where an unsold listing cost 25% at 20% sell-through. Released to the buyer as '
  'reward credits when the listing sells.';
