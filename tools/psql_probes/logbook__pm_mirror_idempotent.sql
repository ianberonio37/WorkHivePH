-- pm_mirror_idempotent: mirroring a logbook PM into pm_completions cannot double-count — the
-- partial dedup index refuses a same-day clone (23505) while a NEXT-DAY completion by the same
-- person on the same item is accepted; rollback restores.
-- expect: dedup_index_live \| t
-- expect: duplicate key value violates unique constraint
-- expect: next_day_accepted \| t
-- expect: restored \| t
SELECT 'dedup_index_live | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE indexname='pm_completions_dedup_uidx');
CREATE TEMP TABLE _pm AS
SELECT scope_item_id, worker_name, completed_at, hive_id, asset_id, auth_uid,
       (SELECT count(*) FROM pm_completions) AS n0
FROM pm_completions WHERE scope_item_id IS NOT NULL LIMIT 1;
BEGIN;
INSERT INTO pm_completions (scope_item_id, worker_name, completed_at, hive_id, asset_id, auth_uid, status)
SELECT scope_item_id, worker_name, completed_at, hive_id, asset_id, auth_uid, 'done' FROM _pm;
ROLLBACK;
BEGIN;
INSERT INTO pm_completions (scope_item_id, worker_name, completed_at, hive_id, asset_id, auth_uid, status)
-- ★THE FREE DAY MUST BE COMPUTED, NOT ASSUMED (fixed 2026-08-31). This read `completed_at +
-- interval '1 day'` and took the refusal that came back as proof the invariant had broken. It had
-- not: the fixture picks the first completion row, and that worker had completions on CONSECUTIVE
-- days, so "tomorrow" was already taken and the dedup index refused it exactly as designed - the
-- probe asserted a same-day clash while standing on one. Anchoring to this pair's LATEST completion
-- makes the next day free by construction, whatever the seed data looks like.
SELECT scope_item_id, worker_name,
       (SELECT max(c.completed_at) FROM pm_completions c
         WHERE c.scope_item_id = _pm.scope_item_id AND c.worker_name = _pm.worker_name)
         + interval '1 day',
       hive_id, asset_id, auth_uid, 'done' FROM _pm;
SELECT 'next_day_accepted | ' || ((SELECT count(*) FROM pm_completions) = (SELECT n0 + 1 FROM _pm));
ROLLBACK;
SELECT 'restored | ' || ((SELECT count(*) FROM pm_completions) = (SELECT n0 FROM _pm));
DROP TABLE _pm;
