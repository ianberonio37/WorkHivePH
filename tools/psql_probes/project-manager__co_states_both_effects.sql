-- co_states_both_effects: every change order states BOTH of its effects — cost impact and schedule
-- impact are present on every row (a CO that hides one half is a decision made on half the price).
-- expect: change_orders \| [1-9][0-9]*
-- expect: missing_effects \| 0
SELECT 'change_orders | ' || count(*) FROM project_change_orders;
SELECT 'missing_effects | ' || count(*) FROM project_change_orders
WHERE cost_impact_php IS NULL OR schedule_impact_days IS NULL;
