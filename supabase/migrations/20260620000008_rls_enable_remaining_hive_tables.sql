-- Arc G G1 — enable RLS on the remaining 16 non-RLS hive-scoped tables (auth-migration enforcement, final).
--
-- These all carry a direct hive_id but had RLS DISABLED (anon/authenticated could read+write any hive's
-- rows via PostgREST): asset_risk_scores, bom_knowledge, calc_knowledge, cmms_audit_log,
-- conversation_analytics, external_sync, failure_signature_alerts, hive_analytics_cache, hive_audit_log,
-- hive_benchmarks, integration_configs, offline_snapshot_cache, parts_staged_reservations,
-- parts_staging_recommendations, project_knowledge, tts_quality_log.
--
-- All have ZERO truly-public-page readers (hive_audit_log is read only by authenticated app pages:
-- alert-hub/asset-hub/audit-log/community/founder-console/hive/inventory/logbook/marketplace-admin/-seller;
-- the knowledge tables carry hive_id so they are per-hive, not the global KB). Guest access was removed by
-- the auth migration. Uniform hive-member-scoped policy (reuses public.user_hive_ids(); service_role bypasses).
--
-- VERIFIED LIVE (ROLLBACK'd, 2026-06-20): member reads own-hive rows (asset_risk_scores 35 / hive_audit_log 11
-- / failure_signature_alerts 43 / cmms_audit_log 11 / hive_benchmarks 5 / integration_configs 1 / …) +
-- cross-hive 0 + anon 0, no recursion. Drives validate_rls_coverage 16 -> 0 (only the 4 by-design marketplace
-- tables remain non-RLS). orphan-RLS stays 0.

do $mig$
declare t text;
begin
  foreach t in array array[
    'asset_risk_scores','bom_knowledge','calc_knowledge','cmms_audit_log','conversation_analytics',
    'external_sync','failure_signature_alerts','hive_analytics_cache','hive_audit_log','hive_benchmarks',
    'integration_configs','offline_snapshot_cache','parts_staged_reservations','parts_staging_recommendations',
    'project_knowledge','tts_quality_log'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists %I on public.%I', t || '_hive_rw', t);  -- idempotent re-run
    execute format($p$create policy %I on public.%I for all
      using      (auth.uid() is not null and hive_id in (select public.user_hive_ids()))
      with check (auth.uid() is not null and hive_id in (select public.user_hive_ids()))$p$,
      t || '_hive_rw', t);
  end loop;
end $mig$;
