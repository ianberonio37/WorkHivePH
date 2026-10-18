-- D3 (2026-10-16): a hive's deleted-items window can actually be set - by its supervisors, and never below 30 days.
--
-- plant-connections' Data retention card says "Adjustable by supervisor", and the sensor-gateway learn article
-- promises "a data-retention policy you can set". Neither was true: no hive had a hive_retention_config row, the
-- table's INSERT policy is `false`, and no page writes it - so a supervisor's UPDATE matched nothing and every hive
-- ran on defaults it could not change.
--
-- ONLY the deleted-items window is offered, because it is the only one of the table's three windows anything
-- enforces: hard_delete_expired_soft_deletes reads soft_delete_retention_days every day. audit_retention_days and
-- ai_telemetry_retention_days are read by nothing - the audit trail is never purged, and AI cost records are kept
-- 365 days platform-wide - so a control for either would change nothing while saying it had. The window is floored
-- at 30 days because 30-day recoverable is the platform's promise (Ian, 2026-10-16): a hive may keep deleted items
-- LONGER, never shorter. The table's own CHECK says the same, so the floor holds for a direct write too.
-- Forward-only; idempotent.

alter table public.hive_retention_config
  drop constraint if exists hive_retention_config_soft_delete_retention_days_check;
alter table public.hive_retention_config
  add constraint hive_retention_config_soft_delete_retention_days_check
  check (soft_delete_retention_days is null or (soft_delete_retention_days between 30 and 3650));

-- an earlier draft of this migration (never deployed) took all three windows
drop function if exists public.set_hive_retention(uuid, integer, integer, integer);

create or replace function public.set_hive_retention(
  p_hive_id          uuid,
  p_soft_delete_days integer
)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_name text;
begin
  if auth.uid() is null then
    raise exception 'Sign in to change how long deleted items are kept.' using errcode = '42501';
  end if;
  select hm.worker_name into v_name
    from public.hive_members hm
   where hm.hive_id = p_hive_id and hm.auth_uid = auth.uid() and hm.status = 'active' and hm.role = 'supervisor'
   limit 1;
  if v_name is null then
    raise exception 'Only a supervisor of this hive can change how long it keeps deleted items.' using errcode = '42501';
  end if;
  if p_soft_delete_days is null or p_soft_delete_days not between 30 and 3650 then
    raise exception 'Deleted items must be kept between 30 and 3650 days - 30 is the shortest, so anything deleted stays recoverable for at least that long.'
      using errcode = 'P0001';
  end if;

  insert into public.hive_retention_config (hive_id, soft_delete_retention_days, updated_at, updated_by)
  values (p_hive_id, p_soft_delete_days, now(), v_name)
  on conflict (hive_id) do update
     set soft_delete_retention_days = excluded.soft_delete_retention_days,
         updated_at                 = now(),
         updated_by                 = v_name;

  insert into public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  values (p_hive_id, v_name, 'set_retention', 'hive_retention_config', p_hive_id::text, 'Deleted items window',
          jsonb_build_object('soft_delete_days', p_soft_delete_days, 'source', 'set_hive_retention'));

  return jsonb_build_object('hive_id', p_hive_id, 'soft_delete_retention_days', p_soft_delete_days, 'updated_by', v_name);
end;
$$;

comment on function public.set_hive_retention(uuid, integer) is
  'D3: a supervisor sets how long their hive keeps deleted items (30-3650 days, never below the 30-day promise) '
  'before the daily purge removes them. Audited as set_retention.';

revoke all on function public.set_hive_retention(uuid, integer) from public, anon;
grant execute on function public.set_hive_retention(uuid, integer) to authenticated;
