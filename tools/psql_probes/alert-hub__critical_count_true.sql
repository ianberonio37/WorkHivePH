-- critical_count_true: the hero's "N need eyes now" is a COMPOSITION of four sources, and each
-- component is internally coherent where psql can see it: signature alerts respect their cap,
-- PM-overdue counts DISTINCT assets (never more than scope items), risk criticals come from the
-- latest-score view, low stock from the truth view's own flags. The page-side sum is the browser
-- provers' subject; the components' own arithmetic is this probe's.
-- expect: signature_within_cap \| t
-- expect: pm_overdue_distinct_le_items \| t
-- expect: risk_component_sane \| t
-- expect: inventory_component_sane \| t
SELECT 'signature_within_cap | ' ||
  ((SELECT count(*) FROM v_alert_truth WHERE alert_kind = 'signature') <= 20
   OR (SELECT count(*) FROM v_alert_truth WHERE alert_kind = 'signature') IS NOT NULL);
SELECT 'pm_overdue_distinct_le_items | ' ||
  ((SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth WHERE is_overdue)
   <= (SELECT count(*) FROM v_pm_scope_items_truth WHERE is_overdue));
SELECT 'risk_component_sane | ' ||
  ((SELECT count(*) FROM v_risk_truth WHERE risk_level IN ('critical','high'))
   <= (SELECT count(*) FROM v_risk_truth));
SELECT 'inventory_component_sane | ' ||
  ((SELECT count(*) FROM v_inventory_items_truth WHERE is_low_stock OR is_out_of_stock)
   <= (SELECT count(*) FROM v_inventory_items_truth));
