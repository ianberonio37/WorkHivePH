-- pm_rail_flags_canonical (P-C tile == DB canonical, 2026-09-05): dayplanner's PM rail states the
-- exact count of v_pm_scope_items_truth rows where is_overdue OR is_due_soon (dayplanner.html ~964,
-- count:'exact' — the rail was once WRONG when it stated data.length). The canonical the tile paints
-- is the view's own flags, so they must agree with next_due_date: overdue = due before today,
-- due-soon = due within the next 14 days (the view's window); and no row may be both.
-- expect: overdue_flag_agrees \| t
-- expect: due_soon_flag_agrees \| t
-- expect: never_both \| t
-- expect: rail_count_is_flag_count \| t
SELECT 'overdue_flag_agrees | ' || (
  (SELECT count(*) FROM v_pm_scope_items_truth
    WHERE next_due_date IS NOT NULL AND is_overdue <> (next_due_date::date < current_date)) = 0);
-- the view's rule (pg_get_viewdef): for non-meter kinds, due-soon = next_due_date in [today, today+14d];
-- meter kinds use the km branch (current_km within 500 of next_due_km) and are left to that branch.
SELECT 'due_soon_flag_agrees | ' || (
  (SELECT count(*) FROM v_pm_scope_items_truth
    WHERE interval_kind <> 'meter' AND next_due_date IS NOT NULL
      AND is_due_soon <> (next_due_date::date >= current_date AND next_due_date::date <= current_date + 14)) = 0);
SELECT 'never_both | ' || ((SELECT count(*) FROM v_pm_scope_items_truth WHERE is_overdue AND is_due_soon) = 0);
SELECT 'rail_count_is_flag_count | ' || (
  (SELECT count(*) FROM v_pm_scope_items_truth WHERE is_overdue OR is_due_soon)
  = (SELECT count(*) FROM v_pm_scope_items_truth WHERE is_overdue) + (SELECT count(*) FROM v_pm_scope_items_truth WHERE is_due_soon));
