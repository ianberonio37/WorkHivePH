-- one_completion_one_mirror: completing a PM writes exactly one pm_completions row - not zero, not two.
-- The "not two" half is a DATABASE guarantee and this pins it: `pm_completions_dedup_uidx` is a PARTIAL
-- unique index on (scope_item_id, worker_name, (completed_at AT TIME ZONE 'UTC')::date) WHERE
-- scope_item_id IS NOT NULL. So a double-tap, a refresh-mid-submit, or a replayed request cannot pay
-- twice for the same scope item on the same day - and it is the INDEX that says so, not the page.
-- The partial predicate is honoured in the duplicate count below rather than ignored: counting rows the
-- index does not cover would report duplicates the guarantee never claimed to prevent, which is the
-- oracle-vocabulary error this bank keeps having to design against.
-- Teeth BOTH directions inside BEGIN/ROLLBACK: the same (scope_item, worker, day) twice must be REFUSED
-- (23505), and the SAME pair on a different day must be ACCEPTED - otherwise an index that rejects
-- everything would read as a working dedup rule.
-- Self-grounding: every fixture is a live completion row.
-- expect: completions_checked \| [1-9][0-9]*
-- expect: dedup_index_present \| t
-- expect: duplicate_same_day_groups \| 0
-- expect: duplicate key value violates unique constraint
-- expect: control_other_day_accepted \| t
-- expect: rows_restored_after_rollback \| t

SELECT 'completions_checked | ' || count(*)::text FROM pm_completions;

SELECT 'dedup_index_present | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename = 'pm_completions'
   AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%scope_item_id%' AND indexdef ILIKE '%worker_name%');

-- the invariant, scoped to exactly the rows the PARTIAL index covers
SELECT 'duplicate_same_day_groups | ' || count(*)::text FROM (
  SELECT scope_item_id, worker_name, ((completed_at AT TIME ZONE 'UTC')::date) AS d
  FROM pm_completions WHERE scope_item_id IS NOT NULL
  GROUP BY 1,2,3 HAVING count(*) > 1) q;

CREATE TEMP TABLE _fix AS
SELECT c.asset_id, c.scope_item_id, c.hive_id, c.worker_name, c.status, c.completed_at,
       (SELECT count(*) FROM pm_completions) AS n0
FROM pm_completions c WHERE c.scope_item_id IS NOT NULL LIMIT 1;

BEGIN;
-- TEETH: same scope item, same worker, same UTC day must be refused by the index
INSERT INTO pm_completions (asset_id, scope_item_id, hive_id, worker_name, status, completed_at)
SELECT asset_id, scope_item_id, hive_id, worker_name, status, completed_at FROM _fix;
ROLLBACK;

BEGIN;
-- CONTROL: the same pair on a DIFFERENT day must be accepted, or the index rejects everything
INSERT INTO pm_completions (asset_id, scope_item_id, hive_id, worker_name, status, completed_at)
SELECT asset_id, scope_item_id, hive_id, worker_name, status, completed_at - INTERVAL '3650 days' FROM _fix;
SELECT 'control_other_day_accepted | ' || EXISTS (
  SELECT 1 FROM pm_completions c JOIN _fix f ON c.scope_item_id = f.scope_item_id
   WHERE c.completed_at = f.completed_at - INTERVAL '3650 days');
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM pm_completions) = (SELECT n0 FROM _fix));
