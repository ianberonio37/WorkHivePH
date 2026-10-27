-- cross_hive_read_refused (integrations, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (api_keys, asset_nodes, cmms_audit_log, external_sync, integration_configs, inventory_items, logbook, pm_assets, pm_scope_items, v_external_sync_truth, v_logbook_truth) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: api_keys_fixture \| t
-- expect: api_keys_foreign_rows \| 0
-- expect: api_keys_own_rows_gt0 \| t
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_rows \| 0
-- expect: asset_nodes_own_rows_gt0 \| t
-- expect: cmms_audit_log_fixture \| t
-- expect: cmms_audit_log_foreign_rows \| 0
-- expect: cmms_audit_log_own_rows_gt0 \| t
-- expect: external_sync_fixture \| t
-- expect: external_sync_foreign_rows \| 0
-- expect: external_sync_own_rows_gt0 \| t
-- expect: integration_configs_fixture \| t
-- expect: integration_configs_foreign_rows \| 0
-- expect: integration_configs_own_rows_gt0 \| t
-- expect: inventory_items_fixture \| t
-- expect: inventory_items_foreign_rows \| 0
-- expect: inventory_items_own_rows_gt0 \| t
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_rows \| 0
-- expect: logbook_own_rows_gt0 \| t
-- expect: pm_assets_fixture \| t
-- expect: pm_assets_foreign_rows \| 0
-- expect: pm_assets_own_rows_gt0 \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_rows \| 0
-- expect: pm_scope_items_own_rows_gt0 \| t
-- expect: v_external_sync_truth_fixture \| t
-- expect: v_external_sync_truth_foreign_rows \| 0
-- expect: v_external_sync_truth_own_rows_gt0 \| t
-- expect: v_logbook_truth_fixture \| t
-- expect: v_logbook_truth_foreign_rows \| 0
-- expect: v_logbook_truth_own_rows_gt0 \| t

CREATE TEMP TABLE _fx_api_keys AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM api_keys x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM api_keys x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_api_keys TO authenticated;
SELECT 'api_keys_fixture | ' || ((SELECT me FROM _fx_api_keys) IS NOT NULL AND (SELECT foreign_hive FROM _fx_api_keys) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_api_keys)::text, 'role','authenticated')::text, true);
SELECT 'api_keys_foreign_rows | ' || (SELECT count(*) FROM api_keys WHERE hive_id = (SELECT foreign_hive FROM _fx_api_keys));
SELECT 'api_keys_own_rows_gt0 | ' || ((SELECT count(*) FROM api_keys WHERE hive_id = (SELECT mine FROM _fx_api_keys)) > 0);
ROLLBACK;

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
ORDER BY (m.role = 'supervisor') DESC, (SELECT count(*) FROM asset_nodes x WHERE x.hive_id = m.hive_id AND x.auth_uid = m.auth_uid) DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_asset_nodes TO authenticated;
SELECT 'asset_nodes_fixture | ' || ((SELECT me FROM _fx_asset_nodes) IS NOT NULL AND (SELECT foreign_hive FROM _fx_asset_nodes) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_asset_nodes)::text, 'role','authenticated')::text, true);
SELECT 'asset_nodes_foreign_rows | ' || (SELECT count(*) FROM asset_nodes WHERE hive_id = (SELECT foreign_hive FROM _fx_asset_nodes));
SELECT 'asset_nodes_own_rows_gt0 | ' || ((SELECT count(*) FROM asset_nodes WHERE hive_id = (SELECT mine FROM _fx_asset_nodes)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_cmms_audit_log AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM cmms_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM cmms_audit_log x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_cmms_audit_log TO authenticated;
SELECT 'cmms_audit_log_fixture | ' || ((SELECT me FROM _fx_cmms_audit_log) IS NOT NULL AND (SELECT foreign_hive FROM _fx_cmms_audit_log) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_cmms_audit_log)::text, 'role','authenticated')::text, true);
SELECT 'cmms_audit_log_foreign_rows | ' || (SELECT count(*) FROM cmms_audit_log WHERE hive_id = (SELECT foreign_hive FROM _fx_cmms_audit_log));
SELECT 'cmms_audit_log_own_rows_gt0 | ' || ((SELECT count(*) FROM cmms_audit_log WHERE hive_id = (SELECT mine FROM _fx_cmms_audit_log)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_external_sync AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM external_sync x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM external_sync x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_external_sync TO authenticated;
SELECT 'external_sync_fixture | ' || ((SELECT me FROM _fx_external_sync) IS NOT NULL AND (SELECT foreign_hive FROM _fx_external_sync) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_external_sync)::text, 'role','authenticated')::text, true);
SELECT 'external_sync_foreign_rows | ' || (SELECT count(*) FROM external_sync WHERE hive_id = (SELECT foreign_hive FROM _fx_external_sync));
SELECT 'external_sync_own_rows_gt0 | ' || ((SELECT count(*) FROM external_sync WHERE hive_id = (SELECT mine FROM _fx_external_sync)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_integration_configs AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM integration_configs x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM integration_configs x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_integration_configs TO authenticated;
SELECT 'integration_configs_fixture | ' || ((SELECT me FROM _fx_integration_configs) IS NOT NULL AND (SELECT foreign_hive FROM _fx_integration_configs) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_integration_configs)::text, 'role','authenticated')::text, true);
SELECT 'integration_configs_foreign_rows | ' || (SELECT count(*) FROM integration_configs WHERE hive_id = (SELECT foreign_hive FROM _fx_integration_configs));
SELECT 'integration_configs_own_rows_gt0 | ' || ((SELECT count(*) FROM integration_configs WHERE hive_id = (SELECT mine FROM _fx_integration_configs)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_inventory_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM inventory_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM inventory_items x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC, (SELECT count(*) FROM inventory_items x WHERE x.hive_id = m.hive_id AND x.auth_uid = m.auth_uid) DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_inventory_items TO authenticated;
SELECT 'inventory_items_fixture | ' || ((SELECT me FROM _fx_inventory_items) IS NOT NULL AND (SELECT foreign_hive FROM _fx_inventory_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_inventory_items)::text, 'role','authenticated')::text, true);
SELECT 'inventory_items_foreign_rows | ' || (SELECT count(*) FROM inventory_items WHERE hive_id = (SELECT foreign_hive FROM _fx_inventory_items));
SELECT 'inventory_items_own_rows_gt0 | ' || ((SELECT count(*) FROM inventory_items WHERE hive_id = (SELECT mine FROM _fx_inventory_items)) > 0);
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
ORDER BY (m.role = 'supervisor') DESC, (SELECT count(*) FROM logbook x WHERE x.hive_id = m.hive_id AND x.auth_uid = m.auth_uid) DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_logbook TO authenticated;
SELECT 'logbook_fixture | ' || ((SELECT me FROM _fx_logbook) IS NOT NULL AND (SELECT foreign_hive FROM _fx_logbook) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_logbook)::text, 'role','authenticated')::text, true);
SELECT 'logbook_foreign_rows | ' || (SELECT count(*) FROM logbook WHERE hive_id = (SELECT foreign_hive FROM _fx_logbook));
SELECT 'logbook_own_rows_gt0 | ' || ((SELECT count(*) FROM logbook WHERE hive_id = (SELECT mine FROM _fx_logbook)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pm_assets AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM pm_assets x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM pm_assets x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC, (SELECT count(*) FROM pm_assets x WHERE x.hive_id = m.hive_id AND x.auth_uid = m.auth_uid) DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_pm_assets TO authenticated;
SELECT 'pm_assets_fixture | ' || ((SELECT me FROM _fx_pm_assets) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_assets) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_assets)::text, 'role','authenticated')::text, true);
SELECT 'pm_assets_foreign_rows | ' || (SELECT count(*) FROM pm_assets WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_assets));
SELECT 'pm_assets_own_rows_gt0 | ' || ((SELECT count(*) FROM pm_assets WHERE hive_id = (SELECT mine FROM _fx_pm_assets)) > 0);
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
ORDER BY (m.role = 'supervisor') DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_pm_scope_items TO authenticated;
SELECT 'pm_scope_items_fixture | ' || ((SELECT me FROM _fx_pm_scope_items) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_scope_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_scope_items)::text, 'role','authenticated')::text, true);
SELECT 'pm_scope_items_foreign_rows | ' || (SELECT count(*) FROM pm_scope_items WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_scope_items));
SELECT 'pm_scope_items_own_rows_gt0 | ' || ((SELECT count(*) FROM pm_scope_items WHERE hive_id = (SELECT mine FROM _fx_pm_scope_items)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_v_external_sync_truth AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_external_sync_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_external_sync_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_v_external_sync_truth TO authenticated;
SELECT 'v_external_sync_truth_fixture | ' || ((SELECT me FROM _fx_v_external_sync_truth) IS NOT NULL AND (SELECT foreign_hive FROM _fx_v_external_sync_truth) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_v_external_sync_truth)::text, 'role','authenticated')::text, true);
SELECT 'v_external_sync_truth_foreign_rows | ' || (SELECT count(*) FROM v_external_sync_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_v_external_sync_truth));
SELECT 'v_external_sync_truth_own_rows_gt0 | ' || ((SELECT count(*) FROM v_external_sync_truth WHERE hive_id = (SELECT mine FROM _fx_v_external_sync_truth)) > 0);
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
ORDER BY (m.role = 'supervisor') DESC, (SELECT count(*) FROM v_logbook_truth x WHERE x.hive_id = m.hive_id AND x.auth_uid = m.auth_uid) DESC, m.auth_uid
LIMIT 1;
GRANT SELECT ON _fx_v_logbook_truth TO authenticated;
SELECT 'v_logbook_truth_fixture | ' || ((SELECT me FROM _fx_v_logbook_truth) IS NOT NULL AND (SELECT foreign_hive FROM _fx_v_logbook_truth) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_v_logbook_truth)::text, 'role','authenticated')::text, true);
SELECT 'v_logbook_truth_foreign_rows | ' || (SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_v_logbook_truth));
SELECT 'v_logbook_truth_own_rows_gt0 | ' || ((SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT mine FROM _fx_v_logbook_truth)) > 0);
ROLLBACK;
