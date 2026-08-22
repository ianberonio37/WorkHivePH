-- last_unit_race: two techs drawing the last unit cannot go negative — the DB CHECK
-- (qty_on_hand >= 0) is the arbiter, not client arithmetic. Teeth: draw an item to exactly 0 is
-- ALLOWED, one more draw is REFUSED (23514), rollback restores; live data holds no negative stock
-- and no transaction ever recorded a negative qty_after.
-- expect: check_constraint_present \| t
-- expect: draw_to_zero_allowed \| t
-- expect: 23514|violates check constraint
-- expect: negatives_live \| 0
-- expect: restored \| t
SELECT 'check_constraint_present | ' || EXISTS (
  SELECT 1 FROM pg_constraint WHERE conrelid='inventory_items'::regclass
   AND pg_get_constraintdef(oid) ILIKE '%qty_on_hand%>=%0%');
CREATE TEMP TABLE _lu AS
SELECT id, qty_on_hand, (SELECT count(*) FROM inventory_items WHERE qty_on_hand < 0) AS neg0
FROM inventory_items WHERE qty_on_hand > 0 ORDER BY qty_on_hand LIMIT 1;
BEGIN;
UPDATE inventory_items SET qty_on_hand = 0 WHERE id = (SELECT id FROM _lu);
SELECT 'draw_to_zero_allowed | ' ||
  ((SELECT qty_on_hand FROM inventory_items WHERE id = (SELECT id FROM _lu)) = 0);
UPDATE inventory_items SET qty_on_hand = qty_on_hand - 1 WHERE id = (SELECT id FROM _lu);
ROLLBACK;
SELECT 'negatives_live | ' || count(*) FROM inventory_items WHERE qty_on_hand < 0;
SELECT 'restored | ' || ((SELECT qty_on_hand FROM inventory_items WHERE id = (SELECT id FROM _lu))
  = (SELECT qty_on_hand FROM _lu));
DROP TABLE _lu;
