-- compliance_recomputes: the page's compliance % is get_pm_compliance_smrp recomputed live — the
-- overall percentage equals its own numerator/denominator, per-asset rows cover the asset count,
-- and the standard is named in the payload itself.
-- expect: standard_named \| t
-- expect: overall_equals_parts \| t
-- expect: per_asset_covers \| t
CREATE TEMP TABLE _cr AS
-- a HIVE-scoped item: the vehicle seed added SOLO (hive_id NULL) scope items, and the solo path of
-- get_pm_compliance_smrp(NULL) RAISEs without a signed-in caller (this recipe runs as postgres).
SELECT get_pm_compliance_smrp((SELECT hive_id FROM v_pm_scope_items_truth WHERE hive_id IS NOT NULL LIMIT 1)) AS j;
SELECT 'standard_named | ' || ((SELECT j->>'standard' FROM _cr) ILIKE 'SMRP%');
SELECT 'overall_equals_parts | ' || (
  SELECT (j->>'total_scheduled')::numeric > 0 AND
         abs((j->>'overall_pct')::numeric -
             round(100.0 * (j->>'total_completed')::numeric / (j->>'total_scheduled')::numeric, 1)) <= 0.11
  FROM _cr);
SELECT 'per_asset_covers | ' || (
  SELECT jsonb_array_length(j->'compliance_by_asset') = (j->>'asset_count')::int FROM _cr);
DROP TABLE _cr;
