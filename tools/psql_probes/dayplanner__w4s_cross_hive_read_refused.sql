-- cross_hive_read_refused (dayplanner, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (logbook, v_logbook_truth, v_pm_scope_items_truth) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: logbook_fixture \| t
-- expect: logbook_foreign_rows \| 0
-- expect: logbook_own_rows_gt0 \| t
-- expect: v_logbook_truth_fixture \| t
-- expect: v_logbook_truth_foreign_rows \| 0
-- expect: v_logbook_truth_own_rows_gt0 \| t
-- expect: pm_scope_items_fixture \| t
-- expect: pm_scope_items_foreign_rows \| 0
-- expect: pm_scope_items_own_rows_gt0 \| t

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
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_logbook TO authenticated;
SELECT 'logbook_fixture | ' || ((SELECT me FROM _fx_logbook) IS NOT NULL AND (SELECT foreign_hive FROM _fx_logbook) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_logbook)::text, 'role','authenticated')::text, true);
SELECT 'logbook_foreign_rows | ' || (SELECT count(*) FROM logbook WHERE hive_id = (SELECT foreign_hive FROM _fx_logbook));
SELECT 'logbook_own_rows_gt0 | ' || ((SELECT count(*) FROM logbook WHERE hive_id = (SELECT mine FROM _fx_logbook)) > 0);
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
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_v_logbook_truth TO authenticated;
SELECT 'v_logbook_truth_fixture | ' || ((SELECT me FROM _fx_v_logbook_truth) IS NOT NULL AND (SELECT foreign_hive FROM _fx_v_logbook_truth) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_v_logbook_truth)::text, 'role','authenticated')::text, true);
SELECT 'v_logbook_truth_foreign_rows | ' || (SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_v_logbook_truth));
SELECT 'v_logbook_truth_own_rows_gt0 | ' || ((SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT mine FROM _fx_v_logbook_truth)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_pm_scope_items AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM v_pm_scope_items_truth x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND NOT EXISTS (SELECT 1 FROM marketplace_platform_admins pa WHERE pa.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM v_pm_scope_items_truth x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_pm_scope_items TO authenticated;
SELECT 'pm_scope_items_fixture | ' || ((SELECT me FROM _fx_pm_scope_items) IS NOT NULL AND (SELECT foreign_hive FROM _fx_pm_scope_items) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_pm_scope_items)::text, 'role','authenticated')::text, true);
SELECT 'pm_scope_items_foreign_rows | ' || (SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id = (SELECT foreign_hive FROM _fx_pm_scope_items));
SELECT 'pm_scope_items_own_rows_gt0 | ' || ((SELECT count(*) FROM v_pm_scope_items_truth WHERE hive_id = (SELECT mine FROM _fx_pm_scope_items)) > 0);
ROLLBACK;
