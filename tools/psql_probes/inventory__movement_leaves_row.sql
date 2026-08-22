-- movement_leaves_row: every stock movement leaves a ledger row that RECONCILES — for every item
-- with transactions, the newest qty_after equals the item's qty_on_hand, and every transaction
-- names its worker and type. Population printed (non-vacuity).
-- expect: items_with_tx \| [1-9][0-9]*
-- expect: ledger_mismatches \| 0
-- expect: anonymous_movements \| 0
CREATE TEMP TABLE _mv AS
SELECT i.id, i.qty_on_hand,
       (SELECT t.qty_after FROM inventory_transactions t
         WHERE t.item_id = i.id ORDER BY t.created_at DESC, t.id DESC LIMIT 1) AS last_after
FROM inventory_items i
WHERE EXISTS (SELECT 1 FROM inventory_transactions t WHERE t.item_id = i.id);
SELECT 'items_with_tx | ' || count(*) FROM _mv;
SELECT 'ledger_mismatches | ' || count(*) FROM _mv WHERE last_after IS DISTINCT FROM qty_on_hand;
SELECT 'anonymous_movements | ' || count(*) FROM inventory_transactions
WHERE worker_name IS NULL OR btrim(worker_name) = '' OR type IS NULL OR btrim(type) = '';
DROP TABLE _mv;
