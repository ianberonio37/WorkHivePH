-- write_authz_depth (pm-scheduler, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (hive_audit_log, logbook, pm_assets, pm_completions, pm_scope_items, project_links) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: hive_audit_log_fixture \| t
-- expect: hive_audit_log_foreign_update_touched \| (0\b|refused)
-- expect: hive_audit_log_foreign_delete_touched \| (0\b|refused)
-- expect: hive_audit_log_move_into_foreign \| (0\b|refused)
-- forbid: hive_audit_log_move_into_foreign \| [1-9]
-- expect: hive_audit_log_rows_restored \| t
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
-- expect: pm_completions_fixture \| t
-- expect: pm_completions_foreign_update_touched \| (0\b|refused)
-- expect: pm_completions_foreign_delete_touched \| (0\b|refused)
-- expect: pm_completions_move_into_foreign \| (0\b|refused)
-- forbid: pm_completions_move_into_foreign \| [1-9]
-- expect: pm_completions_rows_restored \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_update_touched \| (0\b|refused)
-- expect: pm_scope_items_foreign_delete_touched \| (0\b|refused)
-- expect: pm_scope_items_own_update_touched_gt0 \| t
-- expect: pm_scope_items_move_into_foreign \| (0\b|refused)
-- forbid: pm_scope_items_move_into_foreign \| [1-9]
-- expect: pm_scope_items_rows_restored \| t
-- expect: project_links_fixture \| t
-- expect: project_links_foreign_update_touched \| (0\b|refused)
-- expect: project_links_foreign_delete_touched \| (0\b|refused)
-- expect: project_links_own_update_touched_gt0 \| t
-- expect: project_links_move_into_foreign \| (0\b|refused)
-- forbid: project_links_move_into_foreign \| [1-9]
-- expect: project_links_rows_restored \| t

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

CREATE TEMP TABLE _wx_pm_completions AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM pm_completions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM pm_completions x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM pm_completions x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM pm_completions) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM pm_completions x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_pm_completions TO authenticated;
SELECT 'pm_completions_fixture | ' || ((SELECT me FROM _wx_pm_completions) IS NOT NULL AND (SELECT foreign_row FROM _wx_pm_completions) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_pm_completions(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE pm_completions SET id = id WHERE id = (SELECT foreign_row FROM _wx_pm_completions);
  ELSIF op = 'foreign_delete' THEN DELETE FROM pm_completions WHERE id = (SELECT foreign_row FROM _wx_pm_completions);
  ELSIF op = 'own_update' THEN UPDATE pm_completions SET id = id WHERE id = (SELECT own_row FROM _wx_pm_completions);
  ELSIF op = 'move' THEN UPDATE pm_completions SET hive_id = (SELECT foreign_hive FROM _wx_pm_completions) WHERE id = (SELECT own_row FROM _wx_pm_completions);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_pm_completions)::text, 'role','authenticated')::text, true);
SELECT 'pm_completions_foreign_update_touched | ' || pg_temp.wx_try_pm_completions('foreign_update');
SELECT 'pm_completions_foreign_delete_touched | ' || pg_temp.wx_try_pm_completions('foreign_delete');
SELECT 'pm_completions_move_into_foreign | ' || pg_temp.wx_try_pm_completions('move');
ROLLBACK;
SELECT 'pm_completions_rows_restored | ' || ((SELECT count(*) FROM pm_completions) = (SELECT n0 FROM _wx_pm_completions));

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
