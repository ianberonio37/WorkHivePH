-- write_authz_depth (integrations, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (api_keys, asset_nodes, cmms_audit_log, external_sync, integration_configs, inventory_items, logbook, pm_assets, pm_scope_items) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: api_keys_fixture \| t
-- expect: api_keys_foreign_update_touched \| (0\b|refused)
-- expect: api_keys_foreign_delete_touched \| (0\b|refused)
-- expect: api_keys_own_update_touched_gt0 \| t
-- expect: api_keys_move_into_foreign \| (0\b|refused)
-- forbid: api_keys_move_into_foreign \| [1-9]
-- expect: api_keys_rows_restored \| t
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_update_touched \| (0\b|refused)
-- expect: asset_nodes_foreign_delete_touched \| (0\b|refused)
-- expect: asset_nodes_own_update_touched_gt0 \| t
-- expect: asset_nodes_move_into_foreign \| (0\b|refused)
-- forbid: asset_nodes_move_into_foreign \| [1-9]
-- expect: asset_nodes_rows_restored \| t
-- expect: cmms_audit_log_fixture \| t
-- expect: cmms_audit_log_foreign_update_touched \| (0\b|refused)
-- expect: cmms_audit_log_foreign_delete_touched \| (0\b|refused)
-- expect: cmms_audit_log_move_into_foreign \| (0\b|refused)
-- forbid: cmms_audit_log_move_into_foreign \| [1-9]
-- expect: cmms_audit_log_rows_restored \| t
-- expect: external_sync_fixture \| t
-- expect: external_sync_foreign_update_touched \| (0\b|refused)
-- expect: external_sync_foreign_delete_touched \| (0\b|refused)
-- expect: external_sync_own_update_touched_gt0 \| t
-- expect: external_sync_move_into_foreign \| (0\b|refused)
-- forbid: external_sync_move_into_foreign \| [1-9]
-- expect: external_sync_rows_restored \| t
-- expect: integration_configs_fixture \| t
-- expect: integration_configs_foreign_update_touched \| (0\b|refused)
-- expect: integration_configs_foreign_delete_touched \| (0\b|refused)
-- expect: integration_configs_own_update_touched_gt0 \| t
-- expect: integration_configs_move_into_foreign \| (0\b|refused)
-- forbid: integration_configs_move_into_foreign \| [1-9]
-- expect: integration_configs_rows_restored \| t
-- expect: inventory_items_fixture \| t
-- expect: inventory_items_foreign_update_touched \| (0\b|refused)
-- expect: inventory_items_foreign_delete_touched \| (0\b|refused)
-- expect: inventory_items_own_update_touched_gt0 \| t
-- expect: inventory_items_move_into_foreign \| (0\b|refused)
-- forbid: inventory_items_move_into_foreign \| [1-9]
-- expect: inventory_items_rows_restored \| t
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_update_touched \| (0\b|refused)
-- expect: logbook_foreign_delete_touched \| (0\b|refused)
-- expect: logbook_move_into_foreign \| (0\b|refused)
-- forbid: logbook_move_into_foreign \| [1-9]
-- expect: logbook_rows_restored \| t
-- expect: pm_assets_fixture \| t
-- expect: pm_assets_foreign_update_touched \| (0\b|refused)
-- expect: pm_assets_foreign_delete_touched \| (0\b|refused)
-- expect: pm_assets_own_update_touched_gt0 \| t
-- expect: pm_assets_move_into_foreign \| (0\b|refused)
-- forbid: pm_assets_move_into_foreign \| [1-9]
-- expect: pm_assets_rows_restored \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_update_touched \| (0\b|refused)
-- expect: pm_scope_items_foreign_delete_touched \| (0\b|refused)
-- expect: pm_scope_items_own_update_touched_gt0 \| t
-- expect: pm_scope_items_move_into_foreign \| (0\b|refused)
-- forbid: pm_scope_items_move_into_foreign \| [1-9]
-- expect: pm_scope_items_rows_restored \| t

CREATE TEMP TABLE _wx_api_keys AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM api_keys x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM api_keys x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM api_keys x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM api_keys) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM api_keys x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_api_keys TO authenticated;
SELECT 'api_keys_fixture | ' || ((SELECT me FROM _wx_api_keys) IS NOT NULL AND (SELECT foreign_row FROM _wx_api_keys) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_api_keys(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE api_keys SET id = id WHERE id = (SELECT foreign_row FROM _wx_api_keys);
  ELSIF op = 'foreign_delete' THEN DELETE FROM api_keys WHERE id = (SELECT foreign_row FROM _wx_api_keys);
  ELSIF op = 'own_update' THEN UPDATE api_keys SET id = id WHERE id = (SELECT own_row FROM _wx_api_keys);
  ELSIF op = 'move' THEN UPDATE api_keys SET hive_id = (SELECT foreign_hive FROM _wx_api_keys) WHERE id = (SELECT own_row FROM _wx_api_keys);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_api_keys)::text, 'role','authenticated')::text, true);
