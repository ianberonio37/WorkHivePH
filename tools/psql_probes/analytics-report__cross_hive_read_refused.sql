-- cross_hive_read_refused (analytics-report, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (v_hives_truth) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: hives_fixture \| t
-- expect: hives_foreign_rows \| 0
-- expect: hives_own_rows_gt0 \| t

CREATE TEMP TABLE _fx_hives AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.id FROM v_hives_truth x WHERE x.id IS NOT NULL AND x.id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.id AND z.status = 'active')
        GROUP BY x.id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM v_hives_truth x WHERE x.id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_hives TO authenticated;
SELECT 'hives_fixture | ' || ((SELECT me FROM _fx_hives) IS NOT NULL AND (SELECT foreign_hive FROM _fx_hives) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_hives)::text, 'role','authenticated')::text, true);
SELECT 'hives_foreign_rows | ' || (SELECT count(*) FROM v_hives_truth WHERE id = (SELECT foreign_hive FROM _fx_hives));
SELECT 'hives_own_rows_gt0 | ' || ((SELECT count(*) FROM v_hives_truth WHERE id = (SELECT mine FROM _fx_hives)) > 0);
ROLLBACK;
