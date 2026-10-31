-- the_voice_trail_is_the_supervisors: ai_audit_log, the voice trail audit-log.html shows supervisors (HS L1/L2,
--   2026-10-30, migration 20261030000010). Any membership row of any status read the whole hive's trail and wrote into it
--   under any name. Now a worker reads none of it, the active supervisor reads it, an entry carries its writer's own name
--   whatever name was sent, and a member who has been deactivated writes nothing. Every write rolled back.
-- expect: worker_reads \| 0
-- expect: supervisor_reads \| true
-- expect: forged_name_bound_to \| Joel Cruz
-- expect: deactivated_member_writes \| refused
-- expect: deactivated_member_reads \| 0
\set H '30303030-3030-4030-8030-303030303030'

BEGIN;
-- a teammate's voice action in the trail (written as the platform)
INSERT INTO ai_audit_log (hive_id, worker_name, event, payload, source) VALUES (:'H', 'Ana Reyes', 'logbook.create', '{"probe": true}', 'voice-handler');

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Joel Cruz' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
SELECT 'worker_reads | ' || count(*) FROM ai_audit_log WHERE hive_id = :'H';
-- the worker writes an entry naming a supervisor
INSERT INTO ai_audit_log (hive_id, worker_name, event, payload, source) VALUES (:'H', 'Ernesto Villareal', 'pm.complete', '{"probe": "forged"}', 'voice-handler');
RESET ROLE;
SELECT 'forged_name_bound_to | ' || worker_name FROM ai_audit_log WHERE hive_id = :'H' AND payload->>'probe' = 'forged';

SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Ernesto Villareal' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
SELECT 'supervisor_reads | ' || (count(*) > 0) FROM ai_audit_log WHERE hive_id = :'H';
RESET ROLE;

-- a member who has been deactivated: their membership row is still there, with its status
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE hive_id = :'H' AND status = 'deactivated' ORDER BY worker_name LIMIT 1)::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
SELECT 'deactivated_member_reads | ' || count(*) FROM ai_audit_log WHERE hive_id = :'H';
CREATE TEMP TABLE _d (v text) ON COMMIT DROP;
DO $$ BEGIN
  INSERT INTO ai_audit_log (hive_id, worker_name, event, payload, source)
  VALUES ('30303030-3030-4030-8030-303030303030', 'Rodel Ignacio', 'logbook.create', '{"probe": "deactivated"}', 'voice-handler');
  INSERT INTO _d VALUES ('written');
EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _d VALUES ('refused'); END $$;
SELECT 'deactivated_member_writes | ' || v FROM _d;
ROLLBACK;
