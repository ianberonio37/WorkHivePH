-- risk_same_formula: every surface's risk number is the SAME formula — v_risk_truth is DISTINCT ON
-- (hive_id, asset_name) newest-first over asset_risk_scores (latest score per asset, no second
-- derivation), and no asset appears twice in the view.
-- expect: view_is_latest_per_asset \| t
-- expect: duplicate_assets_in_view \| 0
-- expect: view_rows \| [1-9][0-9]*
SELECT 'view_is_latest_per_asset | ' || (
  pg_get_viewdef('v_risk_truth'::regclass) ILIKE '%DISTINCT ON%'
  AND pg_get_viewdef('v_risk_truth'::regclass) ILIKE '%asset_risk_scores%'
  AND pg_get_viewdef('v_risk_truth'::regclass) ILIKE '%generated_at DESC%');
SELECT 'duplicate_assets_in_view | ' || count(*) FROM (
  SELECT hive_id, asset_name FROM v_risk_truth GROUP BY hive_id, asset_name HAVING count(*) > 1) d;
SELECT 'view_rows | ' || count(*) FROM v_risk_truth;
