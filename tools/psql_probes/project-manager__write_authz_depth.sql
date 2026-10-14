-- write_authz_depth (project-manager, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (project_change_orders, project_items, project_links, project_progress_logs, project_roles, projects) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: project_change_orders_fixture \| t
-- expect: project_change_orders_foreign_update_touched \| (0\b|refused)
-- expect: project_change_orders_foreign_delete_touched \| (0\b|refused)
-- expect: project_change_orders_own_update_touched_gt0 \| t
-- expect: project_change_orders_move_into_foreign \| (0\b|refused)
-- forbid: project_change_orders_move_into_foreign \| [1-9]
-- expect: project_change_orders_rows_restored \| t
-- expect: project_items_fixture \| t
-- expect: project_items_foreign_update_touched \| (0\b|refused)
-- expect: project_items_foreign_delete_touched \| (0\b|refused)
-- expect: project_items_own_update_touched_gt0 \| t
-- expect: project_items_move_into_foreign \| (0\b|refused)
-- forbid: project_items_move_into_foreign \| [1-9]
-- expect: project_items_rows_restored \| t
-- expect: project_links_fixture \| t
-- expect: project_links_foreign_update_touched \| (0\b|refused)
-- expect: project_links_foreign_delete_touched \| (0\b|refused)
-- expect: project_links_own_update_touched_gt0 \| t
-- expect: project_links_move_into_foreign \| (0\b|refused)
-- forbid: project_links_move_into_foreign \| [1-9]
-- expect: project_links_rows_restored \| t
-- expect: project_progress_logs_fixture \| t
-- expect: project_progress_logs_foreign_update_touched \| (0\b|refused)
-- expect: project_progress_logs_foreign_delete_touched \| (0\b|refused)
-- expect: project_progress_logs_own_update_touched_gt0 \| t
-- expect: project_progress_logs_move_into_foreign \| (0\b|refused)
-- forbid: project_progress_logs_move_into_foreign \| [1-9]
-- expect: project_progress_logs_rows_restored \| t
-- expect: project_roles_fixture \| t
-- expect: project_roles_foreign_update_touched \| (0\b|refused)
-- expect: project_roles_foreign_delete_touched \| (0\b|refused)
-- expect: project_roles_own_update_touched_gt0 \| t
-- expect: project_roles_move_into_foreign \| (0\b|refused)
-- forbid: project_roles_move_into_foreign \| [1-9]
-- expect: project_roles_rows_restored \| t
-- expect: projects_fixture \| t
-- expect: projects_foreign_update_touched \| (0\b|refused)
-- expect: projects_foreign_delete_touched \| (0\b|refused)
-- expect: projects_move_into_foreign \| (0\b|refused)
-- forbid: projects_move_into_foreign \| [1-9]
-- expect: projects_rows_restored \| t

CREATE TEMP TABLE _wx_project_change_orders AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM project_change_orders x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM project_change_orders x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM project_change_orders x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM project_change_orders) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM project_change_orders x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_project_change_orders TO authenticated;
SELECT 'project_change_orders_fixture | ' || ((SELECT me FROM _wx_project_change_orders) IS NOT NULL AND (SELECT foreign_row FROM _wx_project_change_orders) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_project_change_orders(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE project_change_orders SET id = id WHERE id = (SELECT foreign_row FROM _wx_project_change_orders);
  ELSIF op = 'foreign_delete' THEN DELETE FROM project_change_orders WHERE id = (SELECT foreign_row FROM _wx_project_change_orders);
  ELSIF op = 'own_update' THEN UPDATE project_change_orders SET id = id WHERE id = (SELECT own_row FROM _wx_project_change_orders);
  ELSIF op = 'move' THEN UPDATE project_change_orders SET hive_id = (SELECT foreign_hive FROM _wx_project_change_orders) WHERE id = (SELECT own_row FROM _wx_project_change_orders);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_project_change_orders)::text, 'role','authenticated')::text, true);
