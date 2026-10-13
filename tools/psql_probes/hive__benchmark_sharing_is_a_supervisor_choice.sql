-- expect: PASS a supervisor turns sharing on: flag, stamp and audit row
-- expect: PASS a worker of the hive is refused
-- expect: PASS a non-member is refused
-- expect: PASS turning it on twice changes nothing
-- expect: PASS nothing persisted after the rollback
-- forbid: FAIL
-- benchmark_sharing_is_a_supervisor_choice (2026-10-08): set_federated_benchmark_opt_in, as the person (role
-- authenticated + JWT claims), inside one transaction that is rolled back. Christine Dizon supervises hive
-- 084c113b; Bryan Garcia is a worker there; Rosa dela Cruz (2807e679 supervisor) is not a member of 084c113b.
BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"b2916047-d5b6-4707-bb12-5a569acc1d74","role":"authenticated"}', true);
CREATE TEMP TABLE _on AS SELECT public.set_federated_benchmark_opt_in('084c113b-99c0-45c6-a8e8-b4b8349da46d', true) AS r;
RESET ROLE;
SELECT CASE WHEN (SELECT (r->>'changed')::boolean FROM _on)
             AND (SELECT federated_benchmark_opted_in AND federated_opt_in_by = 'Christine Dizon' AND federated_opt_in_at IS NOT NULL
                    FROM public.hives WHERE id = '084c113b-99c0-45c6-a8e8-b4b8349da46d')
             AND EXISTS (SELECT 1 FROM public.hive_audit_log WHERE hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d'
                          AND action = 'benchmark_sharing_on' AND actor = 'Christine Dizon' AND created_at > now() - interval '1 minute')
            THEN 'PASS' ELSE 'FAIL' END || ' a supervisor turns sharing on: flag, stamp and audit row';
SET LOCAL ROLE authenticated;
SELECT CASE WHEN (public.set_federated_benchmark_opt_in('084c113b-99c0-45c6-a8e8-b4b8349da46d', true)->>'changed')::boolean = false
            THEN 'PASS' ELSE 'FAIL' END || ' turning it on twice changes nothing';
SAVEPOINT w;
SELECT set_config('request.jwt.claims', '{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
DO $$ BEGIN
  PERFORM public.set_federated_benchmark_opt_in('084c113b-99c0-45c6-a8e8-b4b8349da46d', false);
  RAISE NOTICE 'FAIL a worker of the hive is refused (it was allowed)';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS a worker of the hive is refused';
END $$;
ROLLBACK TO SAVEPOINT w;
SAVEPOINT n;
SELECT set_config('request.jwt.claims', (SELECT jsonb_build_object('sub', auth_uid, 'role', 'authenticated')::text
  FROM public.hive_members WHERE worker_name = 'Rosa dela Cruz' AND status = 'active' AND auth_uid IS NOT NULL LIMIT 1), true);
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
