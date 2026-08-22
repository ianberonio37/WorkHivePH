-- queue_drains_once: the DB half of the offline queue's exactly-once drain — the drain path is an
-- UPDATE keyed by entry id under the owner-scoped RLS policy, so replaying the same drain twice
-- rewrites the SAME row rather than inserting a duplicate. Teeth: two identical updates in one txn
-- leave ONE row; count unchanged.
-- expect: replay_leaves_one_row \| t
-- expect: count_unchanged \| t
CREATE TEMP TABLE _qd AS
SELECT id, (SELECT count(*) FROM logbook) AS n0 FROM logbook ORDER BY created_at DESC LIMIT 1;
BEGIN;
UPDATE logbook SET action = action WHERE id = (SELECT id FROM _qd);
UPDATE logbook SET action = action WHERE id = (SELECT id FROM _qd);
SELECT 'replay_leaves_one_row | ' ||
  ((SELECT count(*) FROM logbook WHERE id = (SELECT id FROM _qd)) = 1);
ROLLBACK;
SELECT 'count_unchanged | ' || ((SELECT count(*) FROM logbook) = (SELECT n0 FROM _qd));
DROP TABLE _qd;
