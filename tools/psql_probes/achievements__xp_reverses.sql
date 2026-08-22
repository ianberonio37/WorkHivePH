-- xp_reverses: deleting XP-earning work reverses its XP (mig ...061): trg_logbook_xp_reverse is an
-- AFTER DELETE trigger on logbook, and deleting a logbook row that earned XP writes a NEGATIVE
-- xp_earned row stamped reversed_at. Teeth inside BEGIN/ROLLBACK on a live logbook row that has an
-- achievement_xp_log entry; the rollback restores both tables (counts printed to prove it).
-- expect: trigger_present \| t
-- expect: reversal_written \| t
-- expect: reversal_negative \| t
-- expect: counts_restored \| t
SELECT 'trigger_present | ' || EXISTS (
  SELECT 1 FROM pg_trigger WHERE tgrelid = 'logbook'::regclass AND tgname = 'trg_logbook_xp_reverse');

CREATE TEMP TABLE _fix2 AS
SELECT x.source_id AS log_id, x.worker_name,
       (SELECT count(*) FROM achievement_xp_log) AS xp_n0,
       (SELECT count(*) FROM logbook) AS log_n0
FROM achievement_xp_log x
JOIN logbook l ON l.id = x.source_id
WHERE x.source_action LIKE 'logbook%' AND x.reversed_at IS NULL AND x.xp_earned > 0
LIMIT 1;

BEGIN;
DELETE FROM logbook WHERE id = (SELECT log_id FROM _fix2);
SELECT 'reversal_written | ' || EXISTS (
  SELECT 1 FROM achievement_xp_log
  WHERE source_id = (SELECT log_id FROM _fix2) AND xp_earned < 0);
SELECT 'reversal_negative | ' || (
  SELECT min(xp_earned) < 0 FROM achievement_xp_log
  WHERE source_id = (SELECT log_id FROM _fix2) AND xp_earned < 0);
ROLLBACK;

SELECT 'counts_restored | ' ||
  (((SELECT count(*) FROM achievement_xp_log) = (SELECT xp_n0 FROM _fix2))
   AND ((SELECT count(*) FROM logbook) = (SELECT log_n0 FROM _fix2)));