SELECT 'project_change_orders_foreign_update_touched | ' || pg_temp.wx_try_project_change_orders('foreign_update');
SELECT 'project_change_orders_foreign_delete_touched | ' || pg_temp.wx_try_project_change_orders('foreign_delete');
SELECT 'project_change_orders_move_into_foreign | ' || pg_temp.wx_try_project_change_orders('move');
SELECT 'project_change_orders_own_update_touched_gt0 | ' || (pg_temp.wx_try_project_change_orders('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'project_change_orders_rows_restored | ' || ((SELECT count(*) FROM project_change_orders) = (SELECT n0 FROM _wx_project_change_orders));

CREATE TEMP TABLE _wx_project_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM project_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM project_items x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM project_items x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM project_items) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM project_items x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_project_items TO authenticated;
SELECT 'project_items_fixture | ' || ((SELECT me FROM _wx_project_items) IS NOT NULL AND (SELECT foreign_row FROM _wx_project_items) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_project_items(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE project_items SET id = id WHERE id = (SELECT foreign_row FROM _wx_project_items);
  ELSIF op = 'foreign_delete' THEN DELETE FROM project_items WHERE id = (SELECT foreign_row FROM _wx_project_items);
  ELSIF op = 'own_update' THEN UPDATE project_items SET id = id WHERE id = (SELECT own_row FROM _wx_project_items);
  ELSIF op = 'move' THEN UPDATE project_items SET hive_id = (SELECT foreign_hive FROM _wx_project_items) WHERE id = (SELECT own_row FROM _wx_project_items);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_project_items)::text, 'role','authenticated')::text, true);
SELECT 'project_items_foreign_update_touched | ' || pg_temp.wx_try_project_items('foreign_update');
SELECT 'project_items_foreign_delete_touched | ' || pg_temp.wx_try_project_items('foreign_delete');
SELECT 'project_items_move_into_foreign | ' || pg_temp.wx_try_project_items('move');
SELECT 'project_items_own_update_touched_gt0 | ' || (pg_temp.wx_try_project_items('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'project_items_rows_restored | ' || ((SELECT count(*) FROM project_items) = (SELECT n0 FROM _wx_project_items));

CREATE TEMP TABLE _wx_project_links AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM project_links x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM project_links x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM project_links x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM project_links) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM project_links x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_project_links TO authenticated;
SELECT 'project_links_fixture | ' || ((SELECT me FROM _wx_project_links) IS NOT NULL AND (SELECT foreign_row FROM _wx_project_links) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_project_links(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE project_links SET id = id WHERE id = (SELECT foreign_row FROM _wx_project_links);
  ELSIF op = 'foreign_delete' THEN DELETE FROM project_links WHERE id = (SELECT foreign_row FROM _wx_project_links);
  ELSIF op = 'own_update' THEN UPDATE project_links SET id = id WHERE id = (SELECT own_row FROM _wx_project_links);
  ELSIF op = 'move' THEN UPDATE project_links SET hive_id = (SELECT foreign_hive FROM _wx_project_links) WHERE id = (SELECT own_row FROM _wx_project_links);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_project_links)::text, 'role','authenticated')::text, true);
SELECT 'project_links_foreign_update_touched | ' || pg_temp.wx_try_project_links('foreign_update');
SELECT 'project_links_foreign_delete_touched | ' || pg_temp.wx_try_project_links('foreign_delete');
SELECT 'project_links_move_into_foreign | ' || pg_temp.wx_try_project_links('move');
SELECT 'project_links_own_update_touched_gt0 | ' || (pg_temp.wx_try_project_links('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'project_links_rows_restored | ' || ((SELECT count(*) FROM project_links) = (SELECT n0 FROM _wx_project_links));

CREATE TEMP TABLE _wx_project_progress_logs AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM project_progress_logs x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM project_progress_logs x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM project_progress_logs x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM project_progress_logs) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM project_progress_logs x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_project_progress_logs TO authenticated;
SELECT 'project_progress_logs_fixture | ' || ((SELECT me FROM _wx_project_progress_logs) IS NOT NULL AND (SELECT foreign_row FROM _wx_project_progress_logs) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_project_progress_logs(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE project_progress_logs SET id = id WHERE id = (SELECT foreign_row FROM _wx_project_progress_logs);
  ELSIF op = 'foreign_delete' THEN DELETE FROM project_progress_logs WHERE id = (SELECT foreign_row FROM _wx_project_progress_logs);
  ELSIF op = 'own_update' THEN UPDATE project_progress_logs SET id = id WHERE id = (SELECT own_row FROM _wx_project_progress_logs);
  ELSIF op = 'move' THEN UPDATE project_progress_logs SET hive_id = (SELECT foreign_hive FROM _wx_project_progress_logs) WHERE id = (SELECT own_row FROM _wx_project_progress_logs);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_project_progress_logs)::text, 'role','authenticated')::text, true);
