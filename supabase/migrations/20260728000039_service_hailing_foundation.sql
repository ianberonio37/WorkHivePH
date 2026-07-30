-- SERVICE HAILING FOUNDATION (arc P1 — SERVICE_HAILING_ROADMAP.md §1 Fuel)
-- The request → match → dispatch → track → complete → settle substrate for the
-- service-hailing evolution of the marketplace. Nine tables + PostGIS enable +
-- the state-machine guard + RLS + realtime publications, in the house patterns:
--   * transition guard = guard_marketplace_order_status model (service-role /
--     admin / `workhive.service_system_write` GUC bypasses; raw JWT clients get
--     only the intake states + their own legal transitions)
--   * RLS scoping = hive_members join (never raw hive_id equality)
--   * money/trust rows (credit ledger) are NEVER client-writable — the
--     trust-forge lesson (migs 20260719000002/3) extended to MONEY
--   * live_location is privacy-by-default: NOT in the authenticated column
--     grant; exposed only via a P2 DEFINER tracking view gated on an ACTIVE job
--   * every streamed table is added to supabase_realtime (the R1 silent-zero
--     trap: without the publication line, .stream()/postgres_changes yields
--     NOTHING)
--   * reference defects fixed (R1): GiST indexes ARE created; accept is a
--     status-guarded atomic transition (P2 RPC), not select-then-insert.

-- =============================================
-- 0. PostGIS (G1 — first geo use on the platform)
-- =============================================
create extension if not exists postgis with schema extensions;

