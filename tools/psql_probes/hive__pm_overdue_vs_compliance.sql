-- pm_overdue_vs_compliance: the two PM figures a supervisor sees are DIFFERENT measures and each is
-- internally coherent — "overdue" counts distinct ASSETS with is_overdue out of assets in scope
-- (v_pm_scope_items_truth), while compliance is total_completed/total_scheduled over 90d
-- (get_pm_compliance_smrp, SMRP 2.1.1). The ratio is recomputed from the fn's own numerator and
-- denominator so the pct cannot drift from its parts.
-- expect: scope_positive \| t
-- expect: overdue_le_scope \| t
-- expect: compliance_ratio_coherent \| t
CREATE TEMP TABLE _pm AS
SELECT (SELECT count(DISTINCT asset_name) FROM v_pm_scope_items_truth WHERE is_overdue) AS overdue,
       (SELECT count(DISTINCT asset_name) FROM v_pm_scope_items_truth) AS scope,
       -- a HIVE-scoped item: the vehicle seed added SOLO (hive_id NULL) scope items, and
       -- get_pm_compliance_smrp(NULL) is the solo path that RAISEs without a signed-in caller
       -- (this recipe runs as postgres). Target a real hive so the fn takes its hive path.
       (SELECT hive_id FROM v_pm_scope_items_truth WHERE hive_id IS NOT NULL LIMIT 1) AS hive_id;
SELECT 'scope_positive | ' || ((SELECT scope FROM _pm) > 0);
SELECT 'overdue_le_scope | ' || ((SELECT overdue FROM _pm) <= (SELECT scope FROM _pm));
CREATE TEMP TABLE _cmp AS
SELECT get_pm_compliance_smrp((SELECT hive_id FROM _pm)) AS j;
SELECT 'compliance_ratio_coherent | ' || (
  SELECT (j->>'total_completed')::numeric <= (j->>'total_scheduled')::numeric
     AND ((j->>'total_scheduled')::numeric = 0 OR
          abs((j->>'overall_pct')::numeric -
              round(100.0 * (j->>'total_completed')::numeric / (j->>'total_scheduled')::numeric, 1)) <= 0.11)
  FROM _cmp);
DROP TABLE _cmp; DROP TABLE _pm;
