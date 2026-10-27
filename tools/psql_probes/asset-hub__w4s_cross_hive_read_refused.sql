-- cross_hive_read_refused (asset-hub, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (asset_nodes, hive_audit_log, hive_members, parts_staging_recommendations, pm_completions, pm_scope_items, rcm_fmea_modes, rcm_strategies, v_asset_truth, v_external_sync_truth, v_fmea_truth, v_logbook_truth, v_pf_truth, v_rcm_truth, v_risk_truth, v_sensor_recent, v_sensor_truth, v_weibull_truth) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_rows \| 0
-- expect: asset_nodes_own_rows_gt0 \| t
-- expect: hive_audit_log_fixture \| t
-- expect: hive_audit_log_foreign_rows \| 0
-- expect: hive_audit_log_own_rows_gt0 \| t
-- expect: hive_members_fixture \| t
-- expect: hive_members_foreign_rows \| 0
-- expect: hive_members_own_rows_gt0 \| t
-- expect: parts_staging_recommendations_fixture \| t
-- expect: parts_staging_recommendations_foreign_rows \| 0
-- expect: parts_staging_recommendations_own_rows_gt0 \| t
-- expect: pm_completions_fixture \| t
-- expect: pm_completions_foreign_rows \| 0
-- expect: pm_completions_own_rows_gt0 \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_rows \| 0
-- expect: pm_scope_items_own_rows_gt0 \| t
-- expect: rcm_fmea_modes_fixture \| t
-- expect: rcm_fmea_modes_foreign_rows \| 0
-- expect: rcm_fmea_modes_own_rows_gt0 \| t
-- expect: rcm_strategies_fixture \| t
-- expect: rcm_strategies_foreign_rows \| 0
-- expect: rcm_strategies_own_rows_gt0 \| t
-- expect: asset_fixture \| t
-- expect: asset_foreign_rows \| 0
-- expect: asset_own_rows_gt0 \| t
-- expect: external_sync_fixture \| t
-- expect: external_sync_foreign_rows \| 0
-- expect: external_sync_own_rows_gt0 \| t
-- expect: fmea_fixture \| t
-- expect: fmea_foreign_rows \| 0
-- expect: fmea_own_rows_gt0 \| t
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_rows \| 0
-- expect: logbook_own_rows_gt0 \| t
-- expect: pf_fixture \| t
-- expect: pf_foreign_rows \| 0
-- expect: pf_own_rows_gt0 \| t
-- expect: rcm_fixture \| t
-- expect: rcm_foreign_rows \| 0
-- expect: rcm_own_rows_gt0 \| t
-- expect: risk_fixture \| t
-- expect: risk_foreign_rows \| 0
-- expect: risk_own_rows_gt0 \| t
-- expect: sensor_recent_fixture \| t
-- expect: sensor_recent_foreign_rows \| 0
-- expect: sensor_recent_own_rows_gt0 \| t
-- expect: sensor_fixture \| t
-- expect: sensor_foreign_rows \| 0
-- expect: sensor_own_rows_gt0 \| t
-- expect: weibull_fixture \| t
-- expect: weibull_foreign_rows \| 0
-- expect: weibull_own_rows_gt0 \| t

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

CREATE TEMP TABLE _fx_parts_staging_recommendations AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM parts_staging_recommendations x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM parts_staging_recommendations x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_parts_staging_recommendations TO authenticated;
SELECT 'parts_staging_recommendations_fixture | ' || ((SELECT me FROM _fx_parts_staging_recommendations) IS NOT NULL AND (SELECT foreign_hive FROM _fx_parts_staging_recommendations) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_parts_staging_recommendations)::text, 'role','authenticated')::text, true);
SELECT 'parts_staging_recommendations_foreign_rows | ' || (SELECT count(*) FROM parts_staging_recommendations WHERE hive_id = (SELECT foreign_hive FROM _fx_parts_staging_recommendations));
SELECT 'parts_staging_recommendations_own_rows_gt0 | ' || ((SELECT count(*) FROM parts_staging_recommendations WHERE hive_id = (SELECT mine FROM _fx_parts_staging_recommendations)) > 0);
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

CREATE TEMP TABLE _fx_pm_scope_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM pm_scope_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM pm_scope_items x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_pm_scope_items TO authenticated;
SELECT 'pm_scope_items_fixture | ' || ((SELECT me FROM _fx_pm_scope_items) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_scope_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_scope_items)::text, 'role','authenticated')::text, true);
SELECT 'pm_scope_items_foreign_rows | ' || (SELECT count(*) FROM pm_scope_items WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_scope_items));
SELECT 'pm_scope_items_own_rows_gt0 | ' || ((SELECT count(*) FROM pm_scope_items WHERE hive_id = (SELECT mine FROM _fx_pm_scope_items)) > 0);
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

