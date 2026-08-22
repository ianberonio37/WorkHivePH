-- closed_snapshot_frozen: one snapshot per (hive, phase, period) — the upsert's conflict target is a
-- real UNIQUE index, so a recompute OVERWRITES its own row instead of accumulating drifting copies;
-- periods are the four rolling windows and phases the four analysis stages, nothing else.
-- expect: unique_conflict_target \| t
-- expect: rows \| [0-9]+
-- expect: rogue_periods \| 0
-- expect: rogue_phases \| 0
-- expect: no_duplicate_cells \| t
SELECT 'unique_conflict_target | ' || EXISTS (
  SELECT 1 FROM pg_indexes WHERE tablename='analytics_snapshots'
   AND indexdef ILIKE '%UNIQUE%' AND indexdef ILIKE '%hive_id%'
   AND indexdef ILIKE '%phase%' AND indexdef ILIKE '%period_days%');
SELECT 'rows | ' || count(*) FROM analytics_snapshots;
SELECT 'rogue_periods | ' || count(*) FROM analytics_snapshots WHERE period_days NOT IN (7,14,30,90);
SELECT 'rogue_phases | ' || count(*) FROM analytics_snapshots
WHERE phase NOT IN ('descriptive','diagnostic','predictive','prescriptive');
SELECT 'no_duplicate_cells | ' || NOT EXISTS (
  SELECT 1 FROM analytics_snapshots GROUP BY hive_id, phase, period_days HAVING count(*) > 1);
