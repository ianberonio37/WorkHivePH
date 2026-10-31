-- two_presses_two_codes: a shift pressing Create at once (HS W2, 2026-10-30, migration 20261030000009). project-manager.html
--   asks for the next code, then inserts with it; the generators answered MAX(issued) + 1, so callers before any save all
--   got the SAME code and the unique key refused all but one (measured: 4 of 29 projects, 1 of 29 change orders). Two
--   asks with no save between them must now get two codes. A member of another hive draws no change-order number.
--   Everything rolled back (the counters too).
-- expect: project_codes_distinct \| true
-- expect: change_numbers_distinct \| true
-- expect: outsider_change_number \| refused
\set H '30303030-3030-4030-8030-303030303030'

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Ana Reyes' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
WITH c AS (SELECT generate_project_code(:'H', 'contractor', 2026) AS a, generate_project_code(:'H', 'contractor', 2026) AS b)
SELECT 'project_codes_distinct | ' || (a IS NOT NULL AND b IS NOT NULL AND a <> b) FROM c;
WITH p AS (SELECT id FROM projects WHERE hive_id = :'H' AND deleted_at IS NULL AND project_type <> 'workorder' ORDER BY project_code LIMIT 1),
     c AS (SELECT generate_change_order_number((SELECT id FROM p)) AS a, generate_change_order_number((SELECT id FROM p)) AS b)
SELECT 'change_numbers_distinct | ' || (a IS NOT NULL AND b IS NOT NULL AND a <> b) FROM c;
ROLLBACK;

BEGIN;
-- the project's id is read as the platform (the outsider's own reads cannot see it - RLS), then asked for as the outsider
SELECT set_config('probe.proj', (SELECT id FROM projects WHERE hive_id = :'H' AND deleted_at IS NULL AND project_type <> 'workorder'
  ORDER BY project_code LIMIT 1)::text, true) IS NOT NULL AS proj_set;
-- an active member of a DIFFERENT hive, asking for this hive's project's next change-order number
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT hm.auth_uid FROM hive_members hm
  WHERE hm.hive_id <> :'H' AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM hive_members x WHERE x.auth_uid = hm.auth_uid AND x.hive_id = :'H')
  ORDER BY hm.worker_name LIMIT 1)::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
CREATE TEMP TABLE _o (v text) ON COMMIT DROP;
DO $$ BEGIN
  PERFORM generate_change_order_number(current_setting('probe.proj')::uuid);
  INSERT INTO _o VALUES ('drawn');
EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _o VALUES ('refused'); END $$;
SELECT 'outsider_change_number | ' || v FROM _o;
ROLLBACK;
