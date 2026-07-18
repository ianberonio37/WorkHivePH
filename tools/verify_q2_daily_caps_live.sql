-- Q2 LIVE VERIFY — proves the generic check_daily_row_cap() blocks the (cap+1)th row/day.
-- ======================================================================================
-- Exercises the NEW dynamic-SQL generic function on a representative table
-- (community_posts, cap 200/hive). Confirms: (a) the per-hive/day cap raises SQLSTATE
-- 54000, and (b) the function reads the correct timestamp column generically.
--
-- Requires local Supabase UP + migration 20260705000001_q2_high_write_daily_caps.sql applied.
--   psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -f tools/verify_q2_daily_caps_live.sql
--
-- POLLUTION-SAFE: BEGIN; ... ROLLBACK; undoes every probe row.

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
    RAISE EXCEPTION 'Q2 LIVE VERIFY: no hive exists to test against';
  END IF;

  -- 200 community_posts today for one hive, DISTINCT authors so the per-USER cap (100)
  -- never trips before the per-HIVE cap (200) — isolates the hive-cap assertion.
  FOR i IN 1..200 LOOP
    INSERT INTO public.community_posts (hive_id, author_name, content, category, created_at)
    VALUES (test_hive, 'q2-bot-' || i, 'probe', 'general', now());
  END LOOP;

  -- The 201st (new author, so user cap is irrelevant) must hit the hive cap → 54000.
  BEGIN
    INSERT INTO public.community_posts (hive_id, author_name, content, category, created_at)
    VALUES (test_hive, 'q2-bot-201', 'probe', 'general', now());
  EXCEPTION WHEN sqlstate '54000' THEN
    blocked := true;
  END;

  IF NOT blocked THEN
    RAISE EXCEPTION 'Q2 LIVE VERIFY FAIL: the 201st community_posts row/day was NOT blocked';
  END IF;

  RAISE NOTICE 'Q2 LIVE VERIFY PASS: generic check_daily_row_cap blocked the 201st row (SQLSTATE 54000).';
END $$;

ROLLBACK;
