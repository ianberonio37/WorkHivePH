-- low_stock_by_reorder (hive): the low-stock count equals inventory's OWN reorder-point predicate.
-- The hive board and inventory both surface "low stock", and the failure this guards against is two
-- surfaces quietly disagreeing about what low MEANS - one counting `qty <= min_qty`, the other also
-- counting the shelf that is flat empty. v_inventory_items_truth is the single definition:
--   is_low_stock = qty_on_hand <= 0 OR (min_qty > 0 AND qty_on_hand <= min_qty)
-- ★THE `qty <= 0` DISJUNCT IS LOAD-BEARING and is why this recipe exists. An item with no minimum set
-- (min_qty = 0) that has run to ZERO satisfies neither half of a naive `min_qty > 0 AND qty <= min_qty`
-- test, so it would be OUT of stock and OUT of the low-stock list at the same time - invisible exactly
-- when it matters most. Migration 20260828000001_low_stock_includes_no_stock fixed that, and the
-- fixture below re-creates the case so the fix cannot silently regress.
-- expect: view_matches_raw_predicate \| t
-- expect: low_stock_items \| [1-9][0-9]*
-- expect: not_everything_is_low \| t
-- expect: empty_shelf_with_no_minimum_counts_as_low \| t
-- expect: rows_restored_after_rollback \| t

-- the view's own definition, recomputed from the base table, must agree row for row
SELECT 'view_matches_raw_predicate | ' || (count(*) = 0) FROM (
  SELECT v.id FROM v_inventory_items_truth v JOIN inventory_items i ON i.id = v.id
   WHERE v.is_low_stock IS DISTINCT FROM (i.qty_on_hand <= 0 OR (i.min_qty > 0 AND i.qty_on_hand <= i.min_qty))
) q;

-- non-vacuity, both directions: some items are low, and some are NOT. A predicate that is
-- universally true or universally false would satisfy the equality above and mean nothing.
SELECT 'low_stock_items | ' || count(*) FILTER (WHERE is_low_stock) FROM v_inventory_items_truth;
SELECT 'not_everything_is_low | ' || (count(*) FILTER (WHERE NOT is_low_stock) > 0) FROM v_inventory_items_truth;

CREATE TEMP TABLE _base AS SELECT (SELECT count(*) FROM inventory_items) AS n0,
                                  (SELECT hive_id FROM inventory_items WHERE hive_id IS NOT NULL LIMIT 1) AS hive;
BEGIN;
-- the regressed case, built rather than hoped for: empty shelf, NO minimum configured
INSERT INTO inventory_items (id, hive_id, part_name, qty_on_hand, min_qty, worker_name)
SELECT 'WH-PROBE-lowstock', hive, 'WH-PROBE empty shelf', 0, 0, 'WH-PROBE' FROM _base;
SELECT 'empty_shelf_with_no_minimum_counts_as_low | ' ||
  (SELECT is_low_stock FROM v_inventory_items_truth WHERE id = 'WH-PROBE-lowstock');
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM inventory_items) = (SELECT n0 FROM _base));
DROP TABLE _base;
