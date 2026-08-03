-- The last anti-abuse lever the plan named, and the one the reservation alone cannot supply.
--
-- The 10% reservation was meant to stop nuisance listings. Simulating it directly (plan 4d) showed it
-- does not: a RETURNED reservation costs PHP0, so a funded actor can keep 250 junk listings live for a
-- year and pay nothing. Worse, the starter grant works AGAINST the reservation here -- 1,000 fake
-- accounts x PHP500 free credits = 2,500 free listings. The grant is already gated on identity
-- verification, but verification is a one-time cost and a determined Sybil pays it once per account.
--
-- What actually separates a real provider from a farmed one is not money, it is having TRANSACTED. So a
-- brand-new seller may hold a small number of live listings and no more until one of them completes.
-- Three is not arbitrary: the starter grant is PHP500 and a PHP2,000 listing reserves PHP200, so three is
-- exactly what the grant funds. A genuine provider hits this ceiling only if nothing they listed sold,
-- which is the case where more listings were not the answer anyway.
--
-- Deliberately NOT retroactive: it constrains new publishes, and the sellers already carrying three live
-- listings keep them. A guard that invalidates existing rows punishes people for a rule that did not
-- exist when they acted.

alter table public.hive_service_settings
  add column if not exists first_listings_before_sale integer not null default 3;

comment on column public.hive_service_settings.first_listings_before_sale is
  'How many live listings a seller who has never completed a sale may hold. Sized to the starter grant: '
  'PHP500 funds three PHP2,000 listings at a 10% reservation. 0 disables the gate.';

create or replace function public.guard_first_listings_need_a_sale()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $function$
declare
  v_limit integer;
  v_live  integer;
  v_sold  integer;
begin
  -- Only a publish is gated. Drafts, removals and the sale itself are untouched.
  if new.status <> 'published' then return new; end if;
  if tg_op = 'UPDATE' and old.status = 'published' then return new; end if;   -- already live, an edit

  -- Vetted writers: seeders and sweeps run with no JWT, and a platform act announces itself. Checked
  -- rather than assumed, because three guards in this arc broke an existing path by reasoning about WHO
  -- was writing while the real writer was a trigger running under someone else's token.
  --
  -- BOTH GUCs, because this table speaks a different dialect than the ledger does:
  -- guard_marketplace_listing_status exempts `workhive.listing_system_write` (its future auto-approve
  -- path), while the credit guards use `workhive.service_system_write`. Honouring only the credit one
  -- would leave this guard silently refusing a write the trigger beside it had already blessed.
  if auth.uid() is null
     or current_setting('workhive.service_system_write', true) = 'on'
     or current_setting('workhive.listing_system_write', true) = 'on' then
    return new;
  end if;

  select coalesce(
           (select s.first_listings_before_sale from public.hive_service_settings s
             where s.hive_id = new.hive_id), 3)
    into v_limit;
  if v_limit <= 0 then return new; end if;

  -- Has this seller ever completed anything? A sold listing is the direct proof. A completed service
  -- request is accepted too: a provider who has finished real jobs has demonstrated they exist, and
  -- refusing them a fourth listing would punish the wrong person.
  select count(*) into v_sold
    from public.marketplace_listings l
   where l.seller_name = new.seller_name and l.status = 'sold';

  if v_sold = 0 then
    select count(*) into v_sold
      from public.service_requests r
      join public.service_providers p on p.id = r.matched_provider_id
      join public.marketplace_sellers ms on ms.auth_uid = p.auth_uid
     where ms.worker_name = new.seller_name and r.status in ('completed','settled');
  end if;

  if v_sold > 0 then return new; end if;

  select count(*) into v_live
    from public.marketplace_listings l
   where l.seller_name = new.seller_name
     and l.status = 'published'
     and l.id is distinct from new.id;

  if v_live >= v_limit then
    raise exception 'A new seller can keep % listings live until one of them sells. You have % - sell one, '
                    'or take one down to make room. This is not about the credits: it is what stops one '
                    'person filling the catalogue with listings nobody ever buys.', v_limit, v_live
      using errcode = '42501';
  end if;
  return new;
end $function$;

drop trigger if exists trg_first_listings_need_a_sale on public.marketplace_listings;
create trigger trg_first_listings_need_a_sale
  before insert or update of status on public.marketplace_listings
  for each row execute function public.guard_first_listings_need_a_sale();

comment on function public.guard_first_listings_need_a_sale() is
  'Caps live listings for a seller who has never completed a sale. The 10% reservation does not deter a '
  'funded spammer because a returned reservation costs nothing; having transacted is the signal money is '
  'not. Lifts permanently on the first sold listing or completed service request.';
