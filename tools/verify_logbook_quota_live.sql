-- Q0 LIVE VERIFY — proves the per-day logbook cap blocks the 201st row/day at the DB.
-- =================================================================================
-- FREE_TIER_QUOTA_ROADMAP §Q0 DoD: "a script inserting 201 logbook rows/day is
-- blocked at the DB." This is the runtime proof that complements the static gate
-- (tools/validate_logbook_quota.py). It requires the local Supabase to be UP and
-- migration 20260705000000_q0_logbook_quota_pilot.sql applied.
--
-- HOW TO RUN (once Docker / local Supabase is up):
--   supabase migration up        # (or: supabase db reset) to apply the Q0 migration
--   psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -f tools/verify_logbook_quota_live.sql
--   -- or via the DB container:
--   docker exec -i supabase_db_<project> psql -U postgres -d postgres < tools/verify_logbook_quota_live.sql
--
-- POLLUTION-SAFE: everything runs inside BEGIN; ... ROLLBACK; so the 200 probe
-- rows and the temporary quota override are undone — the shared local DB is left
-- exactly as found (honors the "live writes pollute the test DB" rule).
--
-- Exit 0 + "Q0 LIVE VERIFY PASS" => cap has teeth. Non-zero + "FAIL" => regression.

\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE
  test_hive uuid;
  i         integer;
  blocked   boolean := false;
BEGIN
  SELECT id INTO test_hive FROM public.hives LIMIT 1;
  IF test_hive IS NULL THEN
    RAISE EXCEPTION 'Q0 LIVE VERIFY: no hive exists to test against (seed a hive first)';
  END IF;

  -- Deterministic caps: hive=200 (the target), per-user very high so the 200
  -- same-worker probe rows exercise the HIVE cap, not the user cap.
  INSERT INTO public.hive_quotas (hive_id, max_rows_logbook, max_rows_logbook_per_user)
  VALUES (test_hive, 200, 100000)
  ON CONFLICT (hive_id) DO UPDATE
    SET max_rows_logbook = 200, max_rows_logbook_per_user = 100000;

  -- 200 rows created TODAY — all must succeed (created_at defaults to now()).
  FOR i IN 1..200 LOOP
    INSERT INTO public.logbook (id, worker_name, date, hive_id, status)
    VALUES ('q0verify-' || i, 'q0-verify-bot', now(), test_hive, 'Open');
  END LOOP;

  -- The 201st must be blocked with SQLSTATE 54000.
  BEGIN
    INSERT INTO public.logbook (id, worker_name, date, hive_id, status)
    VALUES ('q0verify-201', 'q0-verify-bot', now(), test_hive, 'Open');
  EXCEPTION WHEN sqlstate '54000' THEN
    blocked := true;
  END;

  IF NOT blocked THEN
    RAISE EXCEPTION 'Q0 LIVE VERIFY FAIL: the 201st logbook row/day was NOT blocked';
  END IF;

  RAISE NOTICE 'Q0 LIVE VERIFY PASS: 200 rows allowed, 201st blocked at DB (SQLSTATE 54000).';
END $$;

ROLLBACK;