CREATE TEMP TABLE _fx_asset AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_asset_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_asset_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_asset TO authenticated;
SELECT 'asset_fixture | ' || ((SELECT me FROM _fx_asset) IS NOT NULL AND (SELECT foreign_hive FROM _fx_asset) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_asset)::text, 'role','authenticated')::text, true);
SELECT 'asset_foreign_rows | ' || (SELECT count(*) FROM v_asset_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_asset));
SELECT 'asset_own_rows_gt0 | ' || ((SELECT count(*) FROM v_asset_truth WHERE hive_id = (SELECT mine FROM _fx_asset)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_external_sync AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_external_sync_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_external_sync_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_external_sync TO authenticated;
SELECT 'external_sync_fixture | ' || ((SELECT me FROM _fx_external_sync) IS NOT NULL AND (SELECT foreign_hive FROM _fx_external_sync) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_external_sync)::text, 'role','authenticated')::text, true);
SELECT 'external_sync_foreign_rows | ' || (SELECT count(*) FROM v_external_sync_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_external_sync));
SELECT 'external_sync_own_rows_gt0 | ' || ((SELECT count(*) FROM v_external_sync_truth WHERE hive_id = (SELECT mine FROM _fx_external_sync)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_fmea AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_fmea_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_fmea_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_fmea TO authenticated;
SELECT 'fmea_fixture | ' || ((SELECT me FROM _fx_fmea) IS NOT NULL AND (SELECT foreign_hive FROM _fx_fmea) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_fmea)::text, 'role','authenticated')::text, true);
SELECT 'fmea_foreign_rows | ' || (SELECT count(*) FROM v_fmea_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_fmea));
SELECT 'fmea_own_rows_gt0 | ' || ((SELECT count(*) FROM v_fmea_truth WHERE hive_id = (SELECT mine FROM _fx_fmea)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_logbook AS
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
GRANT SELECT ON _fx_logbook TO authenticated;
SELECT 'logbook_fixture | ' || ((SELECT me FROM _fx_logbook) IS NOT NULL AND (SELECT foreign_hive FROM _fx_logbook) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_logbook)::text, 'role','authenticated')::text, true);
SELECT 'logbook_foreign_rows | ' || (SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_logbook));
SELECT 'logbook_own_rows_gt0 | ' || ((SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT mine FROM _fx_logbook)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pf AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_pf_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_pf_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_pf TO authenticated;
SELECT 'pf_fixture | ' || ((SELECT me FROM _fx_pf) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pf) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pf)::text, 'role','authenticated')::text, true);
SELECT 'pf_foreign_rows | ' || (SELECT count(*) FROM v_pf_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_pf));
SELECT 'pf_own_rows_gt0 | ' || ((SELECT count(*) FROM v_pf_truth WHERE hive_id = (SELECT mine FROM _fx_pf)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_rcm AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_rcm_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_rcm_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_rcm TO authenticated;
SELECT 'rcm_fixture | ' || ((SELECT me FROM _fx_rcm) IS NOT NULL AND (SELECT foreign_hive FROM _fx_rcm) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_rcm)::text, 'role','authenticated')::text, true);
SELECT 'rcm_foreign_rows | ' || (SELECT count(*) FROM v_rcm_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_rcm));
SELECT 'rcm_own_rows_gt0 | ' || ((SELECT count(*) FROM v_rcm_truth WHERE hive_id = (SELECT mine FROM _fx_rcm)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_risk AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_risk_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_risk_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_risk TO authenticated;
SELECT 'risk_fixture | ' || ((SELECT me FROM _fx_risk) IS NOT NULL AND (SELECT foreign_hive FROM _fx_risk) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_risk)::text, 'role','authenticated')::text, true);
SELECT 'risk_foreign_rows | ' || (SELECT count(*) FROM v_risk_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_risk));
SELECT 'risk_own_rows_gt0 | ' || ((SELECT count(*) FROM v_risk_truth WHERE hive_id = (SELECT mine FROM _fx_risk)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_sensor_recent AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_sensor_recent x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_sensor_recent x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_sensor_recent TO authenticated;
SELECT 'sensor_recent_fixture | ' || ((SELECT me FROM _fx_sensor_recent) IS NOT NULL AND (SELECT foreign_hive FROM _fx_sensor_recent) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_sensor_recent)::text, 'role','authenticated')::text, true);
SELECT 'sensor_recent_foreign_rows | ' || (SELECT count(*) FROM v_sensor_recent WHERE hive_id = (SELECT foreign_hive FROM _fx_sensor_recent));
SELECT 'sensor_recent_own_rows_gt0 | ' || ((SELECT count(*) FROM v_sensor_recent WHERE hive_id = (SELECT mine FROM _fx_sensor_recent)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_sensor AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_sensor_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_sensor_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_sensor TO authenticated;
SELECT 'sensor_fixture | ' || ((SELECT me FROM _fx_sensor) IS NOT NULL AND (SELECT foreign_hive FROM _fx_sensor) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_sensor)::text, 'role','authenticated')::text, true);
SELECT 'sensor_foreign_rows | ' || (SELECT count(*) FROM v_sensor_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_sensor));
SELECT 'sensor_own_rows_gt0 | ' || ((SELECT count(*) FROM v_sensor_truth WHERE hive_id = (SELECT mine FROM _fx_sensor)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_weibull AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_weibull_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_weibull_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_weibull TO authenticated;
SELECT 'weibull_fixture | ' || ((SELECT me FROM _fx_weibull) IS NOT NULL AND (SELECT foreign_hive FROM _fx_weibull) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_weibull)::text, 'role','authenticated')::text, true);
SELECT 'weibull_foreign_rows | ' || (SELECT count(*) FROM v_weibull_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_weibull));
SELECT 'weibull_own_rows_gt0 | ' || ((SELECT count(*) FROM v_weibull_truth WHERE hive_id = (SELECT mine FROM _fx_weibull)) > 0);
ROLLBACK;