SELECT 'api_keys_foreign_update_touched | ' || pg_temp.wx_try_api_keys('foreign_update');
SELECT 'api_keys_foreign_delete_touched | ' || pg_temp.wx_try_api_keys('foreign_delete');
SELECT 'api_keys_move_into_foreign | ' || pg_temp.wx_try_api_keys('move');
SELECT 'api_keys_own_update_touched_gt0 | ' || (pg_temp.wx_try_api_keys('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'api_keys_rows_restored | ' || ((SELECT count(*) FROM api_keys) = (SELECT n0 FROM _wx_api_keys));

CREATE TEMP TABLE _wx_asset_nodes AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM asset_nodes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM asset_nodes x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM asset_nodes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM asset_nodes) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM asset_nodes x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_asset_nodes TO authenticated;
SELECT 'asset_nodes_fixture | ' || ((SELECT me FROM _wx_asset_nodes) IS NOT NULL AND (SELECT foreign_row FROM _wx_asset_nodes) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_asset_nodes(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE asset_nodes SET id = id WHERE id = (SELECT foreign_row FROM _wx_asset_nodes);
  ELSIF op = 'foreign_delete' THEN DELETE FROM asset_nodes WHERE id = (SELECT foreign_row FROM _wx_asset_nodes);
  ELSIF op = 'own_update' THEN UPDATE asset_nodes SET id = id WHERE id = (SELECT own_row FROM _wx_asset_nodes);
  ELSIF op = 'move' THEN UPDATE asset_nodes SET hive_id = (SELECT foreign_hive FROM _wx_asset_nodes) WHERE id = (SELECT own_row FROM _wx_asset_nodes);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_asset_nodes)::text, 'role','authenticated')::text, true);
SELECT 'asset_nodes_foreign_update_touched | ' || pg_temp.wx_try_asset_nodes('foreign_update');
SELECT 'asset_nodes_foreign_delete_touched | ' || pg_temp.wx_try_asset_nodes('foreign_delete');
SELECT 'asset_nodes_move_into_foreign | ' || pg_temp.wx_try_asset_nodes('move');
SELECT 'asset_nodes_own_update_touched_gt0 | ' || (pg_temp.wx_try_asset_nodes('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'asset_nodes_rows_restored | ' || ((SELECT count(*) FROM asset_nodes) = (SELECT n0 FROM _wx_asset_nodes));

CREATE TEMP TABLE _wx_cmms_audit_log AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM cmms_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM cmms_audit_log x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM cmms_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM cmms_audit_log) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM cmms_audit_log x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_cmms_audit_log TO authenticated;
SELECT 'cmms_audit_log_fixture | ' || ((SELECT me FROM _wx_cmms_audit_log) IS NOT NULL AND (SELECT foreign_row FROM _wx_cmms_audit_log) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_cmms_audit_log(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE cmms_audit_log SET id = id WHERE id = (SELECT foreign_row FROM _wx_cmms_audit_log);
  ELSIF op = 'foreign_delete' THEN DELETE FROM cmms_audit_log WHERE id = (SELECT foreign_row FROM _wx_cmms_audit_log);
  ELSIF op = 'own_update' THEN UPDATE cmms_audit_log SET id = id WHERE id = (SELECT own_row FROM _wx_cmms_audit_log);
  ELSIF op = 'move' THEN UPDATE cmms_audit_log SET hive_id = (SELECT foreign_hive FROM _wx_cmms_audit_log) WHERE id = (SELECT own_row FROM _wx_cmms_audit_log);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_cmms_audit_log)::text, 'role','authenticated')::text, true);
SELECT 'cmms_audit_log_foreign_update_touched | ' || pg_temp.wx_try_cmms_audit_log('foreign_update');
SELECT 'cmms_audit_log_foreign_delete_touched | ' || pg_temp.wx_try_cmms_audit_log('foreign_delete');
SELECT 'cmms_audit_log_move_into_foreign | ' || pg_temp.wx_try_cmms_audit_log('move');
ROLLBACK;
SELECT 'cmms_audit_log_rows_restored | ' || ((SELECT count(*) FROM cmms_audit_log) = (SELECT n0 FROM _wx_cmms_audit_log));

