-- badge_uniqueness (skillmatrix): a worker cannot hold the same badge twice - enforced by the
-- DATABASE, not by whichever code path happens to award it. This is the DB-PROVABLE HALF of the
-- `one_submit_one_attempt` oracle ("a double-submit creates neither a second attempt nor a second
-- badge"), and it is deliberately only that half.
--
-- ★WHAT THIS DOES NOT PROVE, MEASURED RATHER THAN ASSUMED (2026-09-10). The ATTEMPT half has NO
-- database enforcement at all: `skill_exam_attempts` carries one index (its primary key on `id`),
-- ZERO unique or exclusion constraints, and its only trigger is `trg_daily_cap_skill_exams` -
-- `check_daily_row_cap(50/day per worker)`, an abuse guard, not a dedup. A double-submit that gets
-- past the client's lock DOES create two attempt rows. That is arguably right: without an
-- idempotency key the database cannot tell a double-submit from a legitimate retake, and retakes are
-- a real product behaviour. So the attempt half stays a client guarantee and stays live-walk
-- evidence; a psql recipe claiming it would bank a claim the schema refutes.
--
-- Teeth both directions inside BEGIN/ROLLBACK: the duplicate insert must be REFUSED (23505), and a
-- control insert (same worker, a badge_key they do not yet hold) must be ACCEPTED - that is what
-- separates a working uniqueness rule from a table that rejects everything. Fixtures are derived
-- from live rows, so the probe grounds itself and never invents a worker.
-- expect: unique_index_present \| t
-- expect: duplicate key value violates unique constraint
-- expect: control_accepted \| t
-- expect: count_restored_after_rollback \| t
-- expect: attempts_have_no_dedup_rule \| t
SELECT 'unique_index_present | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename = 'skill_badges'
   AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%worker_name%' AND indexdef ILIKE '%badge_key%');

-- the negative half of the claim, asserted rather than left to a comment: nothing in the schema
-- dedups an attempt, so this recipe is honest about covering only the badge.
SELECT 'attempts_have_no_dedup_rule | ' || (
  (SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid
    WHERE t.relname = 'skill_exam_attempts' AND c.contype IN ('u','x')) = 0
  AND (SELECT count(*) FROM pg_indexes
        WHERE tablename = 'skill_exam_attempts' AND indexdef ILIKE '%UNIQUE%'
          AND indexdef NOT ILIKE '%(id)%') = 0);

CREATE TEMP TABLE _bfix AS
SELECT sb.worker_name,
       sb.badge_key                              AS held_badge,
       sb.discipline, sb.level,
       'probe-badge-' || substr(md5(random()::text), 1, 8) AS free_badge,
       'probe-discipline-' || substr(md5(random()::text), 1, 8) AS probe_discipline,
       (SELECT count(*) FROM skill_badges)       AS n0
FROM skill_badges sb
LIMIT 1;

BEGIN;
-- the duplicate: must raise 23505 (printed to stderr; ON_ERROR_STOP=0 keeps the session alive)
INSERT INTO skill_badges (worker_name, badge_key, discipline, level)
SELECT worker_name, held_badge, discipline, level FROM _bfix;
ROLLBACK;

BEGIN;
-- the control: the SAME worker, a badge_key they do not hold, must be accepted - otherwise the
-- refusal above proves only that the table rejects everything.
-- Two schema facts the first two drafts each learned the hard way, recorded so the next reader does
-- not: `level` is an INTEGER (draft 1 wrote `level || '-probe'`, which is text and failed the
-- column), and it carries CHECK (level >= 1 AND level <= 5) (draft 2 used max()+900 to dodge the
-- (worker_name, discipline, level) unique index and hit the check instead). Both times the control
-- silently never ran and its expectation read as MISSING - which looks identical to a product
-- finding and is not one. The free axis is DISCIPLINE: plain text, no check, and a probe value
-- cannot collide with a real one.
INSERT INTO skill_badges (worker_name, badge_key, discipline, level)
SELECT worker_name, free_badge, probe_discipline, level FROM _bfix;
SELECT 'control_accepted | ' || ((SELECT count(*) FROM skill_badges) = (SELECT n0 FROM _bfix) + 1);
ROLLBACK;

-- ★A COUNT-BASED RESTORATION CHECK IS BROKEN BY ANY CONCURRENT WRITER (2026-09-10). Comparing
-- count-at-start with count-at-end reported `false` in a sibling recipe while its rollbacks had
-- worked perfectly - an archetype walk had written two real rows between the readings. A probe
-- that fails when the platform is BUSY teaches people to re-run reds until they go green. The
-- assertions below are about THIS probe's own residue, or about the invariant itself, so another
-- writer cannot move them.
SELECT 'count_restored_after_rollback | ' || (
  (SELECT count(*) FROM skill_badges
    WHERE badge_key LIKE 'probe-badge-%' OR discipline LIKE 'probe-discipline-%') = 0);
DROP TABLE _bfix;
