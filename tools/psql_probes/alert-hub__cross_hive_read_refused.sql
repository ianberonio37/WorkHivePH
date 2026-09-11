-- cross_hive_read_refused (alert-hub, P-B, generated 2026-09-05 by tools/gen_cross_hive_read_recipes.py): every
-- hive-scoped table this page reads (amc_briefings, automation_log) must refuse a foreign hive in the DATABASE. RLS USING
-- clauses FILTER rather than raise, so the probe counts rows as a member of exactly one hive: a foreign hive with
-- rows reads 0, the member's own hive reads > 0 (the control). Fixtures are chosen live; a table with rows in
-- fewer than two hives reports 'n/a' and is excluded from the expectations by the generator.
-- expect: amc_briefings_fixture \| t
-- expect: amc_briefings_foreign_rows \| 0
-- expect: amc_briefings_own_rows_gt0 \| t
-- expect: automation_log_fixture \| t
-- expect: automation_log_foreign_rows \| 0
-- expect: automation_log_own_rows_gt0 \| t

CREATE TEMP TABLE _fx_amc_briefings AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM amc_briefings x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM amc_briefings x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_amc_briefings TO authenticated;
SELECT 'amc_briefings_fixture | ' || ((SELECT me FROM _fx_amc_briefings) IS NOT NULL AND (SELECT foreign_hive FROM _fx_amc_briefings) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_amc_briefings)::text, 'role','authenticated')::text, true);
SELECT 'amc_briefings_foreign_rows | ' || (SELECT count(*) FROM amc_briefings WHERE hive_id = (SELECT foreign_hive FROM _fx_amc_briefings));
SELECT 'amc_briefings_own_rows_gt0 | ' || ((SELECT count(*) FROM amc_briefings WHERE hive_id = (SELECT mine FROM _fx_amc_briefings)) > 0);
ROLLBACK;

CREATE TEMP TABLE _fx_automation_log AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT x.hive_id FROM automation_log x WHERE x.hive_id IS NOT NULL AND x.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members z WHERE z.auth_uid = m.auth_uid AND z.hive_id = x.hive_id AND z.status = 'active')
        GROUP BY x.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active'
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM automation_log x WHERE x.hive_id = m.hive_id)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_automation_log TO authenticated;
SELECT 'automation_log_fixture | ' || ((SELECT me FROM _fx_automation_log) IS NOT NULL AND (SELECT foreign_hive FROM _fx_automation_log) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_automation_log)::text, 'role','authenticated')::text, true);
SELECT 'automation_log_foreign_rows | ' || (SELECT count(*) FROM automation_log WHERE hive_id = (SELECT foreign_hive FROM _fx_automation_log));
SELECT 'automation_log_own_rows_gt0 | ' || ((SELECT count(*) FROM automation_log WHERE hive_id = (SELECT mine FROM _fx_automation_log)) > 0);
ROLLBACK;
