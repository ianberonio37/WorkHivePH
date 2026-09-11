-- carry_count_true (shift-brain): the carry-over count is the true size of its own set, not the size
-- of what fits on screen. `payload.carry_forward` holds the hive's OPEN logbook entries, and the page
-- counts that array - so the question the database can answer is whether the STORED array is the whole
-- set or an already-truncated one. A count taken from a truncated array is wrong before the page ever
-- renders it, and no amount of client-side care can fix that.
--
-- ★A CAP I THOUGHT I HAD FOUND, AND THE SOURCE REFUTED (2026-09-10, worth recording because the
-- reading was persuasive). The length distribution is 9 (53 plans), 10 (12), 11 (4), 12 (34),
-- 25 (10), 0 (21) - clustered low, then TEN plans sitting on exactly 25 with nothing whatsoever
-- between 13 and 24. That is the classic signature of a write-time cap, and all ten declare
-- `caps.carry_forward = false`, which would have made the flag a lie. It is not: Manila Electronics
-- Assembly genuinely holds 25 open logbook entries, Lucena 12, Baguio 10. The clustering is three
-- hives with three different true counts, not a ceiling. The shape of a distribution is a hypothesis;
-- the source table is the answer.
--
-- So this asserts the real invariant - the stored set tracks the hive's own open entries and the cap
-- flag tells the truth - with teeth proving the detector fires on a plan that IS silently truncated.
-- expect: plans_checked \| [1-9][0-9]*
-- expect: carry_is_always_an_array \| t
-- expect: no_silent_truncation \| t
-- expect: max_length_differs_by_hive \| t
-- expect: detector_sees_a_silent_truncation \| t
-- expect: rows_restored_after_rollback \| t
SELECT 'plans_checked | ' || (SELECT count(*) FROM shift_plans WHERE payload IS NOT NULL);

SELECT 'carry_is_always_an_array | ' || (
  (SELECT count(*) FROM shift_plans
    WHERE payload IS NOT NULL AND jsonb_typeof(payload->'carry_forward') <> 'array') = 0);

-- THE INVARIANT: a plan may never hold MORE carry-over rows than its hive has open entries, and may
-- never hold FEWER while claiming it was not capped. The second half is the one that matters, and it
-- is checked only against the NEWEST plan per hive - an older plan legitimately differs because an
-- entry closed after it was generated, and comparing a point-in-time snapshot to today's table would
-- manufacture failures out of the product working correctly.
CREATE TEMP VIEW _newest_plan AS
SELECT DISTINCT ON (hive_id) hive_id, payload
FROM shift_plans WHERE payload IS NOT NULL
ORDER BY hive_id, generated_at DESC;

SELECT 'no_silent_truncation | ' || NOT EXISTS (
  SELECT 1 FROM _newest_plan np
   WHERE coalesce(np.payload->'caps'->>'carry_forward', 'false') = 'false'
     AND jsonb_array_length(np.payload->'carry_forward')
         < (SELECT count(*) FROM logbook l WHERE l.hive_id = np.hive_id AND l.status = 'Open'));

-- non-vacuity: if every hive's maximum were the same number, a global ceiling would be the simpler
-- explanation and the check above would be measuring a constant
SELECT 'max_length_differs_by_hive | ' || (
  (SELECT count(DISTINCT m) FROM (
     SELECT max(jsonb_array_length(payload->'carry_forward')) AS m
     FROM shift_plans WHERE payload IS NOT NULL GROUP BY hive_id) x) > 1);

CREATE TEMP TABLE _cfix AS SELECT count(*) AS n0 FROM shift_plans;

BEGIN;
-- TEETH: truncate one newest plan's carry list to a single row while leaving caps saying "not capped".
-- The detector above must see it; if it cannot, the invariant is unguarded.
UPDATE shift_plans SET payload = jsonb_set(
         jsonb_set(payload, '{carry_forward}', jsonb_build_array(payload->'carry_forward'->0)),
         '{caps,carry_forward}', 'false'::jsonb)
 WHERE id = (SELECT p.id FROM shift_plans p
              JOIN (SELECT hive_id, max(generated_at) AS g FROM shift_plans
                     WHERE payload IS NOT NULL GROUP BY hive_id) n
                ON n.hive_id = p.hive_id AND n.g = p.generated_at
             WHERE jsonb_array_length(p.payload->'carry_forward') > 1 LIMIT 1);

SELECT 'detector_sees_a_silent_truncation | ' || EXISTS (
  SELECT 1 FROM (SELECT DISTINCT ON (hive_id) hive_id, payload FROM shift_plans
                  WHERE payload IS NOT NULL ORDER BY hive_id, generated_at DESC) np
   WHERE coalesce(np.payload->'caps'->>'carry_forward', 'false') = 'false'
     AND jsonb_array_length(np.payload->'carry_forward')
         < (SELECT count(*) FROM logbook l WHERE l.hive_id = np.hive_id AND l.status = 'Open'));
ROLLBACK;

-- ★A COUNT-BASED RESTORATION CHECK IS BROKEN BY ANY CONCURRENT WRITER (2026-09-10). Comparing
-- count-at-start with count-at-end reported `false` in a sibling recipe while its rollbacks had
-- worked perfectly - an archetype walk had written two real rows between the readings. A probe
-- that fails when the platform is BUSY teaches people to re-run reds until they go green. The
-- assertions below are about THIS probe's own residue, or about the invariant itself, so another
-- writer cannot move them.
-- the teeth truncate a payload rather than inserting, so restoration means the invariant holds again.
SELECT 'rows_restored_after_rollback | ' || NOT EXISTS (
  SELECT 1 FROM (SELECT DISTINCT ON (hive_id) hive_id, payload FROM shift_plans
                  WHERE payload IS NOT NULL ORDER BY hive_id, generated_at DESC) np
   WHERE coalesce(np.payload->'caps'->>'carry_forward','false') = 'false'
     AND jsonb_array_length(np.payload->'carry_forward')
         < (SELECT count(*) FROM logbook l WHERE l.hive_id = np.hive_id AND l.status = 'Open'));
DROP TABLE _cfix;
