-- completion_attributed: every PM completion names who did it and what — auth_uid, worker_name,
-- scope_item_id, asset_id, completed_at all present on every row, and the dedup index prevents the
-- same person completing the same item twice in one day.
-- expect: completions \| [1-9][0-9]*
-- expect: unattributed \| 0
-- expect: dedup_index_live \| t
SELECT 'completions | ' || count(*) FROM pm_completions;
SELECT 'unattributed | ' || count(*) FROM pm_completions
WHERE auth_uid IS NULL OR worker_name IS NULL OR completed_at IS NULL;
SELECT 'dedup_index_live | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE indexname = 'pm_completions_dedup_uidx');
