-- BRH-V (2026-10-21): a hive's KPIs are read by its own members, and by nobody else.
--
-- v_kpi_truth is a MATERIALIZED view (MTBF, MTTR, downtime and failure counts per machine, every hive, refreshed hourly).
-- Row-level security cannot apply to a materialized view, so its SELECT grant was the only rule: production served it
-- to anon and to every signed-in member (Supabase's advisor, materialized_view_in_api, emailed 2026-10-20). anon lost it
-- in 20261015500000; a member of one hive could still read another hive's figures by asking for that hive's id.
--
-- Its one client reader is voice-handler.js, which asks for the person's own hive. It now reads through hive_kpis(),
-- which returns a hive's rows only when the caller can access that hive (user_can_access_hive, the platform's membership
-- rule), and the view itself is granted to the service role alone. refresh_v_kpi_truth() and the edge functions read it
-- as its owner or the service role, so nothing else changes.

create or replace function public.hive_kpis(p_hive_id uuid)
returns setof public.v_kpi_truth
language sql
stable
security definer
set search_path = ''
as $$
  select k.*
  from public.v_kpi_truth k
  where k.hive_id = p_hive_id
    and public.user_can_access_hive(p_hive_id);
$$;

revoke all on function public.hive_kpis(uuid) from public, anon, authenticated;
grant execute on function public.hive_kpis(uuid) to authenticated, service_role;

revoke all on public.v_kpi_truth from anon, authenticated;
grant select on public.v_kpi_truth to service_role;
