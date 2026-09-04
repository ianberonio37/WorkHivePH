-- tenant_isolation (shift-brain): a foreign hive's plans are invisible. A shift plan names who works
-- which hours, so a leak here hands one plant its neighbour's staffing - and shift-brain is a
-- generated surface, which makes it easy to assume the generator's scoping is the enforcement. It is
-- not; RLS is, and RLS only binds under a real role.
-- Proven as the authenticated ROLE with an active member's claims (as postgres, policies never apply
-- and every such probe passes vacuously), with a CONTROL leg proving foreign rows exist for postgres
-- so the member's zero is a refusal rather than an empty table, and a second control proving the
-- member still sees their OWN plans - a policy that returned nothing to everyone would pass a
-- leak-only test while breaking the product.
-- expect: rls_enabled \| t
-- expect: control_sees_foreign \| t
-- expect: member_plans_own_only \| t
-- expect: member_sees_at_least_own \| t
SELECT 'rls_enabled | ' || relrowsecurity FROM pg_class WHERE relname='shift_plans';
CREATE TEMP TABLE _ti AS
SELECT hm.hive_id, hm.auth_uid,
       (SELECT count(*) FROM shift_plans WHERE hive_id <> hm.hive_id) AS foreign_plans,
       (SELECT count(*) FROM shift_plans WHERE hive_id  = hm.hive_id) AS own_plans
FROM hive_members hm WHERE hm.status='active' AND hm.auth_uid IS NOT NULL
  AND EXISTS (SELECT 1 FROM shift_plans s WHERE s.hive_id = hm.hive_id) LIMIT 1;
GRANT SELECT ON _ti TO authenticated;
SELECT 'control_sees_foreign | ' || ((SELECT foreign_plans FROM _ti) > 0);
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _ti)::text, 'role','authenticated')::text, true);
SELECT 'member_plans_own_only | ' || ((SELECT count(*) FROM shift_plans WHERE hive_id <> (SELECT hive_id FROM _ti)) = 0);
SELECT 'member_sees_at_least_own | ' || ((SELECT count(*) FROM shift_plans) >= (SELECT own_plans FROM _ti));
ROLLBACK;
DROP TABLE _ti;
