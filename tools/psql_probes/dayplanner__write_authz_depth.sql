-- write_authz_depth (dayplanner, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (logbook) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_update_touched \| 0
-- expect: logbook_foreign_delete_touched \| 0
-- expect: logbook_rows_restored \| t

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
