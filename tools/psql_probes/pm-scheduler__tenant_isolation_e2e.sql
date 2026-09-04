-- tenant_isolation_e2e (pm-scheduler): a foreign hive's PM rows are invisible through the reads, and
-- the completions table that drives the realtime channel is itself hive-scoped. Proven under the
-- authenticated ROLE with a real active member's claims - as postgres, RLS never binds and every
-- such probe passes vacuously.
-- The CONTROL leg is what makes the pass mean anything: foreign rows must demonstrably EXIST for
-- postgres, or "member sees zero foreign rows" is satisfied by an empty database.
-- expect: control_sees_foreign \| t
-- expect: member_assets_own_only \| t
-- expect: member_completions_own_only \| t
-- expect: member_scope_items_own_only \| t
-- expect: completions_in_realtime_publication \| t
CREATE TEMP TABLE _ti AS
SELECT hm.hive_id, hm.auth_uid,
       (SELECT count(*) FROM pm_assets      WHERE hive_id <> hm.hive_id) AS f_assets,
       (SELECT count(*) FROM pm_completions WHERE hive_id <> hm.hive_id) AS f_comps,
       (SELECT count(*) FROM pm_scope_items WHERE hive_id <> hm.hive_id) AS f_scope
FROM hive_members hm WHERE hm.status='active' AND hm.auth_uid IS NOT NULL LIMIT 1;
GRANT SELECT ON _ti TO authenticated;
SELECT 'control_sees_foreign | ' || ((SELECT f_assets FROM _ti) > 0 AND (SELECT f_comps FROM _ti) > 0
                                     AND (SELECT f_scope FROM _ti) > 0);
SELECT 'completions_in_realtime_publication | ' || EXISTS (
  SELECT 1 FROM pg_publication_tables WHERE pubname='supabase_realtime' AND tablename='pm_completions');
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _ti)::text, 'role','authenticated')::text, true);
SELECT 'member_assets_own_only | '      || ((SELECT count(*) FROM pm_assets      WHERE hive_id <> (SELECT hive_id FROM _ti)) = 0);
SELECT 'member_completions_own_only | ' || ((SELECT count(*) FROM pm_completions WHERE hive_id <> (SELECT hive_id FROM _ti)) = 0);
SELECT 'member_scope_items_own_only | ' || ((SELECT count(*) FROM pm_scope_items WHERE hive_id <> (SELECT hive_id FROM _ti)) = 0);
ROLLBACK;
DROP TABLE _ti;
