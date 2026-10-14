-- write_authz_depth (asset-hub, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (asset_nodes, hive_audit_log, parts_staged_reservations, parts_staging_recommendations, pm_scope_items, rcm_fmea_modes, rcm_strategies) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_update_touched \| (0\b|refused)
-- expect: asset_nodes_foreign_delete_touched \| (0\b|refused)
-- expect: asset_nodes_own_update_touched_gt0 \| t
-- expect: asset_nodes_move_into_foreign \| (0\b|refused)
-- forbid: asset_nodes_move_into_foreign \| [1-9]
-- expect: asset_nodes_rows_restored \| t
-- expect: hive_audit_log_fixture \| t
-- expect: hive_audit_log_foreign_update_touched \| (0\b|refused)
-- expect: hive_audit_log_foreign_delete_touched \| (0\b|refused)
-- expect: hive_audit_log_move_into_foreign \| (0\b|refused)
-- forbid: hive_audit_log_move_into_foreign \| [1-9]
-- expect: hive_audit_log_rows_restored \| t
-- expect: parts_staged_reservations_fixture \| t
-- expect: parts_staged_reservations_foreign_update_touched \| (0\b|refused)
-- expect: parts_staged_reservations_foreign_delete_touched \| (0\b|refused)
-- expect: parts_staged_reservations_own_update_touched_gt0 \| t
-- expect: parts_staged_reservations_move_into_foreign \| (0\b|refused)
-- forbid: parts_staged_reservations_move_into_foreign \| [1-9]
-- expect: parts_staged_reservations_rows_restored \| t
-- expect: parts_staging_recommendations_fixture \| t
-- expect: parts_staging_recommendations_foreign_update_touched \| (0\b|refused)
-- expect: parts_staging_recommendations_foreign_delete_touched \| (0\b|refused)
-- expect: parts_staging_recommendations_own_update_touched_gt0 \| t
-- expect: parts_staging_recommendations_move_into_foreign \| (0\b|refused)
-- forbid: parts_staging_recommendations_move_into_foreign \| [1-9]
-- expect: parts_staging_recommendations_rows_restored \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_update_touched \| (0\b|refused)
-- expect: pm_scope_items_foreign_delete_touched \| (0\b|refused)
-- expect: pm_scope_items_own_update_touched_gt0 \| t
-- expect: pm_scope_items_move_into_foreign \| (0\b|refused)
-- forbid: pm_scope_items_move_into_foreign \| [1-9]
-- expect: pm_scope_items_rows_restored \| t
-- expect: rcm_fmea_modes_fixture \| t
-- expect: rcm_fmea_modes_foreign_update_touched \| (0\b|refused)
-- expect: rcm_fmea_modes_foreign_delete_touched \| (0\b|refused)
-- expect: rcm_fmea_modes_own_update_touched_gt0 \| t
-- expect: rcm_fmea_modes_move_into_foreign \| (0\b|refused)
-- forbid: rcm_fmea_modes_move_into_foreign \| [1-9]
-- expect: rcm_fmea_modes_rows_restored \| t
-- expect: rcm_strategies_fixture \| t
-- expect: rcm_strategies_foreign_update_touched \| (0\b|refused)
-- expect: rcm_strategies_foreign_delete_touched \| (0\b|refused)
-- expect: rcm_strategies_own_update_touched_gt0 \| t
-- expect: rcm_strategies_move_into_foreign \| (0\b|refused)
-- forbid: rcm_strategies_move_into_foreign \| [1-9]
-- expect: rcm_strategies_rows_restored \| t

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

CREATE TEMP TABLE _wx_hive_audit_log AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM hive_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM hive_audit_log x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM hive_audit_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM hive_audit_log) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM hive_audit_log x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_hive_audit_log TO authenticated;
SELECT 'hive_audit_log_fixture | ' || ((SELECT me FROM _wx_hive_audit_log) IS NOT NULL AND (SELECT foreign_row FROM _wx_hive_audit_log) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_hive_audit_log(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE hive_audit_log SET id = id WHERE id = (SELECT foreign_row FROM _wx_hive_audit_log);
  ELSIF op = 'foreign_delete' THEN DELETE FROM hive_audit_log WHERE id = (SELECT foreign_row FROM _wx_hive_audit_log);
  ELSIF op = 'own_update' THEN UPDATE hive_audit_log SET id = id WHERE id = (SELECT own_row FROM _wx_hive_audit_log);
  ELSIF op = 'move' THEN UPDATE hive_audit_log SET hive_id = (SELECT foreign_hive FROM _wx_hive_audit_log) WHERE id = (SELECT own_row FROM _wx_hive_audit_log);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_hive_audit_log)::text, 'role','authenticated')::text, true);
