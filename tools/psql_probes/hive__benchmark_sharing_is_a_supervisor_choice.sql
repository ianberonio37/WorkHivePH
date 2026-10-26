-- expect: PASS a supervisor turns sharing on: flag, stamp and audit row
-- expect: PASS a worker of the hive is refused
-- expect: PASS a non-member is refused
-- expect: PASS turning it on twice changes nothing
-- expect: PASS nothing persisted after the rollback
-- forbid: FAIL
-- benchmark_sharing_is_a_supervisor_choice (2026-10-08): set_federated_benchmark_opt_in, as the person (role
-- authenticated + JWT claims), inside one transaction that is rolled back. Christine Dizon supervises hive
-- 084c113b; Bryan Garcia is a worker there; Rosa dela Cruz (2807e679 supervisor) is not a member of 084c113b.
-- accounts by EMAIL, resolved before any role switch (literal uids rotted when accounts were recreated, 2026-10-27)
CREATE TEMP TABLE IF NOT EXISTS _probe_acct AS SELECT
  (SELECT id FROM auth.users WHERE email = 'bryangarcia@auth.workhiveph.com') AS bryan,
  (SELECT id FROM auth.users WHERE email = 'junvanowner@auth.workhiveph.com') AS jun;
GRANT SELECT ON _probe_acct TO authenticated;
-- the people, resolved live (a pinned account and two names rotted with the seed, 2026-10-27)
CREATE TEMP TABLE IF NOT EXISTS _bx AS SELECT
  (SELECT auth_uid FROM public.hive_members WHERE hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' AND role = 'supervisor' AND status = 'active'
     AND auth_uid IS NOT NULL ORDER BY joined_at, id LIMIT 1) AS sup,
  (SELECT worker_name FROM public.hive_members WHERE hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' AND role = 'supervisor' AND status = 'active'
     AND auth_uid IS NOT NULL ORDER BY joined_at, id LIMIT 1) AS sup_name,
  (SELECT auth_uid FROM public.hive_members WHERE hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d' AND role = 'worker' AND status = 'active'
     AND auth_uid IS NOT NULL ORDER BY joined_at, id LIMIT 1) AS worker,
  (SELECT m.auth_uid FROM public.hive_members m WHERE m.status = 'active' AND m.auth_uid IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM public.hive_members b WHERE b.auth_uid = m.auth_uid AND b.hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d')
     ORDER BY m.joined_at, m.id LIMIT 1) AS outsider;
GRANT SELECT ON _bx TO authenticated;
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT sup FROM _bx)::text, 'role', 'authenticated')::text, true);
CREATE TEMP TABLE _on AS SELECT public.set_federated_benchmark_opt_in('084c113b-99c0-45c6-a8e8-b4b8349da46d', true) AS r;
RESET ROLE;
SELECT CASE WHEN (SELECT (r->>'changed')::boolean FROM _on)
             AND (SELECT federated_benchmark_opted_in AND federated_opt_in_by = (SELECT sup_name FROM _bx) AND federated_opt_in_at IS NOT NULL
                    FROM public.hives WHERE id = '084c113b-99c0-45c6-a8e8-b4b8349da46d')
             AND EXISTS (SELECT 1 FROM public.hive_audit_log WHERE hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d'
                          AND action = 'benchmark_sharing_on' AND actor = (SELECT sup_name FROM _bx) AND created_at > now() - interval '1 minute')
            THEN 'PASS' ELSE 'FAIL' END || ' a supervisor turns sharing on: flag, stamp and audit row';
SET LOCAL ROLE authenticated;
SELECT CASE WHEN (public.set_federated_benchmark_opt_in('084c113b-99c0-45c6-a8e8-b4b8349da46d', true)->>'changed')::boolean = false
            THEN 'PASS' ELSE 'FAIL' END || ' turning it on twice changes nothing';
SAVEPOINT w;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT worker FROM _bx)::text, 'role', 'authenticated')::text, true);
DO $$ BEGIN
  PERFORM public.set_federated_benchmark_opt_in('084c113b-99c0-45c6-a8e8-b4b8349da46d', false);
  RAISE NOTICE 'FAIL a worker of the hive is refused (it was allowed)';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS a worker of the hive is refused';
END $$;
ROLLBACK TO SAVEPOINT w;
SAVEPOINT n;
SELECT set_config('request.jwt.claims', (SELECT jsonb_build_object('sub', outsider, 'role', 'authenticated')::text FROM _bx), true);
DO $$ BEGIN
  PERFORM public.set_federated_benchmark_opt_in('084c113b-99c0-45c6-a8e8-b4b8349da46d', false);
  RAISE NOTICE 'FAIL a non-member is refused (it was allowed)';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS a non-member is refused';
END $$;
ROLLBACK TO SAVEPOINT n;
RESET ROLE;
ROLLBACK;
SELECT CASE WHEN NOT (SELECT federated_benchmark_opted_in FROM public.hives WHERE id = '084c113b-99c0-45c6-a8e8-b4b8349da46d')
             AND NOT EXISTS (SELECT 1 FROM public.hive_audit_log WHERE action LIKE 'benchmark_sharing_%' AND created_at > now() - interval '1 minute')
            THEN 'PASS' ELSE 'FAIL' END || ' nothing persisted after the rollback';
