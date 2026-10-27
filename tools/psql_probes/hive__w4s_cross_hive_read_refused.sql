-- cross_hive_read_refused (hive, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (asset_nodes, community_xp, hive_audit_log, hive_benchmarks, hive_members, logbook, pm_completions, rcm_fmea_modes, rcm_strategies, v_ai_reports_truth, v_alert_truth, v_amc_truth, v_hive_value_summary, v_inventory_items_truth, v_knowledge_freshness_truth, v_logbook_truth, v_pm_compliance_truth, v_pm_scope_items_truth, v_worker_assignment_truth, v_worker_truth) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_rows \| 0
-- expect: asset_nodes_own_rows_gt0 \| t
-- expect: community_xp_fixture \| t
-- expect: community_xp_foreign_rows \| 0
-- expect: community_xp_own_rows_gt0 \| t
-- expect: hive_audit_log_fixture \| t
-- expect: hive_audit_log_foreign_rows \| 0
-- expect: hive_audit_log_own_rows_gt0 \| t
-- expect: hive_benchmarks_fixture \| t
-- expect: hive_benchmarks_foreign_rows \| 0
-- expect: hive_benchmarks_own_rows_gt0 \| t
-- expect: hive_members_fixture \| t
-- expect: hive_members_foreign_rows \| 0
-- expect: hive_members_own_rows_gt0 \| t
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_rows \| 0
-- expect: logbook_own_rows_gt0 \| t
-- expect: pm_completions_fixture \| t
-- expect: pm_completions_foreign_rows \| 0
-- expect: pm_completions_own_rows_gt0 \| t
-- expect: rcm_fmea_modes_fixture \| t
-- expect: rcm_fmea_modes_foreign_rows \| 0
-- expect: rcm_fmea_modes_own_rows_gt0 \| t
-- expect: rcm_strategies_fixture \| t
-- expect: rcm_strategies_foreign_rows \| 0
-- expect: rcm_strategies_own_rows_gt0 \| t
-- expect: ai_reports_fixture \| t
-- expect: ai_reports_foreign_rows \| 0
-- expect: ai_reports_own_rows_gt0 \| t
-- expect: alert_fixture \| t
-- expect: alert_foreign_rows \| 0
-- expect: alert_own_rows_gt0 \| t
-- expect: amc_fixture \| t
-- expect: amc_foreign_rows \| 0
-- expect: amc_own_rows_gt0 \| t
-- expect: hive_value_summary_fixture \| t
-- expect: hive_value_summary_foreign_rows \| 0
-- expect: hive_value_summary_own_rows_gt0 \| t
-- expect: inventory_items_fixture \| t
-- expect: inventory_items_foreign_rows \| 0
-- expect: inventory_items_own_rows_gt0 \| t
-- expect: knowledge_freshness_fixture \| t
-- expect: knowledge_freshness_foreign_rows \| 0
-- expect: knowledge_freshness_own_rows_gt0 \| t
-- expect: v_logbook_truth_fixture \| t
-- expect: v_logbook_truth_foreign_rows \| 0
-- expect: v_logbook_truth_own_rows_gt0 \| t
-- expect: pm_compliance_fixture \| t
-- expect: pm_compliance_foreign_rows \| 0
-- expect: pm_compliance_own_rows_gt0 \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_rows \| 0
-- expect: pm_scope_items_own_rows_gt0 \| t
-- expect: worker_assignment_fixture \| t
-- expect: worker_assignment_foreign_rows \| 0
-- expect: worker_assignment_own_rows_gt0 \| t
-- expect: worker_fixture \| t
-- expect: worker_foreign_rows \| 0
-- expect: worker_own_rows_gt0 \| t

CREATE TEMP TABLE _fx_asset_nodes AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM asset_nodes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM asset_nodes x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_asset_nodes TO authenticated;
SELECT 'asset_nodes_fixture | ' || ((SELECT me FROM _fx_asset_nodes) IS NOT NULL AND (SELECT foreign_hive FROM _fx_asset_nodes) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_asset_nodes)::text, 'role','authenticated')::text, true);
SELECT 'asset_nodes_foreign_rows | ' || (SELECT count(*) FROM asset_nodes WHERE hive_id = (SELECT foreign_hive FROM _fx_asset_nodes));
SELECT 'asset_nodes_own_rows_gt0 | ' || ((SELECT count(*) FROM asset_nodes WHERE hive_id = (SELECT mine FROM _fx_asset_nodes)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_community_xp AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM community_xp x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM community_xp x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_community_xp TO authenticated;
SELECT 'community_xp_fixture | ' || ((SELECT me FROM _fx_community_xp) IS NOT NULL AND (SELECT foreign_hive FROM _fx_community_xp) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_community_xp)::text, 'role','authenticated')::text, true);
SELECT 'community_xp_foreign_rows | ' || (SELECT count(*) FROM community_xp WHERE hive_id = (SELECT foreign_hive FROM _fx_community_xp));
SELECT 'community_xp_own_rows_gt0 | ' || ((SELECT count(*) FROM community_xp WHERE hive_id = (SELECT mine FROM _fx_community_xp)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_hive_audit_log AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM hive_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM hive_audit_log x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_hive_audit_log TO authenticated;
SELECT 'hive_audit_log_fixture | ' || ((SELECT me FROM _fx_hive_audit_log) IS NOT NULL AND (SELECT foreign_hive FROM _fx_hive_audit_log) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_hive_audit_log)::text, 'role','authenticated')::text, true);
SELECT 'hive_audit_log_foreign_rows | ' || (SELECT count(*) FROM hive_audit_log WHERE hive_id = (SELECT foreign_hive FROM _fx_hive_audit_log));
SELECT 'hive_audit_log_own_rows_gt0 | ' || ((SELECT count(*) FROM hive_audit_log WHERE hive_id = (SELECT mine FROM _fx_hive_audit_log)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_hive_benchmarks AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM hive_benchmarks x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM hive_benchmarks x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_hive_benchmarks TO authenticated;
SELECT 'hive_benchmarks_fixture | ' || ((SELECT me FROM _fx_hive_benchmarks) IS NOT NULL AND (SELECT foreign_hive FROM _fx_hive_benchmarks) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_hive_benchmarks)::text, 'role','authenticated')::text, true);
SELECT 'hive_benchmarks_foreign_rows | ' || (SELECT count(*) FROM hive_benchmarks WHERE hive_id = (SELECT foreign_hive FROM _fx_hive_benchmarks));
SELECT 'hive_benchmarks_own_rows_gt0 | ' || ((SELECT count(*) FROM hive_benchmarks WHERE hive_id = (SELECT mine FROM _fx_hive_benchmarks)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_hive_members AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM hive_members x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM hive_members x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_hive_members TO authenticated;
SELECT 'hive_members_fixture | ' || ((SELECT me FROM _fx_hive_members) IS NOT NULL AND (SELECT foreign_hive FROM _fx_hive_members) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_hive_members)::text, 'role','authenticated')::text, true);
SELECT 'hive_members_foreign_rows | ' || (SELECT count(*) FROM hive_members WHERE hive_id = (SELECT foreign_hive FROM _fx_hive_members));
SELECT 'hive_members_own_rows_gt0 | ' || ((SELECT count(*) FROM hive_members WHERE hive_id = (SELECT mine FROM _fx_hive_members)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_logbook AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM logbook x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM logbook x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_logbook TO authenticated;
SELECT 'logbook_fixture | ' || ((SELECT me FROM _fx_logbook) IS NOT NULL AND (SELECT foreign_hive FROM _fx_logbook) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_logbook)::text, 'role','authenticated')::text, true);
SELECT 'logbook_foreign_rows | ' || (SELECT count(*) FROM logbook WHERE hive_id = (SELECT foreign_hive FROM _fx_logbook));
SELECT 'logbook_own_rows_gt0 | ' || ((SELECT count(*) FROM logbook WHERE hive_id = (SELECT mine FROM _fx_logbook)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pm_completions AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM pm_completions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM pm_completions x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_pm_completions TO authenticated;
SELECT 'pm_completions_fixture | ' || ((SELECT me FROM _fx_pm_completions) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_completions) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_completions)::text, 'role','authenticated')::text, true);
SELECT 'pm_completions_foreign_rows | ' || (SELECT count(*) FROM pm_completions WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_completions));
SELECT 'pm_completions_own_rows_gt0 | ' || ((SELECT count(*) FROM pm_completions WHERE hive_id = (SELECT mine FROM _fx_pm_completions)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_rcm_fmea_modes AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM rcm_fmea_modes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM rcm_fmea_modes x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_rcm_fmea_modes TO authenticated;
SELECT 'rcm_fmea_modes_fixture | ' || ((SELECT me FROM _fx_rcm_fmea_modes) IS NOT NULL AND (SELECT foreign_hive FROM _fx_rcm_fmea_modes) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_rcm_fmea_modes)::text, 'role','authenticated')::text, true);
SELECT 'rcm_fmea_modes_foreign_rows | ' || (SELECT count(*) FROM rcm_fmea_modes WHERE hive_id = (SELECT foreign_hive FROM _fx_rcm_fmea_modes));
SELECT 'rcm_fmea_modes_own_rows_gt0 | ' || ((SELECT count(*) FROM rcm_fmea_modes WHERE hive_id = (SELECT mine FROM _fx_rcm_fmea_modes)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_rcm_strategies AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM rcm_strategies x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM rcm_strategies x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_rcm_strategies TO authenticated;
SELECT 'rcm_strategies_fixture | ' || ((SELECT me FROM _fx_rcm_strategies) IS NOT NULL AND (SELECT foreign_hive FROM _fx_rcm_strategies) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_rcm_strategies)::text, 'role','authenticated')::text, true);
SELECT 'rcm_strategies_foreign_rows | ' || (SELECT count(*) FROM rcm_strategies WHERE hive_id = (SELECT foreign_hive FROM _fx_rcm_strategies));
SELECT 'rcm_strategies_own_rows_gt0 | ' || ((SELECT count(*) FROM rcm_strategies WHERE hive_id = (SELECT mine FROM _fx_rcm_strategies)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_ai_reports AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_ai_reports_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_ai_reports_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_ai_reports TO authenticated;
SELECT 'ai_reports_fixture | ' || ((SELECT me FROM _fx_ai_reports) IS NOT NULL AND (SELECT foreign_hive FROM _fx_ai_reports) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_ai_reports)::text, 'role','authenticated')::text, true);
SELECT 'ai_reports_foreign_rows | ' || (SELECT count(*) FROM v_ai_reports_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_ai_reports));
SELECT 'ai_reports_own_rows_gt0 | ' || ((SELECT count(*) FROM v_ai_reports_truth WHERE hive_id = (SELECT mine FROM _fx_ai_reports)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_alert AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_alert_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_alert_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_alert TO authenticated;
SELECT 'alert_fixture | ' || ((SELECT me FROM _fx_alert) IS NOT NULL AND (SELECT foreign_hive FROM _fx_alert) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_alert)::text, 'role','authenticated')::text, true);
SELECT 'alert_foreign_rows | ' || (SELECT count(*) FROM v_alert_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_alert));
SELECT 'alert_own_rows_gt0 | ' || ((SELECT count(*) FROM v_alert_truth WHERE hive_id = (SELECT mine FROM _fx_alert)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_amc AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_amc_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_amc_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_amc TO authenticated;
SELECT 'amc_fixture | ' || ((SELECT me FROM _fx_amc) IS NOT NULL AND (SELECT foreign_hive FROM _fx_amc) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_amc)::text, 'role','authenticated')::text, true);
SELECT 'amc_foreign_rows | ' || (SELECT count(*) FROM v_amc_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_amc));
SELECT 'amc_own_rows_gt0 | ' || ((SELECT count(*) FROM v_amc_truth WHERE hive_id = (SELECT mine FROM _fx_amc)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_hive_value_summary AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_hive_value_summary x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_hive_value_summary x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_hive_value_summary TO authenticated;
SELECT 'hive_value_summary_fixture | ' || ((SELECT me FROM _fx_hive_value_summary) IS NOT NULL AND (SELECT foreign_hive FROM _fx_hive_value_summary) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_hive_value_summary)::text, 'role','authenticated')::text, true);
SELECT 'hive_value_summary_foreign_rows | ' || (SELECT count(*) FROM v_hive_value_summary WHERE hive_id = (SELECT foreign_hive FROM _fx_hive_value_summary));
SELECT 'hive_value_summary_own_rows_gt0 | ' || ((SELECT count(*) FROM v_hive_value_summary WHERE hive_id = (SELECT mine FROM _fx_hive_value_summary)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_inventory_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_inventory_items_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_inventory_items_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_inventory_items TO authenticated;
SELECT 'inventory_items_fixture | ' || ((SELECT me FROM _fx_inventory_items) IS NOT NULL AND (SELECT foreign_hive FROM _fx_inventory_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_inventory_items)::text, 'role','authenticated')::text, true);
SELECT 'inventory_items_foreign_rows | ' || (SELECT count(*) FROM v_inventory_items_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_inventory_items));
SELECT 'inventory_items_own_rows_gt0 | ' || ((SELECT count(*) FROM v_inventory_items_truth WHERE hive_id = (SELECT mine FROM _fx_inventory_items)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_knowledge_freshness AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_knowledge_freshness_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_knowledge_freshness_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_knowledge_freshness TO authenticated;
SELECT 'knowledge_freshness_fixture | ' || ((SELECT me FROM _fx_knowledge_freshness) IS NOT NULL AND (SELECT foreign_hive FROM _fx_knowledge_freshness) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_knowledge_freshness)::text, 'role','authenticated')::text, true);
SELECT 'knowledge_freshness_foreign_rows | ' || (SELECT count(*) FROM v_knowledge_freshness_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_knowledge_freshness));
SELECT 'knowledge_freshness_own_rows_gt0 | ' || ((SELECT count(*) FROM v_knowledge_freshness_truth WHERE hive_id = (SELECT mine FROM _fx_knowledge_freshness)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_v_logbook_truth AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_logbook_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_logbook_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_v_logbook_truth TO authenticated;
SELECT 'v_logbook_truth_fixture | ' || ((SELECT me FROM _fx_v_logbook_truth) IS NOT NULL AND (SELECT foreign_hive FROM _fx_v_logbook_truth) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_v_logbook_truth)::text, 'role','authenticated')::text, true);
SELECT 'v_logbook_truth_foreign_rows | ' || (SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_v_logbook_truth));
SELECT 'v_logbook_truth_own_rows_gt0 | ' || ((SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT mine FROM _fx_v_logbook_truth)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pm_compliance AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_pm_compliance_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_pm_compliance_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_pm_compliance TO authenticated;
SELECT 'pm_compliance_fixture | ' || ((SELECT me FROM _fx_pm_compliance) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_compliance) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_compliance)::text, 'role','authenticated')::text, true);
SELECT 'pm_compliance_foreign_rows | ' || (SELECT count(*) FROM v_pm_compliance_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_compliance));
SELECT 'pm_compliance_own_rows_gt0 | ' || ((SELECT count(*) FROM v_pm_compliance_truth WHERE hive_id = (SELECT mine FROM _fx_pm_compliance)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pm_scope_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_pm_scope_items_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_pm_scope_items_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_pm_scope_items TO authenticated;
SELECT 'pm_scope_items_fixture | ' || ((SELECT me FROM _fx_pm_scope_items) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_scope_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_scope_items)::text, 'role','authenticated')::text, true);
SELECT 'pm_scope_items_foreign_rows | ' || (SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_scope_items));
SELECT 'pm_scope_items_own_rows_gt0 | ' || ((SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id = (SELECT mine FROM _fx_pm_scope_items)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_worker_assignment AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_worker_assignment_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_worker_assignment_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_worker_assignment TO authenticated;
SELECT 'worker_assignment_fixture | ' || ((SELECT me FROM _fx_worker_assignment) IS NOT NULL AND (SELECT foreign_hive FROM _fx_worker_assignment) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_worker_assignment)::text, 'role','authenticated')::text, true);
SELECT 'worker_assignment_foreign_rows | ' || (SELECT count(*) FROM v_worker_assignment_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_worker_assignment));
SELECT 'worker_assignment_own_rows_gt0 | ' || ((SELECT count(*) FROM v_worker_assignment_truth WHERE hive_id = (SELECT mine FROM _fx_worker_assignment)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_worker AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_worker_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_worker_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_worker TO authenticated;
SELECT 'worker_fixture | ' || ((SELECT me FROM _fx_worker) IS NOT NULL AND (SELECT foreign_hive FROM _fx_worker) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_worker)::text, 'role','authenticated')::text, true);
SELECT 'worker_foreign_rows | ' || (SELECT count(*) FROM v_worker_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_worker));
SELECT 'worker_own_rows_gt0 | ' || ((SELECT count(*) FROM v_worker_truth WHERE hive_id = (SELECT mine FROM _fx_worker)) > 0);
ROLLBACK;
