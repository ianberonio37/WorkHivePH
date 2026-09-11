-- cross_hive_read_refused (skillmatrix, P-B P106, 2026-09-05): v_skill_badges_truth carries no hive_id - its boundary is the
-- OWNER (skill_badges RLS: auth_uid = auth.uid()), so a cross-hive read is a cross-worker read. As an active member with badges,
-- every other worker's badge rows must read 0 (the USING clause filters) and the member's own rows > 0 (the control). Fixture
-- chosen live; rolled back.
-- expect: skill_badges_fixture \| t
-- expect: skill_badges_foreign_rows \| 0
-- expect: skill_badges_own_rows_gt0 \| t
CREATE TEMP TABLE _fx_skill_badges AS
SELECT m.auth_uid AS me
FROM hive_members m
WHERE m.status = 'active' AND m.auth_uid IS NOT NULL
  AND EXISTS (SELECT 1 FROM skill_badges b WHERE b.auth_uid = m.auth_uid)
  AND EXISTS (SELECT 1 FROM skill_badges b WHERE b.auth_uid <> m.auth_uid)
ORDER BY (m.role = 'supervisor') DESC
LIMIT 1;
GRANT SELECT ON _fx_skill_badges TO authenticated;
SELECT 'skill_badges_fixture | ' || ((SELECT me FROM _fx_skill_badges) IS NOT NULL);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT me FROM _fx_skill_badges)::text, 'role','authenticated')::text, true);
SELECT 'skill_badges_foreign_rows | ' || (SELECT count(*) FROM v_skill_badges_truth WHERE auth_uid <> (SELECT me FROM _fx_skill_badges));
SELECT 'skill_badges_own_rows_gt0 | ' || ((SELECT count(*) FROM v_skill_badges_truth WHERE auth_uid = (SELECT me FROM _fx_skill_badges)) > 0);
ROLLBACK;
