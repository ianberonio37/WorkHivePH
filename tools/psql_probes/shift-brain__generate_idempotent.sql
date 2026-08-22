-- generate_idempotent: one plan per (hive, date, window) — the unique index refuses a duplicate
-- (23505) while a control insert on a free date is accepted; the window vocabulary is CHECKed.
-- Teeth both directions inside BEGIN/ROLLBACK, counts restored.
-- expect: unique_per_window \| t
-- expect: duplicate key value violates unique constraint
-- expect: control_accepted \| t
-- expect: window_vocab_checked \| t
-- expect: restored \| t
SELECT 'unique_per_window | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename='shift_plans' AND indexdef ILIKE '%UNIQUE%'
   AND indexdef ILIKE '%hive_id%' AND indexdef ILIKE '%shift_date%' AND indexdef ILIKE '%shift_window%');
SELECT 'window_vocab_checked | ' || EXISTS (
  SELECT 1 FROM pg_constraint WHERE conrelid='shift_plans'::regclass
   -- Postgres canonicalises IN to '= ANY (ARRAY[...])' — match the catalog's phrasing
   AND pg_get_constraintdef(oid) ILIKE '%shift_window = ANY%');
CREATE TEMP TABLE _gi AS
SELECT hive_id, shift_date, shift_window, (SELECT count(*) FROM shift_plans) AS n0
FROM shift_plans LIMIT 1;
BEGIN;
INSERT INTO shift_plans (hive_id, shift_date, shift_window)
SELECT hive_id, shift_date, shift_window FROM _gi;
ROLLBACK;
BEGIN;
INSERT INTO shift_plans (hive_id, shift_date, shift_window)
SELECT hive_id, DATE '2027-03-15', shift_window FROM _gi;
SELECT 'control_accepted | ' || ((SELECT count(*) FROM shift_plans) = (SELECT n0 + 1 FROM _gi));
ROLLBACK;
SELECT 'restored | ' || ((SELECT count(*) FROM shift_plans) = (SELECT n0 FROM _gi));
DROP TABLE _gi;
