-- SERVICE HAILING ENGINE (arc P2 — SERVICE_HAILING_ROADMAP.md §1 Engine)
-- Canonical views (the ONLY read path for Dashboard pages) + the dispatch RPCs.
-- House pattern: views are WITH (security_invoker = false) — owner's rights — so each
-- view RE-ASSERTS its own boundary in WHERE (the DEFINER-is-RLS-exempt lesson); RPCs are
-- SECURITY DEFINER that announce themselves to the state-machine guard via the
-- transaction-local `workhive.service_system_write` GUC (set_config(..., true)).
-- R1 defect fixed here: accept is a STATUS-GUARDED ATOMIC UPDATE (0 rows = lost race,
-- surfaced honestly) — not the reference's select-then-insert TOCTOU.

-- =============================================
-- 1. v_service_provider_truth — the public directory (curated columns ONLY)
-- =============================================
create or replace view public.v_service_provider_truth
with (security_invoker = false) as
select
  sp.id,
  sp.provider_type,
  sp.worker_name,
  sp.hive_id,
  sp.display_name,
  sp.contact,
  sp.categories,
  sp.service_areas,
  sp.base_lat,
  sp.base_lng,
  sp.availability,
  sp.verified,
  sp.verified_at,
  sp.created_at,
  coalesce(j.completed_jobs, 0) as completed_jobs,
  -- canonical truth-view signal-trust contract
  1 as _source_count,
  sp.updated_at as _freshness_ts,
  'service_provider_truth:v1' as _canonical_version
from public.service_providers sp
left join (
  select matched_provider_id, count(*) as completed_jobs
  from public.service_requests
  where status in ('completed','settled')
  group by matched_provider_id
) j on j.matched_provider_id = sp.id;
comment on view public.v_service_provider_truth is
  'Provider directory truth: curated public columns + verified completed-job count. live_location is deliberately ABSENT (privacy: v_service_job_tracking only).';

-- =============================================
-- 2. v_service_request_truth — a party''s own requests (re-asserted boundary)
-- =============================================
create or replace view public.v_service_request_truth
with (security_invoker = false) as
select
  r.id, r.client_auth_uid, r.client_worker_name, r.hive_id, r.segment, r.mode,
  r.catalog_item_id, c.name as catalog_name, c.category as catalog_category,
  c.unit as catalog_unit, c.base_rate as catalog_rate,
  r.custom_scope, r.address, r.urgency, r.budget, r.status,
  r.matched_provider_id, sp.display_name as provider_name, sp.contact as provider_contact,
  sp.availability as provider_availability,
  r.broadcast_radius_m, r.offer_ttl_expires_at,
  r.accepted_at, r.en_route_at, r.on_site_at, r.in_progress_at,
  r.completed_at, r.settled_at, r.cancelled_at, r.created_at, r.updated_at,
  (select count(*) from public.service_offers o
    where o.request_id = r.id and o.status = 'pending') as pending_offers,
  -- canonical truth-view signal-trust contract
  1 as _source_count,
  r.updated_at as _freshness_ts,
  'service_request_truth:v1' as _canonical_version
from public.service_requests r
left join public.service_catalog c on c.id = r.catalog_item_id
left join public.service_providers sp on sp.id = r.matched_provider_id
where r.client_auth_uid = auth.uid()
   or (r.hive_id is not null and r.hive_id in (
         select hm.hive_id from public.hive_members hm
         where hm.auth_uid = auth.uid() and hm.status = 'active'))
   or r.matched_provider_id in (select public.my_service_provider_ids());
comment on view public.v_service_request_truth is
  'Request truth for the request''s parties (client, their hive, matched provider) — boundary re-asserted in the view (DEFINER view = RLS-exempt).';

-- =============================================
-- 3. v_service_open_broadcasts — a provider''s live feed
-- =============================================
create or replace view public.v_service_open_broadcasts
with (security_invoker = false) as
select
  r.id as request_id,
  r.segment, r.mode, r.urgency, r.budget,
  r.catalog_item_id, c.name as catalog_name, c.category as catalog_category,
  c.unit as catalog_unit, c.base_rate as catalog_rate,
  r.custom_scope,
  split_part(coalesce(r.address, ''), ',', 1) as area_hint, -- coarse location pre-accept; exact address on match
  r.broadcast_radius_m, r.offer_ttl_expires_at, r.created_at,
  sp.id as my_provider_id,
  round((extensions.st_distance(r.location, sp.base_location) / 1000.0)::numeric, 1) as distance_km,
  exists (select 1 from public.service_offers o
           where o.request_id = r.id and o.provider_id = sp.id) as already_responded
