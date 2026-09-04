-- stock_conserved (inventory): a part's qty_on_hand equals the NEWEST inventory_transactions.qty_after.
-- This is the invariant that went wrong once and was invisible: trg_inventory_sync_balance MIRRORS
-- qty_after onto qty_on_hand, which makes the two copies AGREE without ever asking whether either is
-- RIGHT - so a producer that miscomputed a running total got it faithfully canonised as the balance,
-- and 4 restocked units went missing with nothing disagreeing with anything.
-- Three legs, because agreement alone is what fooled us before:
--   1. the ledger AGREES with the balance across every item that has a ledger (the state today);
--   2. TEETH - corrupting one balance makes the check FIRE, so a green here is a measurement and not
--      a query that cannot fail;
--   3. LIVE - a real inventory_deduct through the RPC leaves the invariant intact, so the property is
--      maintained by the write path rather than merely true of resting data.
-- Ordered so the teeth are proven independently of the live movement; everything rolls back.
-- expect: items_with_ledger \| [1-9][0-9]*
-- expect: disagreeing_now \| 0
-- expect: teeth_detector_fires \| t
-- expect: rpc_moved_the_shelf \| t
-- expect: invariant_holds_after_live_deduct \| t
-- expect: rows_restored_after_rollback \| t

CREATE TEMP VIEW _newest AS
SELECT DISTINCT ON (item_id) item_id, qty_after
FROM inventory_transactions ORDER BY item_id, created_at DESC, id DESC;

SELECT 'items_with_ledger | ' || count(*) FROM inventory_items i JOIN _newest n ON n.item_id = i.id;
SELECT 'disagreeing_now | ' || count(*) FROM inventory_items i JOIN _newest n ON n.item_id = i.id
 WHERE i.qty_on_hand IS DISTINCT FROM n.qty_after;

-- TEETH: break one balance by hand; the same query must now report exactly one disagreement.
BEGIN;
UPDATE inventory_items SET qty_on_hand = qty_on_hand + 777
 WHERE id = (SELECT i.id FROM inventory_items i JOIN _newest n ON n.item_id = i.id LIMIT 1);
SELECT 'teeth_detector_fires | ' || ((SELECT count(*) FROM inventory_items i JOIN _newest n ON n.item_id = i.id
                                      WHERE i.qty_on_hand IS DISTINCT FROM n.qty_after) = 1);
ROLLBACK;

-- LIVE: a real RPC movement, as the item's own hive member, must leave the invariant intact.
CREATE TEMP TABLE _f AS
SELECT i.id AS item_id, i.hive_id, i.qty_on_hand AS before_qty,
       (SELECT hm.auth_uid FROM hive_members hm
         WHERE hm.hive_id = i.hive_id AND hm.status='active' AND hm.auth_uid IS NOT NULL LIMIT 1) AS uid,
       (SELECT count(*) FROM inventory_transactions) AS n0
FROM inventory_items i
WHERE i.hive_id IS NOT NULL AND i.qty_on_hand >= 2
  AND EXISTS (SELECT 1 FROM hive_members hm WHERE hm.hive_id=i.hive_id AND hm.status='active' AND hm.auth_uid IS NOT NULL)
LIMIT 1;
GRANT SELECT ON _f TO authenticated;

BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT uid FROM _f)::text, 'role','authenticated')::text, true);
SELECT 'rpc_moved_the_shelf | ' ||
  (public.inventory_deduct((SELECT item_id FROM _f), 1) = (SELECT before_qty FROM _f) - 1);
RESET ROLE;
SELECT 'invariant_holds_after_live_deduct | ' ||
  ((SELECT count(*) FROM inventory_items i
     JOIN (SELECT DISTINCT ON (item_id) item_id, qty_after FROM inventory_transactions
            ORDER BY item_id, created_at DESC, id DESC) n2 ON n2.item_id = i.id
    WHERE i.qty_on_hand IS DISTINCT FROM n2.qty_after) = 0);
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM inventory_transactions) = (SELECT n0 FROM _f));
DROP TABLE _f;
