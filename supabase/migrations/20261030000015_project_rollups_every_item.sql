-- project-manager.html computed each project card's progress, done count and late items in the browser, from the hive's
-- scope items read 500 at a time per hundred projects. A cap on a sum is a wrong number: past 500 items in a chunk (about
-- fifty projects of ten steps - a year of a hive of thirty, Wave HS L4, 2026-10-30) a card read the share of its items
-- that happened to arrive, and a late step outside them was never counted. The rollup is a set of sums, so it is summed
-- where every item is.
--
-- The figures are the page's own: progress weighted by planned hours (an item with none weighs 1), the basis named only
-- when some item carries hours, and a step late when it is not done and its planned end is before the hive's today
-- (Asia/Manila, the day the page compares against). SECURITY INVOKER: the reader's RLS decides which items count.
create or replace function public.project_rollups(p_hive uuid)
returns table (project_id uuid, items_total integer, items_done integer, pct_exact numeric, hours_basis boolean,
               late_items integer)
language sql
stable
security invoker
set search_path = public
as $$
  select i.project_id,
         count(*)::integer,
         count(*) filter (where i.status = 'done')::integer,
         sum(coalesce(i.pct_complete, 0) * coalesce(nullif(i.estimated_hours, 0), 1))
           / nullif(sum(coalesce(nullif(i.estimated_hours, 0), 1)), 0),
         bool_or(coalesce(i.estimated_hours, 0) <> 0),
         count(*) filter (where i.planned_end is not null and i.status is distinct from 'done'
                            and i.planned_end < (now() at time zone 'Asia/Manila')::date)::integer
  from public.v_project_items_truth i
  where i.hive_id = p_hive
  group by i.project_id;
$$;

revoke all on function public.project_rollups(uuid) from public, anon;
grant execute on function public.project_rollups(uuid) to authenticated;
