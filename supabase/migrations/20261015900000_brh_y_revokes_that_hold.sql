-- BRH-Y (2026-10-21): the revokes the migrations meant now hold - anon cannot run a function a migration closed to it.
--
-- Measured 2026-10-21: 39 functions a migration revoked from anon (or from PUBLIC) that anon could still execute.
-- Two mechanisms, both Supabase's defaults:
--   * Supabase grants EXECUTE to anon, authenticated and service_role EXPLICITLY on every new function, so
--     `revoke ... from public` never reaches anon's own grant (32 functions - the founder analytics, the hive
--     readiness and anomaly computes, the project budget reads and writes, inventory_restock, join_hive_by_code ...);
--   * DROP + CREATE (or a new signature) gives a function the defaults again (7 functions).
-- Every one of the 32 below checks its caller inside, so anon reached nothing through them - but each migration meant
-- the door shut, and a function that asks who is calling is one mistake away from answering anyone. Their callers are
-- signed-in pages (hive, alert-hub, asset-hub, analytics, pm-scheduler, project-manager, inventory, logbook, resume,
-- community, the founder pages) and voice-handler.js's signed-in paths.
--
-- SEVEN KEEP anon's EXECUTE, by design, and are declared in the definer-doors gate with their reason: row policies or
-- security_invoker views that anon is evaluated against call them (is_platform_admin, listing_is_mine, order_is_mine,
-- my_listing_ids, my_inquiry_ids, user_hive_worker_names, user_supervisor_hive_ids). Taken from anon, a signed-out read
-- of those tables would fail with permission denied instead of returning nothing; each answers false or empty for a
-- caller with no account.
--
-- Three of the 32 are created by migrations not yet in production (founder_feature_use, my_logbook_summary,
-- logbook_synced_machines); those files now revoke from anon themselves. Every overload is closed by name; a function
-- that does not exist yet is skipped.
--
-- ONLY anon changes. anon inherits PUBLIC's EXECUTE, so PUBLIC must go too - and a signed-in role that held EXECUTE
-- only through PUBLIC (compute_hive_readiness, which hive.html calls) would lose it with it. So each function's
-- authenticated and service_role access is read first and granted back explicitly: what a signed-in person or the
-- service role could run before, they can run after.

do $$
declare
  r record;
begin
  for r in
    select p.oid::regprocedure as sig,
           has_function_privilege('authenticated', p.oid, 'execute') as auth_had,
           has_function_privilege('service_role', p.oid, 'execute') as svc_had
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname in ('acknowledge_alert', 'compute_adoption_risk', 'compute_anomaly_signals', 'compute_hive_readiness',
                        'ensure_pm_asset_for_node', 'fetch_active_alerts', 'founder_active_hives', 'founder_anon_sessions',
                        'founder_dau_series', 'founder_feature_use', 'founder_mau', 'founder_page_heatmap',
                        'generate_project_code', 'get_hive_readiness_current', 'get_pm_ontime_delivery', 'get_project_budget',
                        'inquiry_is_from_me', 'inventory_restock', 'join_hive_by_code', 'logbook_synced_machines',
                        'my_logbook_summary', 'my_personal_history_count', 'report_community_post', 'semantic_search_kb',
                        'semantic_search_kg_facts', 'set_project_budget', 'set_worker_display_name', 'store_memory_turn',
                        'suppress_alert', 'sync_asset_identity', 'update_dialog_state', 'user_can_access_hive')
  loop
    execute format('revoke execute on function %s from public, anon', r.sig);
    if r.auth_had then
      execute format('grant execute on function %s to authenticated', r.sig);
    end if;
    if r.svc_had then
      execute format('grant execute on function %s to service_role', r.sig);
    end if;
  end loop;
end
$$;