SELECT 'hive_audit_log_foreign_update_touched | ' || pg_temp.wx_try_hive_audit_log('foreign_update');
SELECT 'hive_audit_log_foreign_delete_touched | ' || pg_temp.wx_try_hive_audit_log('foreign_delete');
SELECT 'hive_audit_log_move_into_foreign | ' || pg_temp.wx_try_hive_audit_log('move');
ROLLBACK;
SELECT 'hive_audit_log_rows_restored | ' || ((SELECT count(*) FROM hive_audit_log) = (SELECT n0 FROM _wx_hive_audit_log));

CREATE TEMP TABLE _wx_parts_staged_reservations AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM parts_staged_reservations x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM parts_staged_reservations x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM parts_staged_reservations x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM parts_staged_reservations) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM parts_staged_reservations x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_parts_staged_reservations TO authenticated;
SELECT 'parts_staged_reservations_fixture | ' || ((SELECT me FROM _wx_parts_staged_reservations) IS NOT NULL AND (SELECT foreign_row FROM _wx_parts_staged_reservations) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_parts_staged_reservations(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE parts_staged_reservations SET id = id WHERE id = (SELECT foreign_row FROM _wx_parts_staged_reservations);
  ELSIF op = 'foreign_delete' THEN DELETE FROM parts_staged_reservations WHERE id = (SELECT foreign_row FROM _wx_parts_staged_reservations);
  ELSIF op = 'own_update' THEN UPDATE parts_staged_reservations SET id = id WHERE id = (SELECT own_row FROM _wx_parts_staged_reservations);
  ELSIF op = 'move' THEN UPDATE parts_staged_reservations SET hive_id = (SELECT foreign_hive FROM _wx_parts_staged_reservations) WHERE id = (SELECT own_row FROM _wx_parts_staged_reservations);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_parts_staged_reservations)::text, 'role','authenticated')::text, true);
SELECT 'parts_staged_reservations_foreign_update_touched | ' || pg_temp.wx_try_parts_staged_reservations('foreign_update');
SELECT 'parts_staged_reservations_foreign_delete_touched | ' || pg_temp.wx_try_parts_staged_reservations('foreign_delete');
SELECT 'parts_staged_reservations_move_into_foreign | ' || pg_temp.wx_try_parts_staged_reservations('move');
SELECT 'parts_staged_reservations_own_update_touched_gt0 | ' || (pg_temp.wx_try_parts_staged_reservations('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'parts_staged_reservations_rows_restored | ' || ((SELECT count(*) FROM parts_staged_reservations) = (SELECT n0 FROM _wx_parts_staged_reservations));

CREATE TEMP TABLE _wx_parts_staging_recommendations AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM parts_staging_recommendations x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM parts_staging_recommendations x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM parts_staging_recommendations x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM parts_staging_recommendations) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM parts_staging_recommendations x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_parts_staging_recommendations TO authenticated;
SELECT 'parts_staging_recommendations_fixture | ' || ((SELECT me FROM _wx_parts_staging_recommendations) IS NOT NULL AND (SELECT foreign_row FROM _wx_parts_staging_recommendations) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_parts_staging_recommendations(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE parts_staging_recommendations SET id = id WHERE id = (SELECT foreign_row FROM _wx_parts_staging_recommendations);
  ELSIF op = 'foreign_delete' THEN DELETE FROM parts_staging_recommendations WHERE id = (SELECT foreign_row FROM _wx_parts_staging_recommendations);
  ELSIF op = 'own_update' THEN UPDATE parts_staging_recommendations SET id = id WHERE id = (SELECT own_row FROM _wx_parts_staging_recommendations);
  ELSIF op = 'move' THEN UPDATE parts_staging_recommendations SET hive_id = (SELECT foreign_hive FROM _wx_parts_staging_recommendations) WHERE id = (SELECT own_row FROM _wx_parts_staging_recommendations);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_parts_staging_recommendations)::text, 'role','authenticated')::text, true);