from public.service_requests r
left join public.service_catalog c on c.id = r.catalog_item_id
join public.service_providers sp on sp.id in (select public.my_service_provider_ids())
where r.status = 'broadcasting'
  and r.client_auth_uid is distinct from auth.uid() -- never your own hail
  and (r.location is null or sp.base_location is null
       or extensions.st_dwithin(r.location, sp.base_location, r.broadcast_radius_m * 4)) -- feed radius = 4x broadcast (provider may still see + quote)
  and (r.catalog_item_id is null or c.category = any (sp.categories));
comment on view public.v_service_open_broadcasts is
  'A provider''s open-broadcast feed: broadcasting requests in category+radius scope, coarse area only (exact address revealed on match). Boundary = caller''s own provider rows.';

-- =============================================
-- 4. v_service_job_tracking — live location, ACTIVE jobs only (the privacy door)
-- =============================================
create or replace view public.v_service_job_tracking
with (security_invoker = false) as
select
  r.id as request_id,
  r.status,
  sp.id as provider_id,
  sp.display_name as provider_name,
  extensions.st_y(sp.live_location::extensions.geometry) as live_lat,
  extensions.st_x(sp.live_location::extensions.geometry) as live_lng,
  extensions.st_y(r.location::extensions.geometry) as request_lat,
  extensions.st_x(r.location::extensions.geometry) as request_lng,
  sp.updated_at as location_updated_at
from public.service_requests r
join public.service_providers sp on sp.id = r.matched_provider_id
where r.status in ('en_route','on_site','in_progress')
  and (r.client_auth_uid = auth.uid()
       or (r.hive_id is not null and r.hive_id in (
             select hm.hive_id from public.hive_members hm
             where hm.auth_uid = auth.uid() and hm.status = 'active'))
       or sp.id in (select public.my_service_provider_ids()));
comment on view public.v_service_job_tracking is
  'The ONLY read path to a provider''s live_location — and only while a job is ACTIVE (en_route/on_site/in_progress) and only to that job''s parties. Privacy-by-default (D8).';

-- =============================================
-- 5. accept_service_request — atomic first-accept-wins (fixes the reference TOCTOU)
-- =============================================
create or replace function public.accept_service_request(p_request_id uuid, p_eta_minutes integer default null)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public', 'extensions'
as $$
declare
  v_provider public.service_providers%rowtype;
  v_req public.service_requests%rowtype;
  v_won boolean;
begin
  -- caller must own an ONLINE provider identity
  select sp.* into v_provider
  from public.service_providers sp
  where sp.id in (select public.my_service_provider_ids())
    and sp.availability = 'online'
  order by sp.verified desc, sp.created_at
  limit 1;
  if v_provider.id is null then
    return jsonb_build_object('accepted', false, 'reason', 'no_online_provider_identity');
  end if;

  select r.* into v_req from public.service_requests r where r.id = p_request_id;
  if v_req.id is null then
    return jsonb_build_object('accepted', false, 'reason', 'not_found');
  end if;
  if v_req.client_auth_uid = auth.uid() then
    return jsonb_build_object('accepted', false, 'reason', 'own_request');
  end if;
  -- eligibility: category overlap (catalog requests) + radius when both points exist
  if v_req.catalog_item_id is not null and not exists (
    select 1 from public.service_catalog c
    where c.id = v_req.catalog_item_id
      and (c.category = any (v_provider.categories))
  ) then
    return jsonb_build_object('accepted', false, 'reason', 'category_mismatch');
  end if;
  if v_req.location is not null and v_provider.base_location is not null
     and not st_dwithin(v_req.location, v_provider.base_location, v_req.broadcast_radius_m * 4) then
    return jsonb_build_object('accepted', false, 'reason', 'out_of_radius');
  end if;

  -- P6b (mig 48 adjunct): a provider in commission DEBT cannot accept until they top up
  if public.provider_credit_balance(v_provider.id) < 0 then
    return jsonb_build_object('accepted', false, 'reason', 'insufficient_credits',
                              'balance', public.provider_credit_balance(v_provider.id));
  end if;

  -- announce to the state-machine guard for THIS transaction only
  perform set_config('workhive.service_system_write', 'on', true);

  -- ★ the atomic race: exactly one caller flips broadcasting -> accepted
  update public.service_requests
     set status = 'accepted',
         matched_provider_id = v_provider.id,
         accepted_at = now(),
         updated_at = now()
   where id = p_request_id
     and status = 'broadcasting';
  v_won := found;

  if not v_won then
    -- 0 rows = lost the race (or state moved) — surfaced honestly, never silently
    return jsonb_build_object('accepted', false, 'reason', 'lost_race_or_closed',
                              'status', (select status from public.service_requests where id = p_request_id));
  end if;

  -- record the winning accept; expire other pending instant-accepts
  insert into public.service_offers (request_id, provider_id, kind, eta_minutes, status)
  values (p_request_id, v_provider.id, 'accept', p_eta_minutes, 'selected')
  on conflict (request_id, provider_id)
  do update set kind = 'accept', status = 'selected', eta_minutes = excluded.eta_minutes, updated_at = now();
  update public.service_offers
     set status = 'expired', updated_at = now()
   where request_id = p_request_id and provider_id <> v_provider.id and status = 'pending' and kind = 'accept';

  -- availability follows the job (mirrors the sync trigger for direct RPC path)
  update public.service_providers set availability = 'on_job', updated_at = now()
   where id = v_provider.id and availability = 'online';

  return jsonb_build_object('accepted', true, 'request_id', p_request_id, 'provider_id', v_provider.id);
