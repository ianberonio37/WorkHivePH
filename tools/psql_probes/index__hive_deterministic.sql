-- hive_deterministic (index): a multi-hive worker resolves to exactly ONE hive, deterministically -
-- the .maybeSingle()/limit(1) class that used to bounce multi-hive users. The half that bit before
-- (reading only one membership) is a client concern and stays live-walk; the half the oracle actually
-- names - DETERMINISTICALLY - is a database question, because a pick is only deterministic if the key
-- it orders by is TOTAL over that worker's memberships.
--
-- ★TODAY IT IS DETERMINISTIC BY LUCK, NOT BY CONSTRUCTION. Three workers hold two active memberships
-- each - Ben Ocampo (two fleets), Christine Dizon and Pablo Aguilar (Lucena + Manila) - and none of
-- them has a tie on `joined_at`, so ordering by that column alone happens to pick the same hive every
-- time. It would stop doing so the moment two memberships were created in one transaction, which is
-- exactly how an invite flow that adds a person to two hives at once would write them. A key that is
-- unique in today's data is not the same as a key that is unique.
--
-- So: assert the population (three multi-hive workers, or this proves nothing), assert no tie exists
-- now, and then MANUFACTURE the tie and show that `joined_at` alone becomes ambiguous while
-- `(joined_at, hive_id)` stays total. The teeth are the whole point - without them this recipe passes
-- on a corpus that simply has not hit the case yet.
-- expect: multi_hive_workers \| [1-9][0-9]*
-- expect: no_joined_at_tie_today \| t
-- expect: joined_at_alone_becomes_ambiguous \| t
-- expect: joined_at_plus_hive_id_stays_total \| t
-- expect: rows_restored_after_rollback \| t
CREATE TEMP VIEW _multi AS
SELECT worker_name FROM hive_members WHERE status = 'active'
 GROUP BY worker_name HAVING count(*) > 1;

SELECT 'multi_hive_workers | ' || (SELECT count(*) FROM _multi);

SELECT 'no_joined_at_tie_today | ' || (
  (SELECT count(*) FROM (
     SELECT hm.worker_name, hm.joined_at
     FROM hive_members hm JOIN _multi m ON m.worker_name = hm.worker_name
     WHERE hm.status = 'active'
     GROUP BY hm.worker_name, hm.joined_at HAVING count(*) > 1) x) = 0);

CREATE TEMP TABLE _hfix AS SELECT count(*) AS n0 FROM hive_members;

BEGIN;
-- TEETH: give one multi-hive worker the SAME joined_at on both memberships - the invite-both-at-once
-- shape - and ask each candidate key whether it still names exactly one row.
UPDATE hive_members SET joined_at = (
    SELECT min(joined_at) FROM hive_members h2
     WHERE h2.worker_name = hive_members.worker_name AND h2.status = 'active')
 WHERE status = 'active'
   AND worker_name = (SELECT worker_name FROM _multi LIMIT 1);

-- ordering by joined_at alone: more than one row now shares the minimum, so "the first" is arbitrary
SELECT 'joined_at_alone_becomes_ambiguous | ' || (
  (SELECT count(*) FROM hive_members hm
    WHERE hm.status = 'active'
      AND hm.worker_name = (SELECT worker_name FROM _multi LIMIT 1)
      AND hm.joined_at = (SELECT min(joined_at) FROM hive_members h3
                           WHERE h3.worker_name = hm.worker_name AND h3.status = 'active')) > 1);

-- ordering by (joined_at, hive_id): the tuple is unique because hive_id is, so exactly one row is first
SELECT 'joined_at_plus_hive_id_stays_total | ' || (
  (SELECT count(*) FROM (
     SELECT DISTINCT ON (worker_name) worker_name, hive_id
     FROM hive_members
     WHERE status = 'active'
       AND worker_name = (SELECT worker_name FROM _multi LIMIT 1)
     ORDER BY worker_name, joined_at ASC, hive_id ASC) y) = 1);
ROLLBACK;

-- ★A COUNT-BASED RESTORATION CHECK IS BROKEN BY ANY CONCURRENT WRITER (2026-09-10). Comparing
-- count-at-start with count-at-end reported `false` in a sibling recipe while its rollbacks had
-- worked perfectly - an archetype walk had written two real rows between the readings. A probe
-- that fails when the platform is BUSY teaches people to re-run reds until they go green. The
-- assertions below are about THIS probe's own residue, or about the invariant itself, so another
-- writer cannot move them.
-- the teeth UPDATE joined_at rather than inserting, so restoration means no tie survives.
SELECT 'rows_restored_after_rollback | ' || (
  (SELECT count(*) FROM (
     SELECT hm.worker_name, hm.joined_at FROM hive_members hm
      WHERE hm.status='active' AND hm.worker_name IN (SELECT worker_name FROM hive_members
            WHERE status='active' GROUP BY worker_name HAVING count(*) > 1)
      GROUP BY hm.worker_name, hm.joined_at HAVING count(*) > 1) z) = 0);
DROP TABLE _hfix;
