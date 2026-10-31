-- a_failure_mode_is_its_proposers: who may change a failure mode on the hive's reliability record (HS L2, 2026-10-30).
--   a supervisor may change any mode; a member only one they proposed, and only while it waits for approval. Measured as
--   the full hive's worker and supervisor (seeders/full_hive.py), every write rolled back, refusals caught as refusals.
--   The worker's own pending mode is made inside the transaction, so "may edit their own" is never vacuous.
-- expect: modes \| [1-9][0-9]*
-- expect: worker_rewrites_others_approved \| refused
-- expect: worker_rewrites_others_pending \| refused
-- expect: worker_deletes_others_pending \| refused
-- expect: worker_edits_own_pending \| allowed
-- expect: worker_deletes_own_pending \| allowed
-- expect: supervisor_rewrites_approved \| allowed
-- expect: supervisor_deletes_pending \| allowed
\set H '30303030-3030-4030-8030-303030303030'
SELECT 'modes | ' || count(*) FROM rcm_fmea_modes WHERE hive_id = :'H';

BEGIN;
CREATE TEMP TABLE _r (k text, v text) ON COMMIT DROP;
GRANT ALL ON _r TO authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Joel Cruz' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
INSERT INTO rcm_fmea_modes (hive_id, asset_id, function_text, failure_mode, severity, occurrence, detection, created_by)
SELECT :'H', id, 'probe function', 'probe mode - rolled back', 5, 5, 5, 'Joel Cruz'
  FROM asset_nodes WHERE hive_id = :'H' ORDER BY tag LIMIT 1;
DO $$
DECLARE h uuid := '30303030-3030-4030-8030-303030303030';
BEGIN
  BEGIN UPDATE rcm_fmea_modes SET severity = 1 WHERE id = (SELECT id FROM rcm_fmea_modes WHERE hive_id = h
          AND approved_at IS NOT NULL AND created_by <> 'Joel Cruz' LIMIT 1);
        INSERT INTO _r VALUES ('a', 'allowed');
  EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _r VALUES ('a', 'refused'); END;
  BEGIN UPDATE rcm_fmea_modes SET severity = 1 WHERE id = (SELECT id FROM rcm_fmea_modes WHERE hive_id = h
          AND approved_at IS NULL AND created_by <> 'Joel Cruz' LIMIT 1);
        INSERT INTO _r VALUES ('b', 'allowed');
  EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _r VALUES ('b', 'refused'); END;
  BEGIN DELETE FROM rcm_fmea_modes WHERE id = (SELECT id FROM rcm_fmea_modes WHERE hive_id = h
          AND approved_at IS NULL AND created_by <> 'Joel Cruz' LIMIT 1);
        INSERT INTO _r VALUES ('c', 'allowed');
  EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _r VALUES ('c', 'refused'); END;
  BEGIN UPDATE rcm_fmea_modes SET severity = 6 WHERE failure_mode = 'probe mode - rolled back' AND hive_id = h;
        INSERT INTO _r VALUES ('d', CASE WHEN FOUND THEN 'allowed' ELSE 'no row' END);
  EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _r VALUES ('d', 'refused'); END;
  BEGIN DELETE FROM rcm_fmea_modes WHERE failure_mode = 'probe mode - rolled back' AND hive_id = h;
        INSERT INTO _r VALUES ('e', CASE WHEN FOUND THEN 'allowed' ELSE 'no row' END);
  EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _r VALUES ('e', 'refused'); END;
END $$;
SELECT 'worker_rewrites_others_approved | ' || v FROM _r WHERE k = 'a';
SELECT 'worker_rewrites_others_pending | ' || v FROM _r WHERE k = 'b';
SELECT 'worker_deletes_others_pending | ' || v FROM _r WHERE k = 'c';
SELECT 'worker_edits_own_pending | ' || v FROM _r WHERE k = 'd';
SELECT 'worker_deletes_own_pending | ' || v FROM _r WHERE k = 'e';
ROLLBACK;

BEGIN;
CREATE TEMP TABLE _s (k text, v text) ON COMMIT DROP;
GRANT ALL ON _s TO authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT auth_uid FROM hive_members
  WHERE worker_name = 'Ernesto Villareal' AND hive_id = :'H')::text, 'role', 'authenticated')::text, true);
SET LOCAL ROLE authenticated;
DO $$
DECLARE h uuid := '30303030-3030-4030-8030-303030303030';
BEGIN
  BEGIN UPDATE rcm_fmea_modes SET severity = severity WHERE id = (SELECT id FROM rcm_fmea_modes WHERE hive_id = h
          AND approved_at IS NOT NULL AND created_by <> 'Ernesto Villareal' LIMIT 1);
        INSERT INTO _s VALUES ('a', CASE WHEN FOUND THEN 'allowed' ELSE 'no row' END);
  EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _s VALUES ('a', 'refused'); END;
  BEGIN DELETE FROM rcm_fmea_modes WHERE id = (SELECT id FROM rcm_fmea_modes WHERE hive_id = h AND approved_at IS NULL LIMIT 1);
        INSERT INTO _s VALUES ('b', CASE WHEN FOUND THEN 'allowed' ELSE 'no row' END);
  EXCEPTION WHEN insufficient_privilege THEN INSERT INTO _s VALUES ('b', 'refused'); END;
END $$;
SELECT 'supervisor_rewrites_approved | ' || v FROM _s WHERE k = 'a';
SELECT 'supervisor_deletes_pending | ' || v FROM _s WHERE k = 'b';
ROLLBACK;
