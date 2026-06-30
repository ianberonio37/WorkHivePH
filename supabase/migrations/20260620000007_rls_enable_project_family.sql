-- Arc G G1 — enable RLS on the project_* family (6 non-RLS hive-scoped tables).
--
-- projects, project_items, project_links, project_roles, project_change_orders, project_progress_logs all
-- carry a direct hive_id but had RLS DISABLED — so anon/authenticated could read+write every hive's project
-- management data directly via PostgREST. All are read only by authenticated app pages (project-manager,
-- pm-scheduler, logbook, project-report); guest access was removed by the auth migration. Enable RLS with a
-- uniform hive-member-scoped policy (reuses public.user_hive_ids(); service_role bypasses for edge/cron).
--
-- VERIFIED LIVE (ROLLBACK'd, 2026-06-20): with these policies, a member reads own-hive rows
-- (projects 4 / project_items 30 / project_links 4 / project_progress_logs 17) + cross-hive 0 + anon 0.
-- (project_roles / project_change_orders had no seed data but use the identical direct-hive_id pattern.)

do $mig$
declare t text;
begin
  foreach t in array array['projects','project_items','project_links','project_roles',
                           'project_change_orders','project_progress_logs'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists %I on public.%I', t || '_hive_rw', t);  -- idempotent re-run
    execute format($p$create policy %I on public.%I for all
      using      (auth.uid() is not null and hive_id in (select public.user_hive_ids()))
      with check (auth.uid() is not null and hive_id in (select public.user_hive_ids()))$p$,
      t || '_hive_rw', t);
  end loop;
end $mig$;
