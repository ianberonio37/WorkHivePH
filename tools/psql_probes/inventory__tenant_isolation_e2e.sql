-- tenant_isolation_e2e (inventory): a foreign hive's parts are invisible END TO END - through the
-- table reads, through the realtime channel's table, AND through the write RPC.
-- The RPC leg is the one RLS cannot cover: inventory_deduct is SECURITY DEFINER, so policies do NOT
-- bind inside it and the ONLY thing standing between a member of hive A and hive B's shelf is the
-- function's own membership re-check. A probe that tested the table alone would call this page
-- isolated while the write path stood open.
-- Both legs of the RPC are exercised: the foreign call must be REFUSED with 42501, and an own-hive
-- call must be ACCEPTED - a function that refused everyone would pass a refusal-only test.
-- qty 0 is deliberate: the membership check runs before any mutation, so the guard is proven without
-- moving stock, and the whole thing is inside BEGIN/ROLLBACK regardless.
-- expect: control_sees_foreign \| t
-- expect: member_items_own_only \| t
-- expect: member_txns_own_only \| t
-- expect: items_in_realtime_publication \| t
-- expect: fixture_has_both_items \| t
-- expect: rpc_own_hive_accepted \| t
-- expect: caller is not an active member
-- expect: rows_restored_after_rollback \| t
CREATE TEMP TABLE _ti AS
SELECT hm.hive_id, hm.auth_uid,
       (SELECT count(*) FROM inventory_items        WHERE hive_id <> hm.hive_id) AS f_items,
       (SELECT count(*) FROM inventory_transactions WHERE hive_id <> hm.hive_id) AS f_txns,
       (SELECT i.id FROM inventory_items i WHERE i.hive_id  = hm.hive_id LIMIT 1) AS own_item,
       (SELECT i.id FROM inventory_items i WHERE i.hive_id <> hm.hive_id AND i.hive_id IS NOT NULL LIMIT 1) AS foreign_item,
       (SELECT count(*) FROM inventory_transactions) AS n0
FROM hive_members hm WHERE hm.status='active' AND hm.auth_uid IS NOT NULL
  AND EXISTS (SELECT 1 FROM inventory_items i WHERE i.hive_id = hm.hive_id) LIMIT 1;
GRANT SELECT ON _ti TO authenticated;
SELECT 'control_sees_foreign | ' || ((SELECT f_items FROM _ti) > 0 AND (SELECT f_txns FROM _ti) > 0);
SELECT 'fixture_has_both_items | ' || ((SELECT own_item FROM _ti) IS NOT NULL AND (SELECT foreign_item FROM _ti) IS NOT NULL);
SELECT 'items_in_realtime_publication | ' || EXISTS (
  SELECT 1 FROM pg_publication_tables WHERE pubname='supabase_realtime' AND tablename='inventory_items');

BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _ti)::text, 'role','authenticated')::text, true);
SELECT 'member_items_own_only | ' || ((SELECT count(*) FROM inventory_items        WHERE hive_id <> (SELECT hive_id FROM _ti)) = 0);
SELECT 'member_txns_own_only | '  || ((SELECT count(*) FROM inventory_transactions WHERE hive_id <> (SELECT hive_id FROM _ti)) = 0);
-- RPC, own hive: must be ACCEPTED (the non-vacuity half of the write leg)
SELECT 'rpc_own_hive_accepted | ' || (public.inventory_deduct((SELECT own_item FROM _ti), 0) IS NOT NULL);
ROLLBACK;

BEGIN;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _ti)::text, 'role','authenticated')::text, true);
-- RPC, foreign hive: the DEFINER function's own membership re-check must REFUSE it
SELECT public.inventory_deduct((SELECT foreign_item FROM _ti), 0);
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM inventory_transactions) = (SELECT n0 FROM _ti));
DROP TABLE _ti;
