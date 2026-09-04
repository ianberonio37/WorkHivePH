-- foreign_entry_refused_as_data (logbook): a worker cannot edit or delete ANOTHER worker's entry, and
-- the refusal is DATA - enforced by RLS in the database - not a button hidden in the page. A UI-only
-- guard is not a guard: the same request from a console, a stale tab or a second client sails through.
-- The mechanism is deliberately asymmetric and worth stating, because the two halves FAIL DIFFERENTLY:
--   SELECT is hive-wide (a teammate's entry is readable - that is the point of a shared logbook),
--   UPDATE and DELETE carry USING (auth_uid = auth.uid()).
-- A USING clause does not RAISE. It FILTERS - so a foreign edit reports success and touches ZERO rows.
-- The probe therefore counts affected rows rather than waiting for an error that will never come, and
-- proves the control case too: the same statement on the worker's OWN entry updates exactly one row,
-- so "0 rows" is a refusal and not a broken query.
-- expect: fixture_two_workers \| t
-- expect: peer_entry_is_readable \| t
-- expect: foreign_update_touched \| 0
-- expect: foreign_delete_touched \| 0
-- expect: own_update_touched \| 1
-- expect: rows_restored_after_rollback \| t
CREATE TEMP TABLE _lb AS
SELECT a.auth_uid AS me,
       (SELECT l.id FROM logbook l WHERE l.auth_uid = a.auth_uid LIMIT 1) AS my_entry,
       (SELECT l.id FROM logbook l WHERE l.auth_uid IS NOT NULL AND l.auth_uid <> a.auth_uid
          AND l.hive_id = a.hive_id LIMIT 1) AS peer_entry,
       (SELECT count(*) FROM logbook) AS n0
FROM (SELECT DISTINCT l.auth_uid, l.hive_id FROM logbook l
       WHERE l.auth_uid IS NOT NULL AND l.hive_id IS NOT NULL) a
WHERE EXISTS (SELECT 1 FROM logbook p WHERE p.hive_id = a.hive_id AND p.auth_uid IS NOT NULL
                AND p.auth_uid <> a.auth_uid)
LIMIT 1;
GRANT SELECT ON _lb TO authenticated;
SELECT 'fixture_two_workers | ' || ((SELECT my_entry FROM _lb) IS NOT NULL AND (SELECT peer_entry FROM _lb) IS NOT NULL);

BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT me FROM _lb)::text, 'role','authenticated')::text, true);
-- the shared-logbook half: the teammate's entry IS visible
SELECT 'peer_entry_is_readable | ' || EXISTS (SELECT 1 FROM logbook WHERE id = (SELECT peer_entry FROM _lb));

-- Counted in ONE statement each: the assumed role cannot create temp tables, and a CTE that
-- RETURNINGs the affected rows measures exactly what a USING clause silently filters away.
WITH u AS (UPDATE logbook SET action = COALESCE(action,'') || ' WH-PROBE-EDIT'
            WHERE id = (SELECT peer_entry FROM _lb) RETURNING 1)
SELECT 'foreign_update_touched | ' || count(*) FROM u;

WITH d AS (DELETE FROM logbook WHERE id = (SELECT peer_entry FROM _lb) RETURNING 1)
SELECT 'foreign_delete_touched | ' || count(*) FROM d;

-- CONTROL: the identical statement on the worker's OWN entry must land
WITH u AS (UPDATE logbook SET action = COALESCE(action,'') || ' WH-PROBE-EDIT'
            WHERE id = (SELECT my_entry FROM _lb) RETURNING 1)
SELECT 'own_update_touched | ' || count(*) FROM u;
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM logbook) = (SELECT n0 FROM _lb));
DROP TABLE _lb;
