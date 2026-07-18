-- Q5-a live-verify: inline base64 image size guard (oversized blocked, honest photo passes). Non-destructive.
BEGIN;
DO $$
DECLARE h uuid; big text; small text;
BEGIN
  SELECT id INTO h FROM public.hives LIMIT 1;
  big := repeat('A', 1600000);   -- ~1.6MB base64 (over the 1.5MB cap)
  small := repeat('A', 5000);    -- ~5KB (an honest small photo)
  BEGIN
    INSERT INTO public.logbook (id, hive_id, worker_name, date, photo)
    VALUES (gen_random_uuid(), h, 'q5a-big', now()::date, big);
    RAISE NOTICE 'BIG FAIL: oversized photo accepted (expected block)';
  EXCEPTION WHEN OTHERS THEN
    IF SQLSTATE='54000' AND SQLERRM ILIKE '%image too large%'
      THEN RAISE NOTICE 'BIG PASS: blocked (%)', left(SQLERRM,45);
      ELSE RAISE NOTICE 'BIG ?: SQLSTATE=% msg=%', SQLSTATE, left(SQLERRM,60); END IF;
  END;
  BEGIN
    INSERT INTO public.logbook (id, hive_id, worker_name, date, photo)
    VALUES (gen_random_uuid(), h, 'q5a-small', now()::date, small);
    RAISE NOTICE 'SMALL PASS: honest photo (~5KB) accepted';
  EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'SMALL FAIL: honest photo rejected SQLSTATE=% msg=%', SQLSTATE, left(SQLERRM,60); END;
END $$;
ROLLBACK;
