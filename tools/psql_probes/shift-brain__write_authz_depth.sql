-- write_authz_depth (shift-brain, P-B, generated 2026-09-05 by tools/gen_write_authz_recipes.py): the hive-scoped
-- tables this page WRITES (shift_plans) must refuse a foreign hive in the DATABASE. A USING clause on
-- UPDATE/DELETE filters, so a no-op UPDATE (pk = pk) and a DELETE on a foreign hive's row must touch 0 rows; the
-- own-hive control must touch >= 1 where the write policy is hive-member ALL (owner/supervisor-scoped tables keep
-- only the refusal half and say so). Everything runs inside a rolled-back transaction; counts are re-checked after.
-- expect: shift_plans_fixture \| t
-- expect: shift_plans_foreign_update_touched \| 0
-- expect: shift_plans_foreign_delete_touched \| 0
-- expect: shift_plans_own_update_touched_gt0 \| t
-- expect: shift_plans_rows_restored \| t

CREATE TEMP TABLE _wx_shift_plans AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM shift_plans x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        LIMIT 1) AS foreign_row,
       (SELECT x.id FROM shift_plans x WHERE x.hive_id = m.hive_id LIMIT 1) AS own_row,
       (SELECT count(*) FROM shift_plans) AS n0
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM shift_plans x WHERE x.hive_id = m.hive_id)
  -- a marketplace/platform admin may write across hives BY DESIGN (is_marketplace_admin()); the refusal is proved for a plain member
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins a JOIN worker_profiles wp ON wp.display_name = a.worker_name WHERE wp.auth_uid = m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _wx_shift_plans TO authenticated;
SELECT 'shift_plans_fixture | ' || ((SELECT me FROM _wx_shift_plans) IS NOT NULL AND (SELECT foreign_row FROM _wx_shift_plans) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _wx_shift_plans)::text, 'role','authenticated')::text, true);
WITH u AS (UPDATE shift_plans SET id = id WHERE id = (SELECT foreign_row FROM _wx_shift_plans) RETURNING 1)
SELECT 'shift_plans_foreign_update_touched | ' || count(*) FROM u;
WITH d AS (DELETE FROM shift_plans WHERE id = (SELECT foreign_row FROM _wx_shift_plans) RETURNING 1)
SELECT 'shift_plans_foreign_delete_touched | ' || count(*) FROM d;
WITH o AS (UPDATE shift_plans SET id = id WHERE id = (SELECT own_row FROM _wx_shift_plans) RETURNING 1)
SELECT 'shift_plans_own_update_touched_gt0 | ' || (count(*) > 0) FROM o;
ROLLBACK;
SELECT 'shift_plans_rows_restored | ' || ((SELECT count(*) FROM shift_plans) = (SELECT n0 FROM _wx_shift_plans));