CREATE TEMP TABLE _wx_external_sync AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM external_sync x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM external_sync x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM external_sync x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM external_sync) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM external_sync x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_external_sync TO authenticated;
SELECT 'external_sync_fixture | ' || ((SELECT me FROM _wx_external_sync) IS NOT NULL AND (SELECT foreign_row FROM _wx_external_sync) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_external_sync(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE external_sync SET id = id WHERE id = (SELECT foreign_row FROM _wx_external_sync);
  ELSIF op = 'foreign_delete' THEN DELETE FROM external_sync WHERE id = (SELECT foreign_row FROM _wx_external_sync);
  ELSIF op = 'own_update' THEN UPDATE external_sync SET id = id WHERE id = (SELECT own_row FROM _wx_external_sync);
  ELSIF op = 'move' THEN UPDATE external_sync SET hive_id = (SELECT foreign_hive FROM _wx_external_sync) WHERE id = (SELECT own_row FROM _wx_external_sync);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_external_sync)::text, 'role','authenticated')::text, true);
SELECT 'external_sync_foreign_update_touched | ' || pg_temp.wx_try_external_sync('foreign_update');
SELECT 'external_sync_foreign_delete_touched | ' || pg_temp.wx_try_external_sync('foreign_delete');
SELECT 'external_sync_move_into_foreign | ' || pg_temp.wx_try_external_sync('move');
SELECT 'external_sync_own_update_touched_gt0 | ' || (pg_temp.wx_try_external_sync('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'external_sync_rows_restored | ' || ((SELECT count(*) FROM external_sync) = (SELECT n0 FROM _wx_external_sync));

CREATE TEMP TABLE _wx_integration_configs AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM integration_configs x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM integration_configs x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM integration_configs x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM integration_configs) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM integration_configs x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_integration_configs TO authenticated;
SELECT 'integration_configs_fixture | ' || ((SELECT me FROM _wx_integration_configs) IS NOT NULL AND (SELECT foreign_row FROM _wx_integration_configs) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_integration_configs(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE integration_configs SET id = id WHERE id = (SELECT foreign_row FROM _wx_integration_configs);
  ELSIF op = 'foreign_delete' THEN DELETE FROM integration_configs WHERE id = (SELECT foreign_row FROM _wx_integration_configs);
  ELSIF op = 'own_update' THEN UPDATE integration_configs SET id = id WHERE id = (SELECT own_row FROM _wx_integration_configs);
  ELSIF op = 'move' THEN UPDATE integration_configs SET hive_id = (SELECT foreign_hive FROM _wx_integration_configs) WHERE id = (SELECT own_row FROM _wx_integration_configs);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_integration_configs)::text, 'role','authenticated')::text, true);
SELECT 'integration_configs_foreign_update_touched | ' || pg_temp.wx_try_integration_configs('foreign_update');
SELECT 'integration_configs_foreign_delete_touched | ' || pg_temp.wx_try_integration_configs('foreign_delete');
SELECT 'integration_configs_move_into_foreign | ' || pg_temp.wx_try_integration_configs('move');
SELECT 'integration_configs_own_update_touched_gt0 | ' || (pg_temp.wx_try_integration_configs('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'integration_configs_rows_restored | ' || ((SELECT count(*) FROM integration_configs) = (SELECT n0 FROM _wx_integration_configs));

CREATE TEMP TABLE _wx_inventory_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM inventory_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM inventory_items x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM inventory_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM inventory_items) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM inventory_items x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_inventory_items TO authenticated;
SELECT 'inventory_items_fixture | ' || ((SELECT me FROM _wx_inventory_items) IS NOT NULL AND (SELECT foreign_row FROM _wx_inventory_items) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_inventory_items(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE inventory_items SET id = id WHERE id = (SELECT foreign_row FROM _wx_inventory_items);
  ELSIF op = 'foreign_delete' THEN DELETE FROM inventory_items WHERE id = (SELECT foreign_row FROM _wx_inventory_items);
  ELSIF op = 'own_update' THEN UPDATE inventory_items SET id = id WHERE id = (SELECT own_row FROM _wx_inventory_items);
  ELSIF op = 'move' THEN UPDATE inventory_items SET hive_id = (SELECT foreign_hive FROM _wx_inventory_items) WHERE id = (SELECT own_row FROM _wx_inventory_items);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_inventory_items)::text, 'role','authenticated')::text, true);
SELECT 'inventory_items_foreign_update_touched | ' || pg_temp.wx_try_inventory_items('foreign_update');
SELECT 'inventory_items_foreign_delete_touched | ' || pg_temp.wx_try_inventory_items('foreign_delete');
SELECT 'inventory_items_move_into_foreign | ' || pg_temp.wx_try_inventory_items('move');
SELECT 'inventory_items_own_update_touched_gt0 | ' || (pg_temp.wx_try_inventory_items('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'inventory_items_rows_restored | ' || ((SELECT count(*) FROM inventory_items) = (SELECT n0 FROM _wx_inventory_items));

CREATE TEMP TABLE _wx_logbook AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM logbook x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM logbook x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM logbook x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM logbook) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM logbook x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_logbook TO authenticated;
SELECT 'logbook_fixture | ' || ((SELECT me FROM _wx_logbook) IS NOT NULL AND (SELECT foreign_row FROM _wx_logbook) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_logbook(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE logbook SET id = id WHERE id = (SELECT foreign_row FROM _wx_logbook);
  ELSIF op = 'foreign_delete' THEN DELETE FROM logbook WHERE id = (SELECT foreign_row FROM _wx_logbook);
  ELSIF op = 'own_update' THEN UPDATE logbook SET id = id WHERE id = (SELECT own_row FROM _wx_logbook);
  ELSIF op = 'move' THEN UPDATE logbook SET hive_id = (SELECT foreign_hive FROM _wx_logbook) WHERE id = (SELECT own_row FROM _wx_logbook);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_logbook)::text, 'role','authenticated')::text, true);
