-- only_a_supervisor_writes_the_cmms_sync: the sync table pushed to the plant CMMS (HS L2, 2026-10-30).
--   every member reads it (CMMS references on asset-hub / logbook / plant-connections); only a supervisor writes it - a
--   worker's update, insert and delete are refused. Full hive subjects (seeders/full_hive.py seeds six SAP work orders).
--   Every write rolled back. Population printed.
-- expect: work_orders \| [1-9][0-9]*
-- expect: worker_reads \| t
-- expect: worker_updates \| 0
-- expect: worker_deletes \| 0
-- expect: worker_inserts \| refused
-- expect: supervisor_updates \| t
\set H '30303030-3030-4030-8030-303030303030'
SELECT 'work_orders | ' || count(*) FROM external_sync WHERE hive_id = :'H' AND entity_type = 'work_order';

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Joel Cruz' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
SELECT 'worker_reads | ' || (count(*) > 0) FROM external_sync WHERE hive_id = :'H';
WITH u AS (UPDATE external_sync SET status = 'Cancelled' WHERE hive_id = :'H' RETURNING 1) SELECT 'worker_updates | ' || count(*) FROM u;
WITH u AS (DELETE FROM external_sync WHERE hive_id = :'H' RETURNING 1) SELECT 'worker_deletes | ' || count(*) FROM u;
CREATE TEMP TABLE _i (v text) ON COMMIT DROP;
DO $$ BEGIN
  INSERT INTO external_sync (hive_id, system_type, external_id, entity_type, status)
  VALUES ('30303030-3030-4030-8030-303030303030', 'SAP_PM', 'WO-PROBE', 'work_order', 'Open');
  INSERT INTO _i VALUES ('allowed');
EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _i VALUES ('refused'); END $$;
SELECT 'worker_inserts | ' || v FROM _i;
ROLLBACK;

BEGIN;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Ernesto Villareal' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
WITH u AS (UPDATE external_sync SET status = status WHERE hive_id = :'H' AND entity_type = 'work_order' RETURNING 1)
SELECT 'supervisor_updates | ' || (count(*) > 0) FROM u;
ROLLBACK;
