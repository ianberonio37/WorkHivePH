-- cross_hive_read_refused (llm-observability, P-B P76, 2026-09-05): the cost log a supervisor reads is HIS hive's.
-- ai_cost_log_read carries (admin OR own auth_uid OR active SUPERVISOR of the row's hive) since SL AU4 (20261014000004:
-- a plain worker read a teammate's AI questions before it); like every USING clause it FILTERS rather than raising, so
-- the probe counts rows: a supervisor of one hive reads 0 rows of a hive with hundreds of cost rows, and >0 rows of his
-- own (the control that proves the query is not broken). The fixture is a SUPERVISOR, chosen in a stated order: an
-- unordered LIMIT 1 over any member passed when it landed on a supervisor and failed when it landed on a worker, whose
-- BLIND control is the policy working (2026-10-27).
-- expect: fixture_member_and_foreign_hive \| t
-- expect: foreign_hive_rows_visible \| 0
-- expect: own_hive_rows_visible_gt0 \| t
CREATE TEMP TABLE _cx AS
SELECT m.auth_uid AS me, m.hive_id AS mine,
       (SELECT c.hive_id FROM ai_cost_log c WHERE c.hive_id IS NOT NULL AND c.hive_id <> m.hive_id
          AND NOT EXISTS (SELECT 1 FROM hive_members x WHERE x.auth_uid = m.auth_uid AND x.hive_id = c.hive_id AND x.status = 'active')
        GROUP BY c.hive_id ORDER BY count(*) DESC LIMIT 1) AS foreign_hive
FROM hive_members m
WHERE m.status = 'active' AND EXISTS (SELECT 1 FROM ai_cost_log c WHERE c.hive_id = m.hive_id)
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND m.role = 'supervisor'
ORDER BY m.joined_at, m.auth_uid
LIMIT 1;
GRANT SELECT ON _cx TO authenticated;
SELECT 'fixture_member_and_foreign_hive | ' || ((SELECT me FROM _cx) IS NOT NULL AND (SELECT foreign_hive FROM _cx) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _cx)::text, 'role','authenticated')::text, true);
SELECT 'foreign_hive_rows_visible | ' || (SELECT count(*) FROM ai_cost_log WHERE hive_id = (SELECT foreign_hive FROM _cx));
SELECT 'own_hive_rows_visible_gt0 | ' || ((SELECT count(*) FROM ai_cost_log WHERE hive_id = (SELECT mine FROM _cx)) > 0);
ROLLBACK;