SELECT 'project_progress_logs_foreign_update_touched | ' || pg_temp.wx_try_project_progress_logs('foreign_update');
SELECT 'project_progress_logs_foreign_delete_touched | ' || pg_temp.wx_try_project_progress_logs('foreign_delete');
SELECT 'project_progress_logs_move_into_foreign | ' || pg_temp.wx_try_project_progress_logs('move');
SELECT 'project_progress_logs_own_update_touched_gt0 | ' || (pg_temp.wx_try_project_progress_logs('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'project_progress_logs_rows_restored | ' || ((SELECT count(*) FROM project_progress_logs) = (SELECT n0 FROM _wx_project_progress_logs));

CREATE TEMP TABLE _wx_project_roles AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM project_roles x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM project_roles x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM project_roles x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM project_roles) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM project_roles x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_project_roles TO authenticated;
SELECT 'project_roles_fixture | ' || ((SELECT me FROM _wx_project_roles) IS NOT NULL AND (SELECT foreign_row FROM _wx_project_roles) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_project_roles(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE project_roles SET id = id WHERE id = (SELECT foreign_row FROM _wx_project_roles);
  ELSIF op = 'foreign_delete' THEN DELETE FROM project_roles WHERE id = (SELECT foreign_row FROM _wx_project_roles);
  ELSIF op = 'own_update' THEN UPDATE project_roles SET id = id WHERE id = (SELECT own_row FROM _wx_project_roles);
  ELSIF op = 'move' THEN UPDATE project_roles SET hive_id = (SELECT foreign_hive FROM _wx_project_roles) WHERE id = (SELECT own_row FROM _wx_project_roles);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_project_roles)::text, 'role','authenticated')::text, true);
SELECT 'project_roles_foreign_update_touched | ' || pg_temp.wx_try_project_roles('foreign_update');
SELECT 'project_roles_foreign_delete_touched | ' || pg_temp.wx_try_project_roles('foreign_delete');
SELECT 'project_roles_move_into_foreign | ' || pg_temp.wx_try_project_roles('move');
SELECT 'project_roles_own_update_touched_gt0 | ' || (pg_temp.wx_try_project_roles('own_update') ~ '^[1-9]');
ROLLBACK;
SELECT 'project_roles_rows_restored | ' || ((SELECT count(*) FROM project_roles) = (SELECT n0 FROM _wx_project_roles));

CREATE TEMP TABLE _wx_projects AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM projects x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM projects x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM projects x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM projects) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM projects x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_projects TO authenticated;
SELECT 'projects_fixture | ' || ((SELECT me FROM _wx_projects) IS NOT NULL AND (SELECT foreign_row FROM _wx_projects) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_projects(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE projects SET id = id WHERE id = (SELECT foreign_row FROM _wx_projects);
  ELSIF op = 'foreign_delete' THEN DELETE FROM projects WHERE id = (SELECT foreign_row FROM _wx_projects);
  ELSIF op = 'own_update' THEN UPDATE projects SET id = id WHERE id = (SELECT own_row FROM _wx_projects);
  ELSIF op = 'move' THEN UPDATE projects SET hive_id = (SELECT foreign_hive FROM _wx_projects) WHERE id = (SELECT own_row FROM _wx_projects);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_projects)::text, 'role','authenticated')::text, true);
SELECT 'projects_foreign_update_touched | ' || pg_temp.wx_try_projects('foreign_update');
SELECT 'projects_foreign_delete_touched | ' || pg_temp.wx_try_projects('foreign_delete');
SELECT 'projects_move_into_foreign | ' || pg_temp.wx_try_projects('move');
ROLLBACK;
SELECT 'projects_rows_restored | ' || ((SELECT count(*) FROM projects) = (SELECT n0 FROM _wx_projects));
