-- ─────────────────────────────────────────────────────────────────────────────
-- SERVICE HAILING P6: bidirectional reviews on COMPLETED hailed jobs.
-- REUSES marketplace_reviews (disposition: extend, don't duplicate): a service
-- review is a row with request_id + direction; listing_id stays NULL for them.
-- Trust design (the trust-forge lesson, applied at BIRTH this time):
--   * a service review may exist ONLY for a completed/settled request,
--     written ONLY by that request's own party, once per direction;
--   * provider rating is COMPUTED IN THE TRUTH VIEW from these legitimacy-
--     guarded rows — there is NO stored counter to forge, no trigger to trick.
-- ─────────────────────────────────────────────────────────────────────────────
alter table public.marketplace_reviews
  add column if not exists request_id uuid references public.service_requests(id) on delete cascade,
  add column if not exists direction text check (direction in ('client_to_provider','provider_to_client')),
  add column if not exists reviewer_auth_uid uuid;

create unique index if not exists marketplace_reviews_one_per_request_direction
  on public.marketplace_reviews (request_id, direction) where request_id is not null;

create or replace function public.guard_service_review()
returns trigger
language plpgsql
security definer
set search_path to 'pg_catalog', 'public'
as $$
declare
  v_req public.service_requests%rowtype;
  v_is_client boolean;
  v_is_provider boolean;
begin
  if new.request_id is null then return new; end if;  -- classic listing reviews: existing rules apply
  -- a SERVICE review is verified by construction on EVERY branch (live-caught: the admin
  -- bypass skipped the pin, leaving verified=false on an admin-authored legit review)
  new.verified_purchase := true;
  if auth.uid() is not null then new.reviewer_auth_uid := coalesce(new.reviewer_auth_uid, auth.uid()); end if;
  if auth.uid() is null
     or public.is_marketplace_admin()
     or current_setting('workhive.service_system_write', true) = 'on' then
    return new;  -- seeders/backend vetted
  end if;
  select r.* into v_req from public.service_requests r where r.id = new.request_id;
  if v_req.id is null then
    raise exception 'Not allowed: unknown service request' using errcode = 'check_violation';
  end if;
  if v_req.status not in ('completed','settled') then
    raise exception 'Not allowed: reviews open after the job is completed' using errcode = 'check_violation';
  end if;
  v_is_client := (v_req.client_auth_uid = auth.uid());
  v_is_provider := v_req.matched_provider_id in (select public.my_service_provider_ids());
  if new.direction = 'client_to_provider' and not v_is_client then
    raise exception 'Not allowed: only the client reviews the provider' using errcode = 'check_violation';
  end if;
  if new.direction = 'provider_to_client' and not v_is_provider then
    raise exception 'Not allowed: only the matched provider reviews the client' using errcode = 'check_violation';
  end if;
  if new.direction is null then
    raise exception 'Not allowed: a service review declares its direction' using errcode = 'check_violation';
  end if;
  new.reviewer_auth_uid := auth.uid();       -- attribution pinned server-side
  new.verified_purchase := true;             -- party-of-a-completed-job IS the verification
  return new;
end $$;

drop trigger if exists trg_guard_service_review on public.marketplace_reviews;
create trigger trg_guard_service_review
  before insert on public.marketplace_reviews
  for each row execute function public.guard_service_review();

-- provider rating, computed from legitimacy-guarded rows only (no stored counter).
-- (drop-and-recreate: CREATE OR REPLACE cannot insert columns before the meta trio; re-grant follows)
drop view if exists public.v_service_provider_truth;
create view public.v_service_provider_truth
with (security_invoker = false) as
select
  sp.id, sp.provider_type, sp.worker_name, sp.hive_id, sp.display_name, sp.contact,
  sp.categories, sp.service_areas, sp.base_lat, sp.base_lng, sp.availability,
  sp.verified, sp.verified_at, sp.created_at,
  coalesce(j.completed_jobs, 0) as completed_jobs,
  rv.rating_avg, coalesce(rv.rating_count, 0) as rating_count,
  1 as _source_count, sp.updated_at as _freshness_ts,
  'service_provider_truth:v2' as _canonical_version
from public.service_providers sp
left join (
  select matched_provider_id, count(*) as completed_jobs
  from public.service_requests where status in ('completed','settled')
  group by matched_provider_id
) j on j.matched_provider_id = sp.id
left join (
  select r.matched_provider_id, round(avg(mr.rating)::numeric, 2) as rating_avg, count(*) as rating_count
  from public.marketplace_reviews mr
  join public.service_requests r on r.id = mr.request_id
  where mr.direction = 'client_to_provider'
  group by r.matched_provider_id
) rv on rv.matched_provider_id = sp.id;

grant select on public.v_service_provider_truth to anon, authenticated;

insert into public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values ('service_hailing', 'rpc', 'guard_service_review', 'marketplace', 'realtime',
        '{"signature": "guard_service_review() RETURNS trigger", "side_effects": ["pins reviewer_auth_uid + verified_purchase on legit service reviews"]}'::jsonb,
        'Birth-time legitimacy guard for bidirectional service reviews: completed jobs, own party, once per direction.')
on conflict do nothing;

-- The 2026-07-19 hardening (mkt_reviews_insert: clients only insert verified_purchase=false
-- with a listing inquiry) is LISTING-review law and cannot admit service reviews, whose
-- verification IS being a party of a completed job (guard-pinned server-side). A second
-- permissive INSERT policy opens exactly that class; permissive policies OR together, and
-- trg_guard_service_review carries the full legitimacy (party, completed, direction, pin).
drop policy if exists service_review_intake on public.marketplace_reviews;
create policy service_review_intake on public.marketplace_reviews
  for insert to authenticated
  with check (request_id is not null);
