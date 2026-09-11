-- write_authz_depth (asset-hub, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (asset_nodes, pm_scope_items, rcm_fmea_modes, parts_staged_reservations) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_update_touched \| 0
-- expect: asset_nodes_foreign_delete_touched \| 0
-- expect: asset_nodes_own_update_touched_gt0 \| t
-- expect: asset_nodes_rows_restored \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_update_touched \| 0
-- expect: pm_scope_items_foreign_delete_touched \| 0
-- expect: pm_scope_items_own_update_touched_gt0 \| t
-- expect: pm_scope_items_rows_restored \| t
-- expect: rcm_fmea_modes_fixture \| t
-- expect: rcm_fmea_modes_foreign_update_touched \| 0
-- expect: rcm_fmea_modes_foreign_delete_touched \| 0
-- expect: rcm_fmea_modes_own_update_touched_gt0 \| t
-- expect: rcm_fmea_modes_rows_restored \| t
-- expect: parts_staged_reservations_fixture \| t
-- expect: parts_staged_reservations_foreign_update_touched \| 0
-- expect: parts_staged_reservations_foreign_delete_touched \| 0
-- expect: parts_staged_reservations_own_update_touched_gt0 \| t
-- expect: parts_staged_reservations_rows_restored \| t

CREATE TEMP TABLE _wx_asset_nodes AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM asset_nodes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM asset_nodes x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT count(*) FROM asset_nodes) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM asset_nodes x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a JOIN worker_profiles wp ON wp.display_name = a.worker_name WHERE wp.auth_uid = m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_asset_nodes TO authenticated;
SELECT 'asset_nodes_fixture | ' || ((SELECT me FROM _wx_asset_nodes) IS NOT NULL AND (SELECT foreign_row FROM _wx_asset_nodes) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_asset_nodes)::text, 'role','authenticated')::text, true);
WITH u AS (UPDATE asset_nodes SET id = id WHERE id = (SELECT foreign_row FROM _wx_asset_nodes) RETURNING 1)
SELECT 'asset_nodes_foreign_update_touched | ' || count(*) FROM u;
WITH d AS (DELETE FROM asset_nodes WHERE id = (SELECT foreign_row FROM _wx_asset_nodes) RETURNING 1)
SELECT 'asset_nodes_foreign_delete_touched | ' || count(*) FROM d;
WITH o AS (UPDATE asset_nodes SET id = id WHERE id = (SELECT own_row FROM _wx_asset_nodes) RETURNING 1)
SELECT 'asset_nodes_own_update_touched_gt0 | ' || (count(*) > 0) FROM o;
ROLLBACK;
SELECT 'asset_nodes_rows_restored | ' || ((SELECT count(*) FROM asset_nodes) = (SELECT n0 FROM _wx_asset_nodes));

CREATE TEMP TABLE _wx_pm_scope_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM pm_scope_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM pm_scope_items x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT count(*) FROM pm_scope_items) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM pm_scope_items x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a JOIN worker_profiles wp ON wp.display_name = a.worker_name WHERE wp.auth_uid = m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_pm_scope_items TO authenticated;
SELECT 'pm_scope_items_fixture | ' || ((SELECT me FROM _wx_pm_scope_items) IS NOT NULL AND (SELECT foreign_row FROM _wx_pm_scope_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_pm_scope_items)::text, 'role','authenticated')::text, true);
WITH u AS (UPDATE pm_scope_items SET id = id WHERE id = (SELECT foreign_row FROM _wx_pm_scope_items) RETURNING 1)
SELECT 'pm_scope_items_foreign_update_touched | ' || count(*) FROM u;
WITH d AS (DELETE FROM pm_scope_items WHERE id = (SELECT foreign_row FROM _wx_pm_scope_items) RETURNING 1)
SELECT 'pm_scope_items_foreign_delete_touched | ' || count(*) FROM d;
WITH o AS (UPDATE pm_scope_items SET id = id WHERE id = (SELECT own_row FROM _wx_pm_scope_items) RETURNING 1)
SELECT 'pm_scope_items_own_update_touched_gt0 | ' || (count(*) > 0) FROM o;
ROLLBACK;
SELECT 'pm_scope_items_rows_restored | ' || ((SELECT count(*) FROM pm_scope_items) = (SELECT n0 FROM _wx_pm_scope_items));

CREATE TEMP TABLE _wx_rcm_fmea_modes AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM rcm_fmea_modes x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM rcm_fmea_modes x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT count(*) FROM rcm_fmea_modes) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM rcm_fmea_modes x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a JOIN worker_profiles wp ON wp.display_name = a.worker_name WHERE wp.auth_uid = m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_rcm_fmea_modes TO authenticated;
SELECT 'rcm_fmea_modes_fixture | ' || ((SELECT me FROM _wx_rcm_fmea_modes) IS NOT NULL AND (SELECT foreign_row FROM _wx_rcm_fmea_modes) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_rcm_fmea_modes)::text, 'role','authenticated')::text, true);
WITH u AS (UPDATE rcm_fmea_modes SET id = id WHERE id = (SELECT foreign_row FROM _wx_rcm_fmea_modes) RETURNING 1)
SELECT 'rcm_fmea_modes_foreign_update_touched | ' || count(*) FROM u;
WITH d AS (DELETE FROM rcm_fmea_modes WHERE id = (SELECT foreign_row FROM _wx_rcm_fmea_modes) RETURNING 1)
SELECT 'rcm_fmea_modes_foreign_delete_touched | ' || count(*) FROM d;
WITH o AS (UPDATE rcm_fmea_modes SET id = id WHERE id = (SELECT own_row FROM _wx_rcm_fmea_modes) RETURNING 1)
SELECT 'rcm_fmea_modes_own_update_touched_gt0 | ' || (count(*) > 0) FROM o;
ROLLBACK;
SELECT 'rcm_fmea_modes_rows_restored | ' || ((SELECT count(*) FROM rcm_fmea_modes) = (SELECT n0 FROM _wx_rcm_fmea_modes));

CREATE TEMP TABLE _wx_parts_staged_reservations AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM parts_staged_reservations x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM parts_staged_reservations x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT count(*) FROM parts_staged_reservations) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM parts_staged_reservations x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a JOIN worker_profiles wp ON wp.display_name = a.worker_name WHERE wp.auth_uid = m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_parts_staged_reservations TO authenticated;
SELECT 'parts_staged_reservations_fixture | ' || ((SELECT me FROM _wx_parts_staged_reservations) IS NOT NULL AND (SELECT foreign_row FROM _wx_parts_staged_reservations) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_parts_staged_reservations)::text, 'role','authenticated')::text, true);
WITH u AS (UPDATE parts_staged_reservations SET id = id WHERE id = (SELECT foreign_row FROM _wx_parts_staged_reservations) RETURNING 1)
SELECT 'parts_staged_reservations_foreign_update_touched | ' || count(*) FROM u;
WITH d AS (DELETE FROM parts_staged_reservations WHERE id = (SELECT foreign_row FROM _wx_parts_staged_reservations) RETURNING 1)
SELECT 'parts_staged_reservations_foreign_delete_touched | ' || count(*) FROM d;
WITH o AS (UPDATE parts_staged_reservations SET id = id WHERE id = (SELECT own_row FROM _wx_parts_staged_reservations) RETURNING 1)
SELECT 'parts_staged_reservations_own_update_touched_gt0 | ' || (count(*) > 0) FROM o;
ROLLBACK;
SELECT 'parts_staged_reservations_rows_restored | ' || ((SELECT count(*) FROM parts_staged_reservations) = (SELECT n0 FROM _wx_parts_staged_reservations));
