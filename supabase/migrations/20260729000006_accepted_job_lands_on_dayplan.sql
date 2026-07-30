-- =====================================================================
-- J27 · an ACCEPTED job LANDS on the provider's day plan
-- =====================================================================
-- §1c promised: "dayplanner (schedule_items) -> Provider availability calendar: accepted jobs land
-- on the provider's day plan." What shipped was a manual "+ Add to my day" deep-link on the job
-- card - the provider still had to file their own schedule entry, so the calendar was only as good
-- as their discipline. The scoreboard scored J27 at 40% for exactly that.
--
-- DESIGN: an AFTER trigger on the accept transition, not client code, so the entry appears no
-- matter which path accepted the job (the RPC, an admin move, a future auto-dispatch). Reuses
-- schedule_items' own source_kind/source_ref columns, which exist precisely so a row can be traced
-- back to what produced it - no new table, no parallel calendar.
--
-- IDEMPOTENT by construction: the schedule_items PK is TEXT, so the row id is derived from the
-- request id ('svc-' || request_id). Re-accepting or replaying can only ever upsert the same row.
-- A provider who deletes it is not fought - a re-accept is the only thing that re-creates it.

BEGIN;

create or replace function public.land_accepted_job_on_dayplan()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_provider public.service_providers%rowtype;
  v_title    text;
  v_worker   text;
  v_auth     uuid;
begin
  -- only the moment a job becomes ACCEPTED
  if new.status <> 'accepted' or coalesce(old.status, '') = 'accepted' then
    return new;
  end if;
  if new.matched_provider_id is null then
    return new;
  end if;

  select sp.* into v_provider from public.service_providers sp where sp.id = new.matched_provider_id;
  if v_provider.id is null then
    return new;
  end if;

  -- A freelancer schedules under their own name. A hive COMPANY has no single worker, so the
  -- entry lands on the dispatcher who owns the provider record when there is one; otherwise the
  -- company keeps no personal calendar and we simply skip - better than inventing an owner.
  v_worker := coalesce(v_provider.worker_name, '');
  v_auth   := v_provider.auth_uid;
  if v_worker = '' then
    return new;
  end if;

  select coalesce(c.name, left(coalesce(new.custom_scope, 'Service job'), 60))
    into v_title
    from public.service_catalog c where c.id = new.catalog_item_id;
  v_title := coalesce(v_title, left(coalesce(new.custom_scope, 'Service job'), 60));

  insert into public.schedule_items
    (id, worker_name, auth_uid, title, date, category, notes, item_status, source_kind, source_ref)
  values
    ('svc-' || new.id::text, v_worker, v_auth,
     'Service job: ' || v_title,
     to_char(now() at time zone 'Asia/Manila', 'YYYY-MM-DD'),
     'CM',
     'Hailed job' || coalesce(' at ' || new.address, '') ||
       coalesce(' for ' || new.client_worker_name, '') ||
       '. Track it from the provider console.',
     'planned', 'service_request', new.id::text)
  on conflict (id) do update
    set title = excluded.title, notes = excluded.notes, date = excluded.date;

  return new;
end $$;

comment on function public.land_accepted_job_on_dayplan() is
  'J27: when a hail is ACCEPTED, the provider gets a schedule_items entry (id svc-<request_id>, source_kind service_request) so the day plan reflects committed work automatically instead of relying on the provider to add it.';

drop trigger if exists trg_land_accepted_job_on_dayplan on public.service_requests;
create trigger trg_land_accepted_job_on_dayplan
  after update on public.service_requests
  for each row execute function public.land_accepted_job_on_dayplan();

COMMIT;
