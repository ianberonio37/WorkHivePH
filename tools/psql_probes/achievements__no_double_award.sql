-- no_double_award: an achievement cannot be awarded twice — enforced by the DATABASE (unique index),
-- not by whichever code path happens to award it. Teeth both directions inside BEGIN/ROLLBACK:
-- the duplicate insert must be REFUSED (23505) and a control insert (same worker, a real defined
-- achievement they do not yet hold) must be ACCEPTED — that is what separates a working uniqueness
-- rule from a table that rejects everything. Self-grounding: fixtures derived from live rows.
-- expect: unique_index_present \| t
-- expect: duplicate key value violates unique constraint
-- expect: control_accepted \| t
-- expect: count_restored_after_rollback \| t
SELECT 'unique_index_present | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename = 'worker_achievements'
  AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%worker_name%' AND indexdef ILIKE '%achievement_id%');

CREATE TEMP TABLE _fix AS
SELECT wa.worker_name, wa.achievement_id AS held,
       (SELECT ad.id FROM achievement_definitions ad
         WHERE ad.id NOT IN (SELECT achievement_id FROM worker_achievements w2
                              WHERE w2.worker_name = wa.worker_name)
         LIMIT 1) AS free_achievement,
       (SELECT count(*) FROM worker_achievements) AS n0
FROM worker_achievements wa
WHERE EXISTS (SELECT 1 FROM achievement_definitions ad
               WHERE ad.id NOT IN (SELECT achievement_id FROM worker_achievements w2
                                    WHERE w2.worker_name = wa.worker_name))
LIMIT 1;

BEGIN;
-- the duplicate: must raise 23505 (printed to stderr; ON_ERROR_STOP=0 keeps the session alive)
INSERT INTO worker_achievements (worker_name, achievement_id)
SELECT worker_name, held FROM _fix;
ROLLBACK;

BEGIN;
INSERT INTO worker_achievements (worker_name, achievement_id)
SELECT worker_name, free_achievement FROM _fix;
SELECT 'control_accepted | ' ||
  ((SELECT count(*) FROM worker_achievements) = (SELECT n0 + 1 FROM _fix));
ROLLBACK;

SELECT 'count_restored_after_rollback | ' ||
  ((SELECT count(*) FROM worker_achievements) = (SELECT n0 FROM _fix));
