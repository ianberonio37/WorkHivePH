-- Q1 live-verify: cumulative hive-quota enforcement. Non-destructive (tests roll back).
\echo '=== TRIGGERS ATTACHED (expect all 5) ==='
SELECT c.relname tbl, t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
 WHERE t.tgname LIKE 'trg_hive_quota%' AND NOT t.tgisinternal ORDER BY 1;

\echo '=== TEST 1: ENFORCE — cap below current count BLOCKS logbook insert with SQLSTATE 54000 (cumulative) ==='
BEGIN;
UPDATE public.hive_quotas SET max_rows_logbook = 1, enforce_blocking = true
 WHERE hive_id = (SELECT hive_id FROM public.logbook GROUP BY hive_id ORDER BY count(*) DESC LIMIT 1);
DO $$
DECLARE h uuid;
BEGIN
  SELECT hive_id INTO h FROM public.logbook GROUP BY hive_id ORDER BY count(*) DESC LIMIT 1;
  BEGIN
    INSERT INTO public.logbook (id, hive_id, worker_name, date)
    VALUES (gen_random_uuid(), h, 'q1-enforce-test', now()::date);
    RAISE NOTICE 'TEST1 FAIL: insert SUCCEEDED (expected block)';
  EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE = '54000' AND SQLERRM ILIKE '%cumulative%'
      THEN RAISE NOTICE 'TEST1 PASS: blocked SQLSTATE=% (%)', SQLSTATE, left(SQLERRM,60);
      ELSE RAISE NOTICE 'TEST1 ?: SQLSTATE=% msg=%', SQLSTATE, left(SQLERRM,80);
    END IF;
  END;
END $$;
ROLLBACK;

\echo '=== TEST 2: WARN-ONLY — enforce off lets the insert THROUGH + logs status=skipped (no constraint violation) ==='
BEGIN;
UPDATE public.hive_quotas SET max_rows_logbook = 1, enforce_blocking = false
 WHERE hive_id = (SELECT hive_id FROM public.logbook GROUP BY hive_id ORDER BY count(*) DESC LIMIT 1);
DO $$
DECLARE h uuid; n_before int; n_after int;
BEGIN
  SELECT hive_id INTO h FROM public.logbook GROUP BY hive_id ORDER BY count(*) DESC LIMIT 1;
  SELECT count(*) INTO n_before FROM public.automation_log WHERE job_name='hive_quota_logbook_over';
  INSERT INTO public.logbook (id, hive_id, worker_name, date)
  VALUES (gen_random_uuid(), h, 'q1-warn-test', now()::date);
  SELECT count(*) INTO n_after FROM public.automation_log WHERE job_name='hive_quota_logbook_over';
  IF n_after > n_before
    THEN RAISE NOTICE 'TEST2 PASS: insert allowed + warn logged (status=skipped), log rows %->%', n_before, n_after;
    ELSE RAISE NOTICE 'TEST2 PARTIAL: insert allowed but no warn log row (%->%)', n_before, n_after;
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'TEST2 FAIL: warn-only path errored SQLSTATE=% msg=%', SQLSTATE, left(SQLERRM,80);
END $$;
ROLLBACK;

\echo '=== TEST 3: NEW-HIVE TRIGGER — a fresh hive auto-gets a generous, enforcing quota row ==='
BEGIN;
DO $$
DECLARE new_hive uuid; got_cap int; got_enf boolean;
BEGIN
  INSERT INTO public.hives (name, invite_code, created_by)
  VALUES ('q1-trigger-test', substr(md5(gen_random_uuid()::text),1,6), 'q1-test')
  RETURNING id INTO new_hive;
  SELECT max_rows_logbook, enforce_blocking INTO got_cap, got_enf
    FROM public.hive_quotas WHERE hive_id = new_hive;
  IF got_cap = 20000 AND got_enf
    THEN RAISE NOTICE 'TEST3 PASS: new hive auto-seeded quota (logbook cap=% enforce=%)', got_cap, got_enf;
    ELSE RAISE NOTICE 'TEST3 FAIL: new hive quota row cap=% enforce=% (expected 20000/true)', got_cap, got_enf;
  END IF;
END $$;
ROLLBACK;
