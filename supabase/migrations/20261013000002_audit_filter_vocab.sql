-- 20261013000002 - THE FILTER LIST DOWNLOADED THE WHOLE AUDIT TRAIL (critique of audit-log.html, 2026-10-13).
--
-- audit-log.html builds its actor / action / target dropdowns from the COMPLETE trail (T64, 2026-08-26: a list built from
-- the feed's capped 500 rows hid people who had acted, which on a compliance surface reads as "they did nothing"). The
-- completeness was right; the method was not: it paged through hive_audit_log 500 rows at a time in the browser. Measured
-- on the local stack's Baguio hive: 28,609 rows, so every open of the page made 58 sequential requests and moved all
-- 28,609 rows to the supervisor's phone to produce 7 actors, 29 actions and 14 target types - growing with every day the
-- hive runs, and on plant 4G the heaviest thing the page does.
--
-- The same answer, computed where the rows live: DISTINCT over both trails (hive_audit_log and the voice half,
-- ai_audit_log), one request. SECURITY INVOKER, so the tables' own RLS decides who may read them - exactly what the paged
-- reads were subject to, nothing more. The page keeps its paged read as the fallback if this call fails.

create or replace function public.audit_filter_vocab(p_hive_id uuid)
returns jsonb
language sql
stable
security invoker
set search_path to 'public'
as $$
  select jsonb_build_object(
    'actors', coalesce((select jsonb_agg(v) from (
        select actor as v from hive_audit_log where hive_id = p_hive_id and actor is not null and actor <> ''
        union
        select worker_name from ai_audit_log where hive_id = p_hive_id and worker_name is not null and worker_name <> '') s),
      '[]'::jsonb),
    'actions', coalesce((select jsonb_agg(v) from (
        select action as v from hive_audit_log where hive_id = p_hive_id and action is not null and action <> ''
        union
        select event from ai_audit_log where hive_id = p_hive_id and event is not null and event <> '') s),
      '[]'::jsonb),
    'targets', coalesce((select jsonb_agg(v) from (
        select target_type as v from hive_audit_log where hive_id = p_hive_id and target_type is not null and target_type <> ''
        union
        select 'voice' where exists (select 1 from ai_audit_log where hive_id = p_hive_id)) s),
      '[]'::jsonb)
  );
$$;

revoke all on function public.audit_filter_vocab(uuid) from public, anon;
grant execute on function public.audit_filter_vocab(uuid) to authenticated;

comment on function public.audit_filter_vocab(uuid) is
  'The audit log''s filter vocabulary (distinct actors, actions, target types over both trails) in one request, under the '
  'caller''s RLS. Replaced a client page-through of the whole trail. See migration 20261013000002.';
