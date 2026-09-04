-- tenant_isolation (engineering-design): a foreign hive's saved calcs are invisible. engineering_calcs
-- carries the design record - inputs, result and the governing standard - so a leak here is not just a
-- privacy break, it hands another plant's engineering to a stranger.
-- Proven under the authenticated ROLE (postgres bypasses RLS entirely), with a control leg proving
-- foreign rows exist so the zero is a REFUSAL and not an empty table.
-- expect: control_sees_foreign \| t
-- expect: member_calcs_own_only \| t
-- expect: member_sees_at_least_own \| t
-- expect: rls_enabled \| t
SELECT 'rls_enabled | ' || relrowsecurity FROM pg_class WHERE relname='engineering_calcs';
CREATE TEMP TABLE _ti AS
SELECT hm.hive_id, hm.auth_uid,
       (SELECT count(*) FROM engineering_calcs WHERE hive_id <> hm.hive_id) AS foreign_calcs,
       (SELECT count(*) FROM engineering_calcs WHERE hive_id  = hm.hive_id) AS own_calcs
FROM hive_members hm WHERE hm.status='active' AND hm.auth_uid IS NOT NULL
  AND EXISTS (SELECT 1 FROM engineering_calcs e WHERE e.hive_id = hm.hive_id) LIMIT 1;
GRANT SELECT ON _ti TO authenticated;
SELECT 'control_sees_foreign | ' || ((SELECT foreign_calcs FROM _ti) > 0);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _ti)::text, 'role','authenticated')::text, true);
SELECT 'member_calcs_own_only | ' || ((SELECT count(*) FROM engineering_calcs WHERE hive_id <> (SELECT hive_id FROM _ti)) = 0);
-- the other half of isolation: it must not have refused EVERYTHING. A policy that returns zero rows
-- to everyone would pass the leak test and break the product.
SELECT 'member_sees_at_least_own | ' || ((SELECT count(*) FROM engineering_calcs) >= (SELECT own_calcs FROM _ti));
ROLLBACK;
DROP TABLE _ti;
