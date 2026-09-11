-- cross_hive_read_refused (achievements, P-B P83, 2026-09-05): v_worker_achievements_truth carries no hive_id - worker_achievements
-- RLS grants a member their OWN rows plus their HIVE-MATES' (worker_name IN user_hive_worker_names()), so the boundary is the hive
-- through membership. As an active single-hive member with an achievement row, a worker who shares NO hive with them must read 0
-- rows and the member's own row > 0 (the control). Fixture chosen live; rolled back.
-- expect: worker_achievements_fixture \| t
-- expect: worker_achievements_foreign_rows \| 0
-- expect: worker_achievements_own_rows_gt0 \| t
CREATE TEMP TABLE _fx_worker_achievements AS
SELECT m.auth_uid AS me,
       (SELECT w.auth_uid FROM worker_achievements w
         WHERE w.auth_uid <> m.auth_uid
           AND NOT EXISTS (SELECT 1 FROM hive_members a JOIN hive_members b ON a.hive_id = b.hive_id
                           WHERE a.auth_uid = m.auth_uid AND b.auth_uid = w.auth_uid AND a.status = 'active' AND b.status = 'active')
         LIMIT 1) AS stranger
FROM hive_members m
WHERE m.status = 'active' AND m.auth_uid IS NOT NULL
  AND (SELECT count(*) FROM hive_members y WHERE y.auth_uid = m.auth_uid AND y.status = 'active') = 1
  AND EXISTS (SELECT 1 FROM worker_achievements w WHERE w.auth_uid = m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_worker_achievements TO authenticated;
SELECT 'worker_achievements_fixture | ' || ((SELECT me FROM _fx_worker_achievements) IS NOT NULL AND (SELECT stranger FROM _fx_worker_achievements) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_worker_achievements)::text, 'role','authenticated')::text, true);
SELECT 'worker_achievements_foreign_rows | ' || (SELECT count(*) FROM v_worker_achievements_truth WHERE auth_uid = (SELECT stranger FROM _fx_worker_achievements));
SELECT 'worker_achievements_own_rows_gt0 | ' || ((SELECT count(*) FROM v_worker_achievements_truth WHERE auth_uid = (SELECT me FROM _fx_worker_achievements)) > 0);
ROLLBACK;