SELECT 'parts_staging_recommendations_foreign_update_touched | ' || pg_temp.wx_try_parts_staging_recommendations('foreign_update');
SELECT 'parts_staging_recommendations_foreign_delete_touched | ' || pg_temp.wx_try_parts_staging_recommendations('foreign_delete');
SELECT 'parts_staging_recommendations_move_into_foreign | ' || pg_temp.wx_try_parts_staging_recommendations('move');
SELECT 'parts_staging_recommendations_own_update_touched_gt0 | ' || (pg_temp.wx_try_parts_staging_recommendations('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'parts_staging_recommendations_rows_restored | ' || ((SELECT count(*) FROM parts_staging_recommendations) = (SELECT n0 FROM _wx_parts_staging_recommendations));

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

CREATE TEMP TABLE _wx_rcm_fmea_modes AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM rcm_fmea_modes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM rcm_fmea_modes x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM rcm_fmea_modes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM rcm_fmea_modes) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM rcm_fmea_modes x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_rcm_fmea_modes TO authenticated;
SELECT 'rcm_fmea_modes_fixture | ' || ((SELECT me FROM _wx_rcm_fmea_modes) IS NOT NULL AND (SELECT foreign_row FROM _wx_rcm_fmea_modes) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_rcm_fmea_modes(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE rcm_fmea_modes SET id = id WHERE id = (SELECT foreign_row FROM _wx_rcm_fmea_modes);
  ELSIF op = 'foreign_delete' THEN DELETE FROM rcm_fmea_modes WHERE id = (SELECT foreign_row FROM _wx_rcm_fmea_modes);
  ELSIF op = 'own_update' THEN UPDATE rcm_fmea_modes SET id = id WHERE id = (SELECT own_row FROM _wx_rcm_fmea_modes);
  ELSIF op = 'move' THEN UPDATE rcm_fmea_modes SET hive_id = (SELECT foreign_hive FROM _wx_rcm_fmea_modes) WHERE id = (SELECT own_row FROM _wx_rcm_fmea_modes);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_rcm_fmea_modes)::text, 'role','authenticated')::text, true);
SELECT 'rcm_fmea_modes_foreign_update_touched | ' || pg_temp.wx_try_rcm_fmea_modes('foreign_update');
SELECT 'rcm_fmea_modes_foreign_delete_touched | ' || pg_temp.wx_try_rcm_fmea_modes('foreign_delete');
SELECT 'rcm_fmea_modes_move_into_foreign | ' || pg_temp.wx_try_rcm_fmea_modes('move');
SELECT 'rcm_fmea_modes_own_update_touched_gt0 | ' || (pg_temp.wx_try_rcm_fmea_modes('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'rcm_fmea_modes_rows_restored | ' || ((SELECT count(*) FROM rcm_fmea_modes) = (SELECT n0 FROM _wx_rcm_fmea_modes));

CREATE TEMP TABLE _wx_rcm_strategies AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM rcm_strategies x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM rcm_strategies x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM rcm_strategies x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM rcm_strategies) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM rcm_strategies x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_rcm_strategies TO authenticated;
SELECT 'rcm_strategies_fixture | ' || ((SELECT me FROM _wx_rcm_strategies) IS NOT NULL AND (SELECT foreign_row FROM _wx_rcm_strategies) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_rcm_strategies(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE rcm_strategies SET id = id WHERE id = (SELECT foreign_row FROM _wx_rcm_strategies);
  ELSIF op = 'foreign_delete' THEN DELETE FROM rcm_strategies WHERE id = (SELECT foreign_row FROM _wx_rcm_strategies);
  ELSIF op = 'own_update' THEN UPDATE rcm_strategies SET id = id WHERE id = (SELECT own_row FROM _wx_rcm_strategies);
  ELSIF op = 'move' THEN UPDATE rcm_strategies SET hive_id = (SELECT foreign_hive FROM _wx_rcm_strategies) WHERE id = (SELECT own_row FROM _wx_rcm_strategies);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_rcm_strategies)::text, 'role','authenticated')::text, true);
SELECT 'rcm_strategies_foreign_update_touched | ' || pg_temp.wx_try_rcm_strategies('foreign_update');
SELECT 'rcm_strategies_foreign_delete_touched | ' || pg_temp.wx_try_rcm_strategies('foreign_delete');
SELECT 'rcm_strategies_move_into_foreign | ' || pg_temp.wx_try_rcm_strategies('move');
SELECT 'rcm_strategies_own_update_touched_gt0 | ' || (pg_temp.wx_try_rcm_strategies('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'rcm_strategies_rows_restored | ' || ((SELECT count(*) FROM rcm_strategies) = (SELECT n0 FROM _wx_rcm_strategies));
