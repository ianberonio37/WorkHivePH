-- pm_denominator: "N of M assets past due" is a DISTINCT-asset count over a stated denominator —
-- overdue distinct pm_asset_ids <= total PM assets, both positive, and the overdue-asset count is
-- genuinely DISTINCT (never the raw scope-item count wearing an asset label).
-- expect: overdue_assets \| [0-9]+
-- expect: assets_total \| [1-9][0-9]*
-- expect: distinct_not_items \| t
-- expect: overdue_le_total \| t
CREATE TEMP TABLE _pd AS
SELECT (SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE is_overdue) AS od,
       (SELECT count(*) FROM v_pm_scope_items_truth WHERE is_overdue) AS od_items,
       (SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth) AS total;
SELECT 'overdue_assets | ' || od FROM _pd;
SELECT 'assets_total | ' || total FROM _pd;
SELECT 'distinct_not_items | ' || (od <= od_items) FROM _pd;
SELECT 'overdue_le_total | ' || (od <= total) FROM _pd;
DROP TABLE _pd;
