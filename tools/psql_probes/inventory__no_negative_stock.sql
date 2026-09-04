-- no_negative_stock: a part cannot go below zero silently. The mechanism is NOT a CHECK constraint -
-- inventory_items carries none for qty_on_hand - it is the RPC: `inventory_deduct` computes
-- v_qty := GREATEST(0, v_qty - p_qty) and returns v_moved = what ACTUALLY left the shelf, "never more
-- than was there". So the guarantee lives in one function, and the honest way to test it is to CALL it
-- and watch, not to grep its body for GREATEST (a comment or a renamed helper would read the same).
-- PROVEN AS A REAL MEMBER, not as the table owner: inventory_deduct is SECURITY DEFINER and re-checks
-- hive membership itself, so postgres would bypass the very path under test. The probe assumes the
-- caller's identity from a LIVE hive_members row.
-- Teeth: ask for far more than the shelf holds. The balance must land at 0 - never negative - and the
-- RPC must report moving only what was there. A clamp that cannot be observed clamping is a comment.
-- expect: negative_rows_before \| 0
-- expect: items_checked \| [1-9][0-9]*
-- expect: teeth_fixture_found \| t
-- expect: qty_after_overdraw \| 0
-- expect: rpc_returns_clamped_zero \| t
-- expect: ledger_recorded_what_left \| t
-- expect: rows_restored_after_rollback \| t

SELECT 'items_checked | ' || count(*)::text
     || E'\nnegative_rows_before | ' || count(*) FILTER (WHERE qty_on_hand < 0)::text
FROM inventory_items;

-- a live item WITH stock, plus an active member of its hive to act as
CREATE TEMP TABLE _fix AS
SELECT i.id AS item_id, i.qty_on_hand AS before_qty, hm.auth_uid,
       (SELECT count(*) FROM inventory_transactions) AS n0
FROM inventory_items i
JOIN hive_members hm ON hm.hive_id = i.hive_id AND hm.status = 'active' AND hm.auth_uid IS NOT NULL
WHERE i.qty_on_hand > 0
LIMIT 1;
SELECT 'teeth_fixture_found | ' || EXISTS (SELECT 1 FROM _fix);

BEGIN;
DO $probe$
DECLARE v_moved numeric; v_before numeric; v_item text; v_uid uuid;
BEGIN
  SELECT item_id, before_qty, auth_uid INTO v_item, v_before, v_uid FROM _fix;
  PERFORM set_config('request.jwt.claims',
    json_build_object('sub', v_uid::text, 'role', 'authenticated')::text, true);
  -- ask for far more than exists
  SELECT public.inventory_deduct(v_item, (v_before + 9999)::int, 'WH-PROBE overdraw') INTO v_moved;
  RAISE NOTICE 'RESULT qty_after_overdraw | %', (SELECT qty_on_hand FROM inventory_items WHERE id = v_item);
  -- inventory_deduct RETURNS the NEW quantity, not the moved amount - so the clamp shows up as a
  -- returned 0, and what actually LEFT is (before - returned). The ledger must record THAT, never the
  -- larger amount that was asked for: a movement the shelf could not make must not appear as one it did.
  RAISE NOTICE 'RESULT rpc_returns_clamped_zero | %', (v_moved = 0);
  RAISE NOTICE 'RESULT ledger_recorded_what_left | %', (
    SELECT qty_change = -(v_before) FROM inventory_transactions
     WHERE item_id = v_item ORDER BY created_at DESC, id DESC LIMIT 1);
END $probe$;
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM inventory_transactions) = (SELECT n0 FROM _fix));
