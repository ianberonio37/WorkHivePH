-- write_authz_depth (hive, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (hive_audit_log, hive_members, logbook) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: hive_audit_log_fixture \| t
-- expect: hive_audit_log_foreign_update_touched \| (0\b|refused)
-- expect: hive_audit_log_foreign_delete_touched \| (0\b|refused)
-- expect: hive_audit_log_move_into_foreign \| (0\b|refused)
-- forbid: hive_audit_log_move_into_foreign \| [1-9]
-- expect: hive_audit_log_rows_restored \| t
-- expect: hive_members_fixture \| t
-- expect: hive_members_foreign_update_touched \| (0\b|refused)
-- expect: hive_members_foreign_delete_touched \| (0\b|refused)
-- expect: hive_members_move_into_foreign \| (0\b|refused)
-- forbid: hive_members_move_into_foreign \| [1-9]
-- expect: hive_members_rows_restored \| t
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_update_touched \| (0\b|refused)
-- expect: logbook_foreign_delete_touched \| (0\b|refused)
-- expect: logbook_move_into_foreign \| (0\b|refused)
-- forbid: logbook_move_into_foreign \| [1-9]
-- expect: logbook_rows_restored \| t

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

CREATE TEMP TABLE _wx_hive_members AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM hive_members x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM hive_members x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT x.hive_id FROM hive_members x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_hive,
       (SELECT count(*) FROM hive_members) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM hive_members x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a WHERE a.auth_uid = m.auth_uid)   -- by account, never by display name
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_hive_members TO authenticated;
SELECT 'hive_members_fixture | ' || ((SELECT me FROM _wx_hive_members) IS NOT NULL AND (SELECT foreign_row FROM _wx_hive_members) IS NOT NULL);
-- every write probe runs through ONE exception-safe function (2026-10-14): a refused write (42501, a missing grant, a
-- guard trigger) returns 'refused <SQLSTATE>' instead of aborting the rolled-back transaction and every probe after it
CREATE FUNCTION pg_temp.wx_try_hive_members(op text) RETURNS text LANGUAGE plpgsql AS $wx$
DECLARE n int;
BEGIN
  IF op = 'foreign_update' THEN UPDATE hive_members SET id = id WHERE id = (SELECT foreign_row FROM _wx_hive_members);
  ELSIF op = 'foreign_delete' THEN DELETE FROM hive_members WHERE id = (SELECT foreign_row FROM _wx_hive_members);
  ELSIF op = 'own_update' THEN UPDATE hive_members SET id = id WHERE id = (SELECT own_row FROM _wx_hive_members);
  ELSIF op = 'move' THEN UPDATE hive_members SET hive_id = (SELECT foreign_hive FROM _wx_hive_members) WHERE id = (SELECT own_row FROM _wx_hive_members);
  END IF;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n::text;
EXCEPTION WHEN insufficient_privilege THEN RETURN 'refused 42501';
  WHEN others THEN RETURN 'refused ' || SQLSTATE;
END $wx$;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_hive_members)::text, 'role','authenticated')::text, true);
SELECT 'hive_members_foreign_update_touched | ' || pg_temp.wx_try_hive_members('foreign_update');
SELECT 'hive_members_foreign_delete_touched | ' || pg_temp.wx_try_hive_members('foreign_delete');
SELECT 'hive_members_move_into_foreign | ' || pg_temp.wx_try_hive_members('move');
ROLLBACK;
SELECT 'hive_members_rows_restored | ' || ((SELECT count(*) FROM hive_members) = (SELECT n0 FROM _wx_hive_members));

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
