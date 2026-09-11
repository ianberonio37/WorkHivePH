-- write_authz_depth (logbook, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (logbook, pm_completions, project_links, asset_nodes) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_update_touched \| 0
-- expect: logbook_foreign_delete_touched \| 0
-- expect: logbook_rows_restored \| t
-- expect: pm_completions_fixture \| t
-- expect: pm_completions_foreign_update_touched \| 0
-- expect: pm_completions_foreign_delete_touched \| 0
-- expect: pm_completions_rows_restored \| t
-- expect: project_links_fixture \| t
-- expect: project_links_foreign_update_touched \| 0
-- expect: project_links_foreign_delete_touched \| 0
-- expect: project_links_own_update_touched_gt0 \| t
-- expect: project_links_rows_restored \| t
-- expect: asset_nodes_fixture \| t
-- expect: asset_nodes_foreign_update_touched \| 0
-- expect: asset_nodes_foreign_delete_touched \| 0
-- expect: asset_nodes_own_update_touched_gt0 \| t
-- expect: asset_nodes_rows_restored \| t

CREATE TEMP TABLE _wx_logbook AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM logbook x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM logbook x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT count(*) FROM logbook) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM logbook x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a JOIN worker_profiles wp ON wp.display_name = a.worker_name WHERE wp.auth_uid = m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_logbook TO authenticated;
SELECT 'logbook_fixture | ' || ((SELECT me FROM _wx_logbook) IS NOT NULL AND (SELECT foreign_row FROM _wx_logbook) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_logbook)::text, 'role','authenticated')::text, true);
WITH u AS (UPDATE logbook SET id = id WHERE id = (SELECT foreign_row FROM _wx_logbook) RETURNING 1)
SELECT 'logbook_foreign_update_touched | ' || count(*) FROM u;
WITH d AS (DELETE FROM logbook WHERE id = (SELECT foreign_row FROM _wx_logbook) RETURNING 1)
SELECT 'logbook_foreign_delete_touched | ' || count(*) FROM d;
ROLLBACK;
SELECT 'logbook_rows_restored | ' || ((SELECT count(*) FROM logbook) = (SELECT n0 FROM _wx_logbook));

CREATE TEMP TABLE _wx_pm_completions AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM pm_completions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM pm_completions x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT count(*) FROM pm_completions) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM pm_completions x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a JOIN worker_profiles wp ON wp.display_name = a.worker_name WHERE wp.auth_uid = m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_pm_completions TO authenticated;
SELECT 'pm_completions_fixture | ' || ((SELECT me FROM _wx_pm_completions) IS NOT NULL AND (SELECT foreign_row FROM _wx_pm_completions) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_pm_completions)::text, 'role','authenticated')::text, true);
WITH u AS (UPDATE pm_completions SET id = id WHERE id = (SELECT foreign_row FROM _wx_pm_completions) RETURNING 1)
SELECT 'pm_completions_foreign_update_touched | ' || count(*) FROM u;
WITH d AS (DELETE FROM pm_completions WHERE id = (SELECT foreign_row FROM _wx_pm_completions) RETURNING 1)
SELECT 'pm_completions_foreign_delete_touched | ' || count(*) FROM d;
ROLLBACK;
SELECT 'pm_completions_rows_restored | ' || ((SELECT count(*) FROM pm_completions) = (SELECT n0 FROM _wx_pm_completions));

CREATE TEMP TABLE _wx_project_links AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM project_links x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM project_links x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT count(*) FROM project_links) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM project_links x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a JOIN worker_profiles wp ON wp.display_name = a.worker_name WHERE wp.auth_uid = m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_project_links TO authenticated;
SELECT 'project_links_fixture | ' || ((SELECT me FROM _wx_project_links) IS NOT NULL AND (SELECT foreign_row FROM _wx_project_links) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_project_links)::text, 'role','authenticated')::text, true);
WITH u AS (UPDATE project_links SET id = id WHERE id = (SELECT foreign_row FROM _wx_project_links) RETURNING 1)
SELECT 'project_links_foreign_update_touched | ' || count(*) FROM u;
WITH d AS (DELETE FROM project_links WHERE id = (SELECT foreign_row FROM _wx_project_links) RETURNING 1)
SELECT 'project_links_foreign_delete_touched | ' || count(*) FROM d;
WITH o AS (UPDATE project_links SET id = id WHERE id = (SELECT own_row FROM _wx_project_links) RETURNING 1)
SELECT 'project_links_own_update_touched_gt0 | ' || (count(*) > 0) FROM o;
ROLLBACK;
SELECT 'project_links_rows_restored | ' || ((SELECT count(*) FROM project_links) = (SELECT n0 FROM _wx_project_links));

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
