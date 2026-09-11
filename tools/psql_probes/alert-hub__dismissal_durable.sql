-- dismissal_durable (alert-hub): a dismissed alert stays dismissed, and pressing Handled twice leaves
-- EXACTLY ONE row - enforced by the DATABASE (unique index on hive_id, alert_key), not by whichever
-- code path happens to write it. This is the DB-provable half of the cell's claim; the reload and the
-- realtime-push halves are browser observations and stay live-walk evidence.
--
-- ★AND THE SCOPE IS HIVE-WIDE, WHICH THE ORACLE ASKS ABOUT BY NAME. The cell's sibling
-- (`dismissal_scope_stated`) says "a dismissal is scoped to its dismisser, or explicitly to the hive,
-- AND the surface says which - one person quietly blinding the team is the failure mode". The unique
-- key settles which it is: (hive_id, alert_key), with no actor in it. So one member's Handled DOES
-- hide the alert from everyone in that hive. That is a design choice, not a defect - and it is only
-- safe while the surface says so, which is a screen claim this recipe deliberately does not make.
-- `actor` is asserted NOT NULL on the live row so the dismissal is at least attributable.
--
-- Teeth both directions inside BEGIN/ROLLBACK: the duplicate must be REFUSED (23505), and a control
-- insert with a different alert_key in the same hive must be ACCEPTED - otherwise the refusal proves
-- only that the table rejects everything. Self-grounded: the fixture is a live row.
-- expect: unique_on_hive_and_key \| t
-- expect: scope_is_hive_not_actor \| t
-- expect: duplicate key value violates unique constraint
-- expect: control_accepted \| t
-- expect: actor_recorded \| t
-- expect: count_restored_after_rollback \| t
SELECT 'unique_on_hive_and_key | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename = 'alert_dismissals'
   AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%hive_id%' AND indexdef ILIKE '%alert_key%');

-- the scope question, answered from the index rather than from the UI: an actor in the unique key
-- would make a dismissal personal; its absence makes it hive-wide.
SELECT 'scope_is_hive_not_actor | ' || NOT EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename = 'alert_dismissals'
   AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%alert_key%' AND indexdef ILIKE '%actor%');

CREATE TEMP TABLE _dfix AS
SELECT ad.hive_id, ad.alert_key, ad.actor,
       'probe-key-' || substr(md5(random()::text), 1, 10) AS free_key,
       (SELECT count(*) FROM alert_dismissals)            AS n0
FROM alert_dismissals ad LIMIT 1;

SELECT 'actor_recorded | ' || ((SELECT actor FROM _dfix) IS NOT NULL);

BEGIN;
-- the duplicate: same hive, same alert_key - must raise 23505
INSERT INTO alert_dismissals (hive_id, alert_key, action, actor)
SELECT hive_id, alert_key, 'handled', actor FROM _dfix;
ROLLBACK;

BEGIN;
-- the control: same hive, a key nobody has dismissed - must be accepted
INSERT INTO alert_dismissals (hive_id, alert_key, action, actor)
SELECT hive_id, free_key, 'handled', actor FROM _dfix;
SELECT 'control_accepted | ' || ((SELECT count(*) FROM alert_dismissals) = (SELECT n0 FROM _dfix) + 1);
ROLLBACK;

-- ★A COUNT-BASED RESTORATION CHECK IS BROKEN BY ANY CONCURRENT WRITER (2026-09-10). Comparing
-- count-at-start with count-at-end reported `false` in a sibling recipe while its rollbacks had
-- worked perfectly - an archetype walk had written two real rows between the readings. A probe
-- that fails when the platform is BUSY teaches people to re-run reds until they go green. The
-- assertions below are about THIS probe's own residue, or about the invariant itself, so another
-- writer cannot move them.
SELECT 'count_restored_after_rollback | ' || (
  (SELECT count(*) FROM alert_dismissals WHERE alert_key LIKE 'probe-key-%') = 0);
DROP TABLE _dfix;
