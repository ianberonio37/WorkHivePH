-- tenant_isolation_e2e (dayplanner): schedule_items is per-PERSON — RLS is enabled, and under the
-- authenticated ROLE with a real owner's claims the visible rows are exactly that owner's own
-- (the probe needs the ROLE, not just claims: as postgres RLS never binds). A second owner sees
-- none of the first owner's rows; realtime republication carries the same table.
-- expect: rls_enabled \| t
-- expect: owner_sees_own \| t
-- expect: peer_sees_none_of_owner \| t
-- expect: in_realtime_publication \| t
SELECT 'rls_enabled | ' || relrowsecurity FROM pg_class WHERE relname = 'schedule_items';
SELECT 'in_realtime_publication | ' || EXISTS (
  SELECT 1 FROM pg_publication_tables WHERE pubname='supabase_realtime' AND tablename='schedule_items');

CREATE TEMP TABLE _ti AS
SELECT a.auth_uid AS owner_uid,
       (SELECT count(*) FROM schedule_items s WHERE s.auth_uid = a.auth_uid) AS owner_rows,
       (SELECT b.auth_uid FROM schedule_items b WHERE b.auth_uid IS NOT NULL
          AND b.auth_uid <> a.auth_uid LIMIT 1) AS peer_uid
FROM schedule_items a
WHERE a.auth_uid IS NOT NULL
GROUP BY a.auth_uid ORDER BY 2 DESC LIMIT 1;
-- the fixture must survive SET ROLE: a temp table is owned by postgres, so grant it
GRANT SELECT ON _ti TO authenticated;

BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT owner_uid FROM _ti)::text, 'role', 'authenticated')::text, true);
SELECT 'owner_sees_own | ' ||
  ((SELECT count(*) FROM schedule_items) >= (SELECT owner_rows FROM _ti)
   AND (SELECT count(*) FROM schedule_items WHERE auth_uid <> (SELECT owner_uid FROM _ti)) = 0);
ROLLBACK;

BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT peer_uid FROM _ti)::text, 'role', 'authenticated')::text, true);
SELECT 'peer_sees_none_of_owner | ' ||
  ((SELECT count(*) FROM schedule_items WHERE auth_uid = (SELECT owner_uid FROM _ti)) = 0);
ROLLBACK;
DROP TABLE _ti;
