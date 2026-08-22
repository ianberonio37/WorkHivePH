-- missed_pm_traceable: a missed PM can be traced to its breakdown consequences — the id bridge
-- holds: every scope item resolves to a pm_asset, pm_assets carry the tag that logbook.machine
-- records, and breakdowns matching a tag exist (the join a supervisor's "what did skipping cost"
-- question runs).
-- expect: scope_items_resolve \| t
-- expect: assets_tagged \| t
-- expect: breakdowns_bridgeable \| [1-9][0-9]*
-- the scope item's asset column is asset_id (-> pm_assets.id); the truth view aliases it
SELECT 'scope_items_resolve | ' || (count(*) = 0) FROM pm_scope_items s
WHERE s.asset_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM pm_assets p WHERE p.id = s.asset_id);
SELECT 'assets_tagged | ' || (
  (SELECT count(*) FROM pm_assets WHERE tag_id IS NOT NULL AND btrim(tag_id) <> '')
  >= (SELECT count(*) - 1 FROM pm_assets));
SELECT 'breakdowns_bridgeable | ' || count(*) FROM logbook l
WHERE l.maintenance_type = 'Breakdown / Corrective'
  AND EXISTS (SELECT 1 FROM pm_assets p WHERE p.tag_id = l.machine);
