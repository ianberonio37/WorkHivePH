-- one_brief_per_day: an AMC briefing is one per hive per shift_date — enforced by the DATABASE
-- (unique index uq_amc_briefings_hive_shift), not by whichever cron or edge path happens to write it.
-- WHY THIS IS A RECIPE AND NOT A HAND-WALK: the property is pure DB truth, so re-proving it after every
-- shared-file edit cost a browser walk that could only ever re-observe what SQL can assert. Turning it
-- into an executable probe is the same move that keeps the other psql-kind rows permanently green.
-- Teeth BOTH directions inside BEGIN/ROLLBACK: a SECOND brief for a hive+date already taken must be
-- REFUSED (23505), and a control insert for the SAME hive on a FREE date must be ACCEPTED — that is what
-- separates a working uniqueness rule from a table that rejects everything. Non-vacuity is explicit: the
-- population is printed, so an empty table cannot masquerade as agreement.
-- Self-grounding: every fixture is derived from a live row, never a literal.
-- expect: unique_index_present \| t
-- expect: groups_checked \| [1-9][0-9]*
-- expect: duplicate_days \| 0
-- expect: duplicate key value violates unique constraint
-- expect: control_accepted \| t
-- expect: count_restored_after_rollback \| t
SELECT 'unique_index_present | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename = 'amc_briefings'
   AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%hive_id%' AND indexdef ILIKE '%shift_date%');

-- the invariant as it stands, with its population printed beside it
SELECT 'groups_checked | ' || count(*)::text FROM (
  SELECT hive_id, shift_date FROM amc_briefings GROUP BY hive_id, shift_date) g;
SELECT 'duplicate_days | ' || count(*)::text FROM (
  SELECT hive_id, shift_date FROM amc_briefings GROUP BY hive_id, shift_date HAVING count(*) > 1) d;

CREATE TEMP TABLE _fix AS
SELECT b.id AS src_id, b.hive_id, b.shift_date, b.brief,
       (SELECT count(*) FROM amc_briefings) AS n0
FROM amc_briefings b LIMIT 1;

BEGIN;
-- TEETH: the same hive+date twice must be refused by the index, not by application code
INSERT INTO amc_briefings (hive_id, shift_date, generated_at, status, brief)
SELECT hive_id, shift_date, now(), 'pending', brief FROM _fix;   -- brief is JSON: reuse the live one
ROLLBACK;

BEGIN;
-- CONTROL: the SAME hive on a date nobody has used must be accepted, or the index rejects everything
INSERT INTO amc_briefings (hive_id, shift_date, generated_at, status, brief)
SELECT hive_id, shift_date - INTERVAL '3650 days', now(), 'pending', brief FROM _fix;
SELECT 'control_accepted | ' || EXISTS (
  SELECT 1 FROM amc_briefings a JOIN _fix f ON a.hive_id = f.hive_id
   WHERE a.shift_date = f.shift_date - INTERVAL '3650 days');
ROLLBACK;

SELECT 'count_restored_after_rollback | ' || ((SELECT count(*) FROM amc_briefings) = (SELECT n0 FROM _fix));
