-- consumers_reconcile: every consumer reads the SAME derived truth — v_logbook_truth is a live VIEW
-- (relkind 'v', derived at read, no materialised copy to drift), so a base-row change is visible to
-- all 12 pages + 2 edge fns at the next read. Teeth: flip one maintenance_type in-txn, the view
-- reflects it immediately; rollback restores.
-- expect: is_live_view \| t
-- expect: view_reflects_change \| t
-- expect: restored \| t
SELECT 'is_live_view | ' || (relkind = 'v') FROM pg_class WHERE relname = 'v_logbook_truth';
CREATE TEMP TABLE _cr AS
SELECT id, maintenance_type FROM logbook WHERE maintenance_type = 'Inspection' LIMIT 1;
BEGIN;
UPDATE logbook SET maintenance_type = 'Breakdown / Corrective' WHERE id = (SELECT id FROM _cr);
SELECT 'view_reflects_change | ' || (
  (SELECT maintenance_type FROM v_logbook_truth WHERE id = (SELECT id FROM _cr))
  = 'Breakdown / Corrective');
ROLLBACK;
SELECT 'restored | ' || (
  (SELECT maintenance_type FROM v_logbook_truth WHERE id = (SELECT id FROM _cr)) = 'Inspection');
DROP TABLE _cr;