SELECT 'logbook_foreign_update_touched | ' || pg_temp.wx_try_logbook('foreign_update');
SELECT 'logbook_foreign_delete_touched | ' || pg_temp.wx_try_logbook('foreign_delete');
SELECT 'logbook_move_into_foreign | ' || pg_temp.wx_try_logbook('move');
ROLLBACK;
SELECT 'logbook_rows_restored | ' || ((SELECT count(*) FROM logbook) = (SELECT n0 FROM _wx_logbook));

CREATE TEMP TABLE _wx_pm_assets AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM pm_assets x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM pm_assets x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM pm_assets x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM pm_assets) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM pm_assets x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_pm_assets TO authenticated;
SELECT 'pm_assets_fixture | ' || ((SELECT me FROM _wx_pm_assets) IS NOT NULL AND (SELECT foreign_row FROM _wx_pm_assets) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_pm_assets(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE pm_assets SET id = id WHERE id = (SELECT foreign_row FROM _wx_pm_assets);
  ELSIF op = 'foreign_delete' THEN DELETE FROM pm_assets WHERE id = (SELECT foreign_row FROM _wx_pm_assets);
  ELSIF op = 'own_update' THEN UPDATE pm_assets SET id = id WHERE id = (SELECT own_row FROM _wx_pm_assets);
  ELSIF op = 'move' THEN UPDATE pm_assets SET hive_id = (SELECT foreign_hive FROM _wx_pm_assets) WHERE id = (SELECT own_row FROM _wx_pm_assets);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_pm_assets)::text, 'role','authenticated')::text, true);
SELECT 'pm_assets_foreign_update_touched | ' || pg_temp.wx_try_pm_assets('foreign_update');
SELECT 'pm_assets_foreign_delete_touched | ' || pg_temp.wx_try_pm_assets('foreign_delete');
SELECT 'pm_assets_move_into_foreign | ' || pg_temp.wx_try_pm_assets('move');
SELECT 'pm_assets_own_update_touched_gt0 | ' || (pg_temp.wx_try_pm_assets('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'pm_assets_rows_restored | ' || ((SELECT count(*) FROM pm_assets) = (SELECT n0 FROM _wx_pm_assets));

CREATE TEMP TABLE _wx_pm_scope_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM pm_scope_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM pm_scope_items x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM pm_scope_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM pm_scope_items) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM pm_scope_items x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_pm_scope_items TO authenticated;
SELECT 'pm_scope_items_fixture | ' || ((SELECT me FROM _wx_pm_scope_items) IS NOT NULL AND (SELECT foreign_row FROM _wx_pm_scope_items) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_pm_scope_items(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE pm_scope_items SET id = id WHERE id = (SELECT foreign_row FROM _wx_pm_scope_items);
  ELSIF op = 'foreign_delete' THEN DELETE FROM pm_scope_items WHERE id = (SELECT foreign_row FROM _wx_pm_scope_items);
  ELSIF op = 'own_update' THEN UPDATE pm_scope_items SET id = id WHERE id = (SELECT own_row FROM _wx_pm_scope_items);
  ELSIF op = 'move' THEN UPDATE pm_scope_items SET hive_id = (SELECT foreign_hive FROM _wx_pm_scope_items) WHERE id = (SELECT own_row FROM _wx_pm_scope_items);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_pm_scope_items)::text, 'role','authenticated')::text, true);
SELECT 'pm_scope_items_foreign_update_touched | ' || pg_temp.wx_try_pm_scope_items('foreign_update');
SELECT 'pm_scope_items_foreign_delete_touched | ' || pg_temp.wx_try_pm_scope_items('foreign_delete');
SELECT 'pm_scope_items_move_into_foreign | ' || pg_temp.wx_try_pm_scope_items('move');
SELECT 'pm_scope_items_own_update_touched_gt0 | ' || (pg_temp.wx_try_pm_scope_items('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'pm_scope_items_rows_restored | ' || ((SELECT count(*) FROM pm_scope_items) = (SELECT n0 FROM _wx_pm_scope_items));