-- =============================================
-- 1. service_catalog — the rate card (instant mode's price list)
-- =============================================
create table if not exists public.service_catalog (
  id          uuid primary key default gen_random_uuid(),
  segment     text not null check (segment in ('industrial','consumer')),
  category    text not null,
  name        text not null,
  description text,
  unit        text not null default 'per_visit' check (unit in ('per_visit','per_hour')),
  base_rate   numeric(12,2) not null check (base_rate >= 0),
  active      boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
comment on table public.service_catalog is
  'Service-hailing rate card. Both segments seeded from day one; consumer rows sit behind the segment flag until P8.';

create index if not exists service_catalog_segment_active
  on public.service_catalog (segment, active);

-- =============================================
-- 2. service_providers — the "drivers": freelancers AND hive companies
-- =============================================
create table if not exists public.service_providers (
  id            uuid primary key default gen_random_uuid(),
  provider_type text not null check (provider_type in ('freelancer','hive')),
  auth_uid      uuid references auth.users(id) on delete set null,
  worker_name   text,
  hive_id       uuid references public.hives(id) on delete set null,
  display_name  text not null,
  contact       text,
  categories    text[] not null default '{}',
  service_areas text[] not null default '{}',
  base_location extensions.geography(POINT),
  live_location extensions.geography(POINT),
  base_lat      double precision generated always as (extensions.st_y(base_location::extensions.geometry)) stored,
  base_lng      double precision generated always as (extensions.st_x(base_location::extensions.geometry)) stored,
  availability  text not null default 'offline' check (availability in ('online','offline','on_job')),
  verified      boolean not null default false,
  verified_at   timestamptz,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  -- a freelancer is anchored to an auth account; a hive-company to a hive
  constraint service_provider_identity check (
    (provider_type = 'freelancer' and auth_uid is not null)
    or (provider_type = 'hive' and hive_id is not null)
  )
);
comment on table public.service_providers is
  'Provider registry (freelance technicians + hive service companies). live_location is privacy-guarded: no broad column grant; readable only via the active-job tracking view (P2).';

create index if not exists service_providers_base_location_gix
  on public.service_providers using gist (base_location);
create index if not exists service_providers_live_location_gix
  on public.service_providers using gist (live_location);
create index if not exists service_providers_availability
  on public.service_providers (availability) where availability = 'online';
create index if not exists service_providers_hive_id
  on public.service_providers (hive_id);

-- =============================================
-- 3. service_requests — the hail (state machine spine)
-- =============================================
create table if not exists public.service_requests (
  id                 uuid primary key default gen_random_uuid(),
  client_auth_uid    uuid not null references auth.users(id) on delete cascade,
  client_worker_name text,
  hive_id            uuid references public.hives(id) on delete set null, -- NULL = consumer (hive-less) client
  segment            text not null default 'industrial' check (segment in ('industrial','consumer')),
  mode               text not null check (mode in ('instant','quote')),
  catalog_item_id    uuid references public.service_catalog(id) on delete set null,
  custom_scope       text,
  address            text,
  location           extensions.geography(POINT),
  urgency            text not null default 'normal' check (urgency in ('low','normal','high','critical')),
  budget             numeric(12,2) check (budget is null or budget >= 0),
  status             text not null default 'requested' check (status in (
                       'requested','broadcasting','accepted','en_route','on_site',
                       'in_progress','completed','settled',
                       'cancelled_by_client','cancelled_by_provider','expired','disputed')),
  matched_provider_id uuid references public.service_providers(id) on delete set null,
  broadcast_radius_m integer not null default 3000 check (broadcast_radius_m between 500 and 100000),
  offer_ttl_expires_at timestamptz,
  accepted_at        timestamptz,
  en_route_at        timestamptz,
  on_site_at         timestamptz,
  in_progress_at     timestamptz,
  completed_at       timestamptz,
  settled_at         timestamptz,
  cancelled_at       timestamptz,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  constraint service_request_scope check (catalog_item_id is not null or custom_scope is not null)
);
comment on table public.service_requests is
  'A hail. State machine: requested→broadcasting→accepted→en_route→on_site→in_progress→completed→settled (+cancelled_by_client/cancelled_by_provider/expired/disputed). Transitions DB-enforced by guard_service_request_status.';

create index if not exists service_requests_location_gix
  on public.service_requests using gist (location);
create index if not exists service_requests_status
  on public.service_requests (status);
create index if not exists service_requests_client
  on public.service_requests (client_auth_uid);
create index if not exists service_requests_hive
  on public.service_requests (hive_id);
create index if not exists service_requests_provider
  on public.service_requests (matched_provider_id);

-- =============================================
-- 4. service_offers — accepts + quotes
-- =============================================
create table if not exists public.service_offers (
  id          uuid primary key default gen_random_uuid(),
  request_id  uuid not null references public.service_requests(id) on delete cascade,
  provider_id uuid not null references public.service_providers(id) on delete cascade,
  kind        text not null check (kind in ('accept','quote')),
  price       numeric(12,2) check (price is null or price >= 0),
  eta_minutes integer check (eta_minutes is null or eta_minutes between 0 and 10080),
  message     text,
  status      text not null default 'pending' check (status in ('pending','selected','declined','withdrawn','expired')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  constraint service_offer_one_per_provider unique (request_id, provider_id)
);
comment on table public.service_offers is
  'Provider responses to a hail: instant-mode accepts and quote-mode quotes. One per provider per request.';

create index if not exists service_offers_request
  on public.service_offers (request_id, status);
create index if not exists service_offers_provider
  on public.service_offers (provider_id, status);

-- =============================================
-- 5. service_job_events — append-only transition timeline
-- =============================================
create table if not exists public.service_job_events (
  id          bigint generated by default as identity primary key,
  request_id  uuid not null references public.service_requests(id) on delete cascade,
  actor_uid   uuid,
  actor_role  text,
  from_state  text,
  to_state    text not null,
  note        text,
  created_at  timestamptz not null default now()
);
comment on table public.service_job_events is
  'Append-only job timeline, written by the transition guard itself — the record outlives the action.';

create index if not exists service_job_events_request
  on public.service_job_events (request_id, created_at);

-- =============================================
-- 6. service_credit_ledger — append-only MONEY ledger (founder income)
-- =============================================
create table if not exists public.service_credit_ledger (
  id           bigint generated by default as identity primary key,
  account_type text not null check (account_type in ('provider','consumer')),
  account_id   uuid not null, -- provider_id for providers; auth_uid for consumers
  entry_type   text not null check (entry_type in ('topup','commission','voucher_grant','voucher_reimburse','adjustment')),
  amount       numeric(12,2) not null, -- signed: topups/grants positive, commissions negative
  ref_kind     text,
  ref_id       uuid,
  note         text,
  created_at   timestamptz not null default now()
);
comment on table public.service_credit_ledger is
  'Append-only credit ledger. Balance == SUM(amount) per account. NO client-writable path — entries are minted only by verified backend events (topup verification, completion commission, voucher flows). Credits are non-withdrawable prepaid platform fees.';

create index if not exists service_credit_ledger_account
  on public.service_credit_ledger (account_type, account_id, created_at);

-- =============================================
-- 7. service_credit_topups — GCash P2P intake + founder verification
-- =============================================
create table if not exists public.service_credit_topups (
  id            uuid primary key default gen_random_uuid(),
  account_type  text not null check (account_type in ('provider','consumer')),
  account_id    uuid not null,
  payer_auth_uid uuid not null references auth.users(id) on delete cascade,
  amount        numeric(12,2) not null check (amount > 0),
  gcash_ref     text not null check (gcash_ref ~ '^[0-9]{9,20}$'),
  status        text not null default 'pending_verification'
                check (status in ('pending_verification','verified','rejected')),
  verified_by   uuid,
  verified_at   timestamptz,
  note          text,
  created_at    timestamptz not null default now()
);
comment on table public.service_credit_topups is
  'GCash P2P top-up intake: user sends to the founder''s GCash number and files the reference no; the founder verifies against the GCash app. Verification (admin/GUC-only) mints the ledger entry.';

create index if not exists service_credit_topups_status
  on public.service_credit_topups (status, created_at);
create unique index if not exists service_credit_topups_ref_unique
  on public.service_credit_topups (gcash_ref) where status <> 'rejected';

-- =============================================
-- 8. service_vouchers + 9. service_voucher_redemptions
-- =============================================
create table if not exists public.service_vouchers (
  id             uuid primary key default gen_random_uuid(),
  code           text not null unique,
  kind           text not null check (kind in ('percent','fixed')),
  value          numeric(12,2) not null check (value > 0),
  segment        text check (segment is null or segment in ('industrial','consumer')),
  max_uses       integer check (max_uses is null or max_uses > 0),
  per_user_limit integer not null default 1 check (per_user_limit > 0),
  expires_at     timestamptz,
  active         boolean not null default true,
  created_at     timestamptz not null default now()
);
comment on table public.service_vouchers is
  'Founder-minted discount vouchers — platform-funded acquisition (signup/referral). Admin-only writes.';

create table if not exists public.service_voucher_redemptions (
  id               uuid primary key default gen_random_uuid(),
  voucher_id       uuid not null references public.service_vouchers(id) on delete cascade,
  request_id       uuid not null references public.service_requests(id) on delete cascade,
  consumer_auth_uid uuid not null references auth.users(id) on delete cascade,
  amount           numeric(12,2) not null check (amount >= 0),
  created_at       timestamptz not null default now(),
  constraint voucher_once_per_request unique (voucher_id, request_id)
);
comment on table public.service_voucher_redemptions is
  'Voucher redemption records — created only by the completion-gated redemption path (RPC/GUC), never by a raw client.';

-- =============================================
-- 10. State-machine guard (trust-forge pattern) + timeline writer
-- =============================================
create or replace function public.guard_service_request_status()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'extensions'
as $$
declare
  v_is_client boolean;
  v_is_matched_provider boolean;
  v_legal boolean := false;
begin
  -- backend writes (no JWT: seeders, system sweeps) are vetted — allow.
  -- (journaling lives in the AFTER trigger journal_service_request — an AFTER-INSERT
  --  journal from a BEFORE trigger FK-fails because the request row doesn't exist yet;
  --  caught live by the P1 adversarial suite.)
  if auth.uid() is null
     or public.is_marketplace_admin()
     or current_setting('workhive.service_system_write', true) = 'on' then
    return new;
  end if;

  -- ---- raw authenticated client from here ----
  if TG_OP = 'INSERT' then
    if new.status not in ('requested','broadcasting') then
      raise exception 'Not allowed: a new service request must start as requested/broadcasting (status % is system-set)', new.status
        using errcode = 'check_violation';
    end if;
    if new.client_auth_uid is distinct from auth.uid() then
      raise exception 'Not allowed: client_auth_uid must be the caller (attribution)' using errcode = 'check_violation';
    end if;
    if new.matched_provider_id is not null then
      raise exception 'Not allowed: a new request cannot be born matched' using errcode = 'check_violation';
    end if;
    return new;
  end if;

  -- UPDATE: who is the caller relative to this request?
  v_is_client := (old.client_auth_uid = auth.uid());
  v_is_matched_provider := exists (
    select 1 from public.service_providers sp
    where sp.id = old.matched_provider_id
      and (sp.auth_uid = auth.uid()
           or (sp.provider_type = 'hive' and sp.hive_id in (
                 select hm.hive_id from public.hive_members hm
                 where hm.auth_uid = auth.uid() and hm.status = 'active')))
  );

  if new.status is distinct from old.status then
    -- the accept transition (broadcasting→accepted) is RPC-only (atomic, GUC-announced) — never a raw client write.
    v_legal :=
         (v_is_client and old.status = 'requested'    and new.status = 'broadcasting')
      or (v_is_client and old.status = 'completed'    and new.status = 'settled')  -- P6: the client confirms they paid (mig 47 mints the commission)
      or (v_is_client and old.status in ('requested','broadcasting','accepted','en_route','on_site')
                      and new.status = 'cancelled_by_client')
      or (v_is_matched_provider and old.status = 'accepted'    and new.status = 'en_route')
      or (v_is_matched_provider and old.status = 'en_route'    and new.status = 'on_site')
      or (v_is_matched_provider and old.status = 'on_site'     and new.status = 'in_progress')
      or (v_is_matched_provider and old.status = 'in_progress' and new.status = 'completed')
      or (v_is_matched_provider and old.status in ('accepted','en_route','on_site')
                      and new.status = 'cancelled_by_provider')
      or ((v_is_client or v_is_matched_provider) and old.status in ('in_progress','completed')
                      and new.status = 'disputed');
    if not v_legal then
      raise exception 'Not allowed: illegal service request transition % -> % for this caller', old.status, new.status
        using errcode = 'check_violation';
    end if;
  elsif not (v_is_client or v_is_matched_provider) then
    raise exception 'Not allowed: only the request''s client or matched provider may edit it' using errcode = 'check_violation';
  end if;

  -- clients/providers may not reassign matching or identity fields directly
  if new.matched_provider_id is distinct from old.matched_provider_id then
    raise exception 'Not allowed: matching is set by the accept/select RPC, not a direct write' using errcode = 'check_violation';
  end if;
  if new.client_auth_uid is distinct from old.client_auth_uid then
    raise exception 'Not allowed: request ownership cannot be reassigned' using errcode = 'check_violation';
  end if;

  return new;
end $$;

drop trigger if exists trg_guard_service_request_status on public.service_requests;
create trigger trg_guard_service_request_status
  before insert or update on public.service_requests
  for each row execute function public.guard_service_request_status();

-- AFTER-trigger journaler: the record that outlives the action. Runs after the row
-- exists (the BEFORE-journal FK failure was caught live by the P1 adversarial suite).
create or replace function public.journal_service_request()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_role text;
begin
  if TG_OP = 'UPDATE' and new.status is not distinct from old.status then
    return new;
  end if;
  v_role := case
    when auth.uid() is null then 'system'
    when auth.uid() = new.client_auth_uid then 'client'
    when exists (select 1 from public.service_providers sp
                 where sp.id = new.matched_provider_id
                   and (sp.auth_uid = auth.uid()
                        or (sp.provider_type = 'hive' and sp.hive_id in (
                              select hm.hive_id from public.hive_members hm
                              where hm.auth_uid = auth.uid() and hm.status = 'active'))))
      then 'provider'
    else 'system' end;
  insert into public.service_job_events (request_id, actor_uid, actor_role, from_state, to_state)
  values (new.id, auth.uid(), v_role,
          case when TG_OP = 'INSERT' then null else old.status end, new.status);
  return new;
end $$;

drop trigger if exists trg_journal_service_request on public.service_requests;
create trigger trg_journal_service_request
  after insert or update on public.service_requests
  for each row execute function public.journal_service_request();

-- =============================================
-- 11. Provider availability follows the job (reference trigger, hardened)
-- =============================================
create or replace function public.sync_provider_availability()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  if new.matched_provider_id is null then return new; end if;
  if new.status in ('accepted','en_route','on_site','in_progress') then
    update public.service_providers set availability = 'on_job', updated_at = now()
    where id = new.matched_provider_id and availability <> 'on_job';
  elsif new.status in ('settled','cancelled_by_client','cancelled_by_provider','expired') then
    update public.service_providers set availability = 'online', updated_at = now()
    where id = new.matched_provider_id and availability = 'on_job';
  end if;
  return new;
end $$;

drop trigger if exists trg_sync_provider_availability on public.service_requests;
create trigger trg_sync_provider_availability
  after update of status on public.service_requests
  for each row execute function public.sync_provider_availability();

-- =============================================
-- 12. Provider write guard: verified + availability='on_job' are system-set
-- =============================================
create or replace function public.guard_service_provider_writes()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  if auth.uid() is null
     or public.is_marketplace_admin()
     or current_setting('workhive.service_system_write', true) = 'on' then
    return new;
  end if;
  if TG_OP = 'INSERT' then
    if new.verified then
      raise exception 'Not allowed: verification is granted by the platform, not self-declared' using errcode = 'check_violation';
    end if;
    if new.availability = 'on_job' then
      raise exception 'Not allowed: on_job is set by the job lifecycle' using errcode = 'check_violation';
    end if;
    return new;
  end if;
  if new.verified is distinct from old.verified or new.verified_at is distinct from old.verified_at then
    raise exception 'Not allowed: verification is granted by the platform, not self-declared' using errcode = 'check_violation';
  end if;
  if new.availability = 'on_job' and old.availability <> 'on_job' then
    raise exception 'Not allowed: on_job is set by the job lifecycle' using errcode = 'check_violation';
  end if;
  return new;
end $$;

drop trigger if exists trg_guard_service_provider_writes on public.service_providers;
create trigger trg_guard_service_provider_writes
  before insert or update on public.service_providers
  for each row execute function public.guard_service_provider_writes();

-- =============================================
-- 13. Top-up verification guard + ledger mint (money trust-forge)
-- =============================================
create or replace function public.guard_service_topup_status()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
begin
  if auth.uid() is null
     or public.is_marketplace_admin()
     or current_setting('workhive.service_system_write', true) = 'on' then
    -- a verification mints the ledger entry exactly once
    if TG_OP = 'UPDATE' and new.status = 'verified' and old.status = 'pending_verification' then
      new.verified_by := coalesce(new.verified_by, auth.uid());
      new.verified_at := coalesce(new.verified_at, now());
      insert into public.service_credit_ledger (account_type, account_id, entry_type, amount, ref_kind, ref_id, note)
      values (new.account_type, new.account_id, 'topup', new.amount, 'topup', new.id, 'GCash ref ' || new.gcash_ref);
    end if;
    return new;
  end if;
  -- raw client: may only file a PENDING intake row for themself
  if TG_OP = 'INSERT' then
    if new.status <> 'pending_verification' then
      raise exception 'Not allowed: a top-up starts pending_verification (the founder verifies it)' using errcode = 'check_violation';
    end if;
    if new.payer_auth_uid is distinct from auth.uid() then
      raise exception 'Not allowed: payer_auth_uid must be the caller' using errcode = 'check_violation';
    end if;
    return new;
  end if;
  raise exception 'Not allowed: top-up verification is founder/admin-only' using errcode = 'check_violation';
end $$;

drop trigger if exists trg_guard_service_topup_status on public.service_credit_topups;
create trigger trg_guard_service_topup_status
  before insert or update on public.service_credit_topups
  for each row execute function public.guard_service_topup_status();

-- =============================================
-- 13b. DEFINER helper — "my provider identities" (the user_hive_ids() pattern).
-- RLS policy subqueries run with the CALLER's column grants; since live_location's
-- privacy revoke strips broad access to service_providers, policies must resolve
-- provider identity through a DEFINER helper, not a raw subquery (caught live by
-- the P1 adversarial suite T11: request intake 42501'd post-revoke).
-- =============================================
create or replace function public.my_service_provider_ids()
returns setof uuid
language sql
stable
security definer
set search_path to 'pg_catalog', 'public'
as $$
  select sp.id from public.service_providers sp
  where sp.auth_uid = auth.uid()
     or (sp.provider_type = 'hive' and sp.hive_id in (
           select hm.hive_id from public.hive_members hm
           where hm.auth_uid = auth.uid() and hm.status = 'active'));
$$;
grant execute on function public.my_service_provider_ids() to authenticated;

-- =============================================
-- 14. RLS + grants
-- =============================================
alter table public.service_catalog             enable row level security;
alter table public.service_providers           enable row level security;
alter table public.service_requests            enable row level security;
alter table public.service_offers              enable row level security;
alter table public.service_job_events          enable row level security;
alter table public.service_credit_ledger       enable row level security;
alter table public.service_credit_topups       enable row level security;
alter table public.service_vouchers            enable row level security;
alter table public.service_voucher_redemptions enable row level security;

-- catalog: public browse (consumer door P8 needs anon), admin-only writes
-- rls-open-allow: platform rate card — a public price list by design (marketplace_listings precedent); no tenant data, admin-only writes
drop policy if exists service_catalog_read on public.service_catalog;
create policy service_catalog_read on public.service_catalog
  for select to anon, authenticated using (true);
drop policy if exists service_catalog_admin_write on public.service_catalog;
create policy service_catalog_admin_write on public.service_catalog
  for all to authenticated
  using (public.is_marketplace_admin()) with check (public.is_marketplace_admin());

-- providers: signed-in browse (live_location privacy = column grant, below);
-- self-registration + self/own-hive-supervisor updates
-- rls-open-allow: provider DIRECTORY (marketplace_sellers sibling) — discovery across hives IS the product; the always-true SELECT is defanged by the revoke-first COLUMN grant below (live_location/base_location/auth_uid NOT granted; T9 live-proved 42501) — see validate_rls_tenant_isolation BY_DESIGN entry
drop policy if exists service_providers_read on public.service_providers;
create policy service_providers_read on public.service_providers
  for select to authenticated using (true);
drop policy if exists service_providers_self_insert on public.service_providers;
create policy service_providers_self_insert on public.service_providers
  for insert to authenticated
  with check (
    (provider_type = 'freelancer' and auth_uid = auth.uid())
    or (provider_type = 'hive' and hive_id in (
          select hm.hive_id from public.hive_members hm
          where hm.auth_uid = auth.uid() and hm.status = 'active' and hm.role = 'supervisor'))
  );
drop policy if exists service_providers_self_update on public.service_providers;
create policy service_providers_self_update on public.service_providers
  for update to authenticated
  using (
    auth_uid = auth.uid()
    or (provider_type = 'hive' and hive_id in (
          select hm.hive_id from public.hive_members hm
          where hm.auth_uid = auth.uid() and hm.status = 'active' and hm.role = 'supervisor'))
  );

-- requests: the client (or their hive's members) and the matched provider see it;
-- broadcast visibility for candidate providers arrives via the P2 DEFINER view, not the raw table
drop policy if exists service_requests_party_read on public.service_requests;
create policy service_requests_party_read on public.service_requests
  for select to authenticated
  using (
    client_auth_uid = auth.uid()
    or (hive_id is not null and hive_id in (
          select hm.hive_id from public.hive_members hm
          where hm.auth_uid = auth.uid() and hm.status = 'active'))
    or matched_provider_id in (select public.my_service_provider_ids())
  );
drop policy if exists service_requests_client_insert on public.service_requests;
create policy service_requests_client_insert on public.service_requests
  for insert to authenticated with check (client_auth_uid = auth.uid());
drop policy if exists service_requests_party_update on public.service_requests;
create policy service_requests_party_update on public.service_requests
  for update to authenticated
  using (
    client_auth_uid = auth.uid()
    or matched_provider_id in (select public.my_service_provider_ids())
  );

-- offers: the offering provider and the request's client
drop policy if exists service_offers_party_read on public.service_offers;
create policy service_offers_party_read on public.service_offers
  for select to authenticated
  using (
    provider_id in (select public.my_service_provider_ids())
    or request_id in (select r.id from public.service_requests r where r.client_auth_uid = auth.uid())
  );
drop policy if exists service_offers_provider_insert on public.service_offers;
create policy service_offers_provider_insert on public.service_offers
  for insert to authenticated
  with check (
    provider_id in (select public.my_service_provider_ids())
  );
drop policy if exists service_offers_party_update on public.service_offers;
create policy service_offers_party_update on public.service_offers
  for update to authenticated
  using (
    provider_id in (select public.my_service_provider_ids())
    or request_id in (select r.id from public.service_requests r where r.client_auth_uid = auth.uid())
  );

-- job events: readable by the request's parties (same predicate through the request); writes = trigger only
drop policy if exists service_job_events_party_read on public.service_job_events;
create policy service_job_events_party_read on public.service_job_events
  for select to authenticated
  using (request_id in (select r.id from public.service_requests r)); -- r is already RLS-filtered per caller

-- credit ledger: own rows only; NO client insert/update/delete policies exist (backend-only)
drop policy if exists service_credit_ledger_own_read on public.service_credit_ledger;
create policy service_credit_ledger_own_read on public.service_credit_ledger
  for select to authenticated
  using (
    (account_type = 'consumer' and account_id = auth.uid())
    or (account_type = 'provider' and account_id in (select public.my_service_provider_ids()))
    or public.is_marketplace_admin()
  );

-- topups: payer files + sees own; admin sees all (verification queue)
drop policy if exists service_credit_topups_own on public.service_credit_topups;
create policy service_credit_topups_own on public.service_credit_topups
  for select to authenticated
  using (payer_auth_uid = auth.uid() or public.is_marketplace_admin());
drop policy if exists service_credit_topups_intake on public.service_credit_topups;
create policy service_credit_topups_intake on public.service_credit_topups
  for insert to authenticated with check (payer_auth_uid = auth.uid());
drop policy if exists service_credit_topups_admin_update on public.service_credit_topups;
create policy service_credit_topups_admin_update on public.service_credit_topups
  for update to authenticated
  using (public.is_marketplace_admin());

-- vouchers: signed-in read of active vouchers; admin-only writes; redemptions via RPC only
drop policy if exists service_vouchers_read on public.service_vouchers;
create policy service_vouchers_read on public.service_vouchers
  for select to authenticated using (active = true or public.is_marketplace_admin());
drop policy if exists service_vouchers_admin_write on public.service_vouchers;
create policy service_vouchers_admin_write on public.service_vouchers
  for all to authenticated
  using (public.is_marketplace_admin()) with check (public.is_marketplace_admin());
drop policy if exists service_voucher_redemptions_own_read on public.service_voucher_redemptions;
create policy service_voucher_redemptions_own_read on public.service_voucher_redemptions
  for select to authenticated
  using (consumer_auth_uid = auth.uid() or public.is_marketplace_admin());

-- grants. ★Supabase DEFAULT PRIVILEGES auto-grant ALL on new tables to anon/authenticated —
-- restrictive column-level privacy therefore requires REVOKE-first (grants are additive;
-- caught live by the P1 adversarial suite T9: live_location was readable despite the
-- column-list grant). Revoke the defaults, then grant back exactly what the design says.
revoke all on public.service_catalog             from anon, authenticated;
revoke all on public.service_providers           from anon, authenticated;
revoke all on public.service_requests            from anon, authenticated;
revoke all on public.service_offers              from anon, authenticated;
revoke all on public.service_job_events          from anon, authenticated;
revoke all on public.service_credit_ledger       from anon, authenticated;
revoke all on public.service_credit_topups       from anon, authenticated;
revoke all on public.service_vouchers            from anon, authenticated;
revoke all on public.service_voucher_redemptions from anon, authenticated;

grant select on public.service_catalog to anon, authenticated;
grant insert, update on public.service_catalog to authenticated; -- RLS admin-gates

-- providers: COLUMN-LEVEL select — live_location / base_location geography excluded;
-- the P2 DEFINER tracking view is the only live-location read path (privacy-by-default)
grant select (id, provider_type, worker_name, hive_id, display_name, contact, categories,
              service_areas, base_lat, base_lng, availability, verified, verified_at, created_at, updated_at)
  on public.service_providers to authenticated;
grant insert, update on public.service_providers to authenticated; -- RLS + guard trigger gate

grant select, insert, update on public.service_requests to authenticated; -- RLS + guard trigger gate
grant select, insert, update on public.service_offers to authenticated;   -- RLS gates
grant select on public.service_job_events to authenticated;                -- append-only; writes via DEFINER trigger
grant select on public.service_credit_ledger to authenticated;             -- backend-only writes
grant select, insert, update on public.service_credit_topups to authenticated; -- guard trigger gates transitions
grant select on public.service_vouchers to authenticated;
grant insert, update, delete on public.service_vouchers to authenticated;  -- RLS admin-gates
grant select on public.service_voucher_redemptions to authenticated;       -- inserts via RPC/GUC only

-- =============================================
-- 15. Realtime publications (the R1 silent-zero trap — required per streamed table)
-- =============================================
do $$
begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'service_requests') then
    alter publication supabase_realtime add table public.service_requests;
  end if;
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'service_offers') then
    alter publication supabase_realtime add table public.service_offers;
  end if;
  -- service_providers is DELIBERATELY NOT published (P5 finding, 2026-07-29): realtime
  -- payloads honor ROW RLS but not COLUMN grants, and the directory read policy is
  -- using(true) - publishing the table would stream live_location to ANY authenticated
  -- subscriber, bypassing the revoke-first column privacy (D8). Live tracking reads
  -- v_service_job_tracking (poll); a realtime upgrade needs a payload-safe channel
  -- (e.g. a broadcast channel fed by a DEFINER trigger), not postgres_changes here.
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'service_job_events') then
    alter publication supabase_realtime add table public.service_job_events;
  end if;
end $$;
