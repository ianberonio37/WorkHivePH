-- no_silent_amend_after_signoff: an edit that raced someone else's change matches ZERO rows instead
-- of overwriting — the optimistic-concurrency chain rests on updated_at moving under every write,
-- which trg_logbook_touch_updated_at guarantees. Teeth: update a row in-txn, updated_at MOVES.
-- expect: touch_trigger_live \| t
-- expect: updated_at_moves \| t
-- expect: restored \| t
SELECT 'touch_trigger_live | ' || EXISTS (
  SELECT 1 FROM pg_trigger WHERE tgrelid='logbook'::regclass
   AND tgname ILIKE '%touch_updated%' AND tgenabled <> 'D');
CREATE TEMP TABLE _oc AS
SELECT id, updated_at FROM logbook ORDER BY created_at DESC LIMIT 1;
BEGIN;
UPDATE logbook SET action = action WHERE id = (SELECT id FROM _oc);  -- logbook has no notes col; a no-op SET still fires the touch trigger
SELECT 'updated_at_moves | ' || (
  (SELECT updated_at FROM logbook WHERE id = (SELECT id FROM _oc))
  IS DISTINCT FROM (SELECT updated_at FROM _oc));
ROLLBACK;
SELECT 'restored | ' || (
  (SELECT updated_at FROM logbook WHERE id = (SELECT id FROM _oc))
  IS NOT DISTINCT FROM (SELECT updated_at FROM _oc));
DROP TABLE _oc;
