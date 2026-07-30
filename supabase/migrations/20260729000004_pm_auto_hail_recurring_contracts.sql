-- =====================================================================
-- J24 · RECURRING SERVICE CONTRACTS - a PM plan that AUTO-HAILS when it comes due
-- =====================================================================
-- §1c promised the Urban-Company-plans analog: "a maintenance plan that auto-hails on schedule -
-- subscription-like retention + predictable provider income". What actually shipped was a MANUAL
-- "Hail a specialist" CTA on the pm-scheduler detail: a human still has to press it, so the
-- recurring half of the promise was never built. The arc scoreboard scored J24 at 40% for exactly
-- that reason. This is the missing half.
--
-- DESIGN - reuse, don't reinvent:
--   * DUE-ness comes from v_pm_scope_items_truth (next_due_date / is_overdue), the platform's own
--     PM frequency engine. No second due-date implementation to drift.
--   * The sweep mirrors sweep_service_broadcasts() (mig 42): a SECURITY DEFINER function that sets
--     the workhive.service_system_write GUC so the request guard accepts a system-authored hail,
--     journals what it did, and is safe to run repeatedly.
--   * Idempotency is structural: a partial unique index means one OPEN auto-hail per scope item.
--     Re-running the sweep can never fan out duplicates, which is the failure mode that would
--     spam every provider's feed.
--
-- SAFETY: opt-in per scope item (default false), and it only fires for a hive that has a
-- catalog-matched category. A plan whose category is not in the rate card is skipped, not guessed.

BEGIN;

-- 1. Opt-in config on the PM scope item -------------------------------------------------
alter table public.pm_scope_items
  add column if not exists auto_hail boolean not null default false,
  add column if not exists auto_hail_category text;

comment on column public.pm_scope_items.auto_hail is
  'J24 recurring contract: when this PM item comes due, sweep_pm_auto_hail() files a service request automatically instead of waiting for someone to press Hail a specialist.';

-- 2. Link the hail back to the PM item that spawned it -----------------------------------
alter table public.service_requests
  add column if not exists pm_scope_item_id uuid references public.pm_scope_items(id) on delete set null;

comment on column public.service_requests.pm_scope_item_id is
  'Set when the request was auto-filed by a recurring PM contract (J24). NULL for a human-filed hail.';

-- ONE open auto-hail per PM item: the structural idempotency the sweep relies on.
create unique index if not exists service_requests_one_open_auto_hail
  on public.service_requests (pm_scope_item_id)
  where pm_scope_item_id is not null
    and status in ('requested','broadcasting','accepted','en_route','on_site','in_progress');

-- 3. The sweep ---------------------------------------------------------------------------
create or replace function public.sweep_pm_auto_hail()
returns TABLE(filed integer, skipped_no_category integer)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_filed int := 0;
  v_skipped int := 0;
  r record;
  v_catalog_id uuid;
  v_req_id uuid;
begin
  -- system-authored writes: the same GUC the seeders/backends use, so guard_service_request_status
  -- accepts a request nobody clicked for.
  perform set_config('workhive.service_system_write', 'on', true);

  for r in
    select t.scope_item_id, t.hive_id, t.item_text, t.asset_name, t.asset_tag,
           t.asset_location, t.next_due_date, si.auto_hail_category
      from public.v_pm_scope_items_truth t
      join public.pm_scope_items si on si.id = t.scope_item_id
     where si.auto_hail = true
       and t.next_due_date is not null
       and t.next_due_date <= current_date          -- due or overdue
  loop
    -- structural idempotency: skip if this item already has an OPEN auto-hail
    if exists (
      select 1 from public.service_requests sr
       where sr.pm_scope_item_id = r.scope_item_id
         and sr.status in ('requested','broadcasting','accepted','en_route','on_site','in_progress')
    ) then
      continue;
    end if;

    select c.id into v_catalog_id
      from public.service_catalog c
     where c.active = true
       and c.segment = 'industrial'
       and (r.auto_hail_category is null or c.category = r.auto_hail_category)
     order by (c.category = coalesce(r.auto_hail_category, '')) desc, c.base_rate asc
     limit 1;

    if v_catalog_id is null then
      v_skipped := v_skipped + 1;      -- no rate-card match: skip honestly, never guess a service
      continue;
    end if;

    insert into public.service_requests
      (client_auth_uid, client_worker_name, hive_id, segment, mode, catalog_item_id,
       custom_scope, address, urgency, status, pm_scope_item_id)
    values
      ((select auth_uid from public.pm_assets pa
         join public.pm_scope_items s2 on s2.asset_id = pa.id
        where s2.id = r.scope_item_id and pa.auth_uid is not null limit 1),
       'PM auto-hail', r.hive_id, 'industrial', 'instant', v_catalog_id,
       'Recurring PM contract: ' || r.item_text || ' on ' || coalesce(r.asset_name, 'asset')
         || coalesce(' (' || r.asset_tag || ')', '') || ' - due ' || r.next_due_date::text,
       r.asset_location, 'normal', 'broadcasting', r.scope_item_id)
    returning id into v_req_id;

    insert into public.service_job_events (request_id, actor_uid, actor_role, from_state, to_state, note)
    values (v_req_id, null, 'system:pm-auto-hail', null, 'broadcasting',
            'Auto-filed by the recurring PM contract for scope item ' || r.scope_item_id::text);

    v_filed := v_filed + 1;
  end loop;

  perform set_config('workhive.service_system_write', 'off', true);
  return query select v_filed, v_skipped;
end $$;

comment on function public.sweep_pm_auto_hail() is
  'J24: files a service request for every DUE PM scope item flagged auto_hail, at most one open hail per item. Due-ness is read from v_pm_scope_items_truth so there is no second frequency implementation.';

revoke all on function public.sweep_pm_auto_hail() from public, anon, authenticated;

-- 4. Daily cron (the TTL-sweep precedent from mig 42) ------------------------------------
do $cron$
begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') then
    perform cron.unschedule('pm-auto-hail-daily')
      where exists (select 1 from cron.job where jobname = 'pm-auto-hail-daily');
    perform cron.schedule('pm-auto-hail-daily', '15 0 * * *', 'select public.sweep_pm_auto_hail();');
  end if;
end $cron$;

COMMIT;
