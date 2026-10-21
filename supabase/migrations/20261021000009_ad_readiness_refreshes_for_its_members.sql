-- BRH 9 AD (2026-10-21): the hive board's readiness refreshes again - for the hive's own members, at most once a day.
--
-- Measured: of the 87 functions pages call, production refuses exactly one to a signed-in member -
-- compute_hive_readiness(uuid). 20260619000000 revoked it from authenticated to close a real cross-tenant write (it had
-- no membership gate), on two premises its own comment states: "No browser/edge code invokes compute_hive_readiness
-- directly" and "it runs server-side (cron / service-role)". Both were false. hive.html calls it whenever the snapshot
-- is missing or over 24 hours old, and no scheduled job or edge function runs it. So since 2026-06-19 nothing could
-- refresh a hive's readiness: every board load past a day made a refused call and showed the old snapshot, and a new
-- hive's board said there was none.
--
-- refresh_hive_readiness is the browser's door to the same computation, with the gate the original lacked:
--   - the caller must be able to access the hive (user_can_access_hive - the gate get_hive_readiness_current uses);
--   - it computes only when the newest snapshot is missing or older than 24 hours, so calling it again cannot be used
--     to write repeatedly (compute_hive_readiness upserts one row per hive per day);
--   - it returns the newest snapshot, so the page needs no second read.
-- compute_hive_readiness itself stays closed to anon and authenticated, as 20260619000000 meant.

create or replace function public.refresh_hive_readiness(p_hive_id uuid)
returns public.hive_readiness
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  r public.hive_readiness;
begin
  if p_hive_id is null or not public.user_can_access_hive(p_hive_id) then
    raise exception 'not a member of this hive' using errcode = '42501';
  end if;
  select * into r from public.hive_readiness
   where hive_id = p_hive_id
   order by snapshot_date desc, computed_at desc
   limit 1;
  if r.hive_id is null or r.computed_at is null or r.computed_at < now() - interval '24 hours' then
    perform public.compute_hive_readiness(p_hive_id);
    select * into r from public.hive_readiness
     where hive_id = p_hive_id
     order by snapshot_date desc, computed_at desc
     limit 1;
  end if;
  return r;
end;
$$;

revoke all on function public.refresh_hive_readiness(uuid) from public, anon;
grant execute on function public.refresh_hive_readiness(uuid) to authenticated, service_role;

comment on function public.refresh_hive_readiness(uuid) is
  'The hive board''s readiness, recomputed when the newest snapshot is missing or over 24 hours old - for a member of '
  'the hive only (user_can_access_hive). compute_hive_readiness stays service-role only (20260619000000).';