end $$;
grant execute on function public.accept_service_request(uuid, integer) to authenticated;

-- =============================================
-- 6. submit_service_quote — quote-mode response
-- =============================================
create or replace function public.submit_service_quote(
  p_request_id uuid, p_price numeric, p_eta_minutes integer default null, p_message text default null)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_provider_id uuid;
  v_req public.service_requests%rowtype;
begin
  select sp.id into v_provider_id
  from public.service_providers sp
  where sp.id in (select public.my_service_provider_ids())
  order by sp.verified desc, sp.created_at limit 1;
  if v_provider_id is null then
    return jsonb_build_object('quoted', false, 'reason', 'no_provider_identity');
  end if;
  select r.* into v_req from public.service_requests r where r.id = p_request_id;
  if v_req.id is null or v_req.status <> 'broadcasting' then
    return jsonb_build_object('quoted', false, 'reason', 'not_open');
  end if;
  if v_req.client_auth_uid = auth.uid() then
    return jsonb_build_object('quoted', false, 'reason', 'own_request');
  end if;
  if p_price is null or p_price < 0 then
    return jsonb_build_object('quoted', false, 'reason', 'bad_price');
  end if;
  insert into public.service_offers (request_id, provider_id, kind, price, eta_minutes, message)
  values (p_request_id, v_provider_id, 'quote', p_price, p_eta_minutes, p_message)
  on conflict (request_id, provider_id)
  do update set kind = 'quote', price = excluded.price, eta_minutes = excluded.eta_minutes,
                message = excluded.message, status = 'pending', updated_at = now();
  return jsonb_build_object('quoted', true, 'request_id', p_request_id, 'provider_id', v_provider_id);
end $$;
grant execute on function public.submit_service_quote(uuid, numeric, integer, text) to authenticated;

-- =============================================
-- 7. select_quote — the client picks a quote (atomic match)
-- =============================================
create or replace function public.select_quote(p_offer_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_offer public.service_offers%rowtype;
  v_req public.service_requests%rowtype;
begin
  select o.* into v_offer from public.service_offers o where o.id = p_offer_id;
  if v_offer.id is null or v_offer.kind <> 'quote' or v_offer.status <> 'pending' then
    return jsonb_build_object('selected', false, 'reason', 'offer_not_open');
  end if;
  select r.* into v_req from public.service_requests r where r.id = v_offer.request_id;
  if v_req.client_auth_uid is distinct from auth.uid() then
    return jsonb_build_object('selected', false, 'reason', 'not_your_request');
  end if;

  perform set_config('workhive.service_system_write', 'on', true);

  update public.service_requests
     set status = 'accepted', matched_provider_id = v_offer.provider_id,
         accepted_at = now(), updated_at = now()
   where id = v_offer.request_id and status = 'broadcasting';
  if not found then
    return jsonb_build_object('selected', false, 'reason', 'request_closed',
                              'status', (select status from public.service_requests where id = v_offer.request_id));
  end if;

  update public.service_offers set status = 'selected', updated_at = now() where id = p_offer_id;
  update public.service_offers set status = 'declined', updated_at = now()
   where request_id = v_offer.request_id and id <> p_offer_id and status = 'pending';
  update public.service_providers set availability = 'on_job', updated_at = now()
   where id = v_offer.provider_id and availability = 'online';

  return jsonb_build_object('selected', true, 'request_id', v_offer.request_id, 'provider_id', v_offer.provider_id);
end $$;
grant execute on function public.select_quote(uuid) to authenticated;

-- =============================================
-- 8. Grants on the views
-- =============================================
grant select on public.v_service_provider_truth  to anon, authenticated;
grant select on public.v_service_request_truth   to authenticated;
grant select on public.v_service_open_broadcasts to authenticated;
grant select on public.v_service_job_tracking    to authenticated;
