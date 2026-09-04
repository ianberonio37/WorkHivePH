-- T189 (2026-08-28), second instance: v_asset_truth.pm_completed_count also counted SKIPPED PMs.
--
-- The sibling of 20260828000002. That migration fixed v_pm_compliance_truth; this one fixes the
-- per-asset counter, which had the identical defect and drives a tile the Asset Hub labels
-- literally "PM completed":
--
--     ( SELECT count(*) FROM pm_completions pc
--        WHERE pc.hive_id = n.hive_id AND pc.asset_id = n.pm_asset_id ) AS pm_completed_count
--
-- pm_completions holds done AND skipped rows, so a column whose NAME is a claim about completed
-- work counted work that was explicitly recorded as not done. Measured on the local fixture:
-- 47 assets overcounted, 78 phantom completions - every machine whose history includes a skip
-- shows an inflated figure on its own detail page.
--
-- ★THIS ONE ESCAPED THE FIRST SWEEP, AND THE MISS IS THE LESSON. After fixing the compliance view
-- I swept for the class by asking the catalog for every v_*_truth that AGGREGATES but never
-- mentions `status`, and concluded the compliance view was the only instance. v_asset_truth DOES
-- mention status - twice, for the ASSET's own approval state (`status` column, `WHERE status =
-- 'approved'`) - so it was filtered out of the sweep while ignoring status in the one subquery
-- that needed it. A view can honour a column for one purpose and ignore it for another; "mentions
-- the word" is not "filters the rows", and a sweep keyed to vocabulary rather than to the specific
-- aggregate will keep producing that false negative. Found instead by following the CONSUMER -
-- asset-hub's "PM completed" tile - back to its source, which is the check the catalog query
-- could not do.
--
-- Also adds pm_skipped_count, for the same reason as its sibling: removing skips from the
-- numerator without surfacing them anywhere trades an overstatement for a blind spot. Appended
-- LAST because CREATE OR REPLACE VIEW may only add columns at the end.
--
-- ★security_invoker RE-DECLARED: this view carries security_invoker=true and CREATE OR REPLACE
-- silently drops reloptions. Losing it would run the view with owner rights and bypass RLS on
-- asset_nodes/logbook/pm_completions - a tenant-isolation hole opened by a counter fix.

BEGIN;

CREATE OR REPLACE VIEW public.v_asset_truth
WITH (security_invoker = true) AS
SELECT
  id AS asset_id,
  hive_id,
  auth_uid,
  parent_id,
  level,
  tag,
  name,
  iso_class,
  criticality,
  location,
  manufacturer,
  model,
  serial_no,
  install_date,
  external_ids,
  legacy_asset_id,
  pm_asset_id,
  status,
  submitted_by,
  approved_by,
  approved_at,
  created_at,
  updated_at,
  ( SELECT count(*) AS count
      FROM logbook l
     WHERE l.hive_id = n.hive_id AND l.asset_node_id = n.id) AS lifetime_logbook_entries,
  ( SELECT max(l.created_at) AS max
      FROM logbook l
     WHERE l.hive_id = n.hive_id AND l.asset_node_id = n.id
       AND l.maintenance_type = 'Breakdown / Corrective'::text) AS last_failure_at,
  -- the fix: a completion count must count completions
  ( SELECT count(*) AS count
      FROM pm_completions pc
     WHERE pc.hive_id = n.hive_id AND pc.asset_id = n.pm_asset_id
       AND pc.status = 'done'::text) AS pm_completed_count,
  ( SELECT count(*) AS count
      FROM asset_edges e
     WHERE e.hive_id = n.hive_id AND (e.from_node_id = n.id OR e.to_node_id = n.id)) AS edge_count,
  -- appended: the skips the counter above no longer absorbs, so they stay visible somewhere
  ( SELECT count(*) AS count
      FROM pm_completions pc
     WHERE pc.hive_id = n.hive_id AND pc.asset_id = n.pm_asset_id
       AND pc.status = 'skipped'::text) AS pm_skipped_count
FROM asset_nodes n
WHERE status = 'approved'::text;

COMMENT ON VIEW public.v_asset_truth IS
  'Canonical per-asset truth over approved asset_nodes. pm_completed_count counts pm_completions.status = ''done'' ONLY - a skipped PM is recorded non-performance and must never read as a completion (T189, 2026-08-28); skips are surfaced separately as pm_skipped_count.';

GRANT SELECT ON public.v_asset_truth TO anon, authenticated;

COMMIT;
