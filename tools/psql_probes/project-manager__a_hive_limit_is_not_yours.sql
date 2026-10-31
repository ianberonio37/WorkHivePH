-- a_hive_limit_is_not_yours: the shared daily cap (check_daily_row_cap, 29 tables) has the hive's limit and the person's
--   own (HS W2, 2026-10-30, migration 20261030000008). In a hive of thirty the hive's limit is spent by the others: the
--   member it refuses wrote nothing today, and must be told it was the HIVE's limit - not "You have reached". The
--   person's own limit keeps "You have reached". Change orders (hive 100, person 50). Every write rolled back.
-- expect: hive_refusal \| Your hive has reached today's free limit of 100
-- expect: own_refusal \| You have reached today's free limit \(50\)
\set H '30303030-3030-4030-8030-303030303030'

BEGIN;
-- the other 28 have filed the hive's 100 today (triggers off for the fill)
SET LOCAL session_replication_role = replica;
INSERT INTO project_change_orders (project_id, hive_id, co_number, title, scope_change, status, requested_by)
SELECT (SELECT id FROM projects WHERE hive_id = :'H' AND deleted_at IS NULL AND project_type <> 'workorder' ORDER BY project_code LIMIT 1),
       :'H', 'CO-PROBE-' || g, 'probe ' || g, 'probe', 'pending', 'Ernesto Villareal'
FROM generate_series(1, 100) g;
SET LOCAL session_replication_role = origin;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Ana Reyes' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
CREATE TEMP TABLE _r (v text) ON COMMIT DROP;
DO $$ BEGIN
  INSERT INTO project_change_orders (project_id, hive_id, co_number, title, scope_change, status, requested_by)
  VALUES ((SELECT id FROM projects WHERE hive_id = '30303030-3030-4030-8030-303030303030' AND deleted_at IS NULL
           AND project_type <> 'workorder' ORDER BY project_code LIMIT 1),
          '30303030-3030-4030-8030-303030303030', 'CO-PROBE-X', 'probe x', 'probe', 'pending', 'Ana Reyes');
  INSERT INTO _r VALUES ('saved');
EXCEPTION WHEN program_limit_exceeded THEN INSERT INTO _r VALUES (SQLERRM); END $$;
SELECT 'hive_refusal | ' || v FROM _r;
ROLLBACK;

BEGIN;
-- one member's own 50 today, the hive far from its 100
SET LOCAL session_replication_role = replica;
INSERT INTO project_change_orders (project_id, hive_id, co_number, title, scope_change, status, requested_by)
SELECT (SELECT id FROM projects WHERE hive_id = :'H' AND deleted_at IS NULL AND project_type <> 'workorder' ORDER BY project_code LIMIT 1),
       :'H', 'CO-PROBE-' || g, 'probe ' || g, 'probe', 'pending', 'Ana Reyes'
FROM generate_series(1, 50) g;
SET LOCAL session_replication_role = origin;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Ana Reyes' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
CREATE TEMP TABLE _o (v text) ON COMMIT DROP;
DO $$ BEGIN
  INSERT INTO project_change_orders (project_id, hive_id, co_number, title, scope_change, status, requested_by)
  VALUES ((SELECT id FROM projects WHERE hive_id = '30303030-3030-4030-8030-303030303030' AND deleted_at IS NULL
           AND project_type <> 'workorder' ORDER BY project_code LIMIT 1),
          '30303030-3030-4030-8030-303030303030', 'CO-PROBE-Y', 'probe y', 'probe', 'pending', 'Ana Reyes');
  INSERT INTO _o VALUES ('saved');
EXCEPTION WHEN program_limit_exceeded THEN INSERT INTO _o VALUES (SQLERRM); END $$;
SELECT 'own_refusal | ' || v FROM _o;
ROLLBACK;
