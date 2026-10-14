-- consumption_names_part: BOTH consumption paths (inventory's Use modal and logbook's parts_used)
-- go through the ONE shared RPC inventory_deduct — the deduction always names its part, and there
-- is no second writer that could skip the ledger. The fn is present, writes the transaction with
-- the item id, and no OTHER function updates qty_on_hand.
-- expect: rpc_present \| t
-- expect: rpc_writes_ledger \| t
-- expect: other_qty_writers \| 0
-- expect: adjust_writes_ledger_not_balance \| t
SELECT 'rpc_present | ' || EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'inventory_deduct');
SELECT 'rpc_writes_ledger | ' ||
  (prosrc ILIKE '%inventory_transactions%' AND prosrc ILIKE '%item_id%')
FROM pg_proc WHERE proname = 'inventory_deduct';
-- exclusions WITH their mechanism (a bare name-list silently converts violations into passes):
-- inventory_deduct / inventory_restock are the two consumption/restock paths under test;
-- inventory_sync_balance_from_ledger writes qty_on_hand FROM the ledger (the DI §10.5 seesaw
-- reconciler) — it cannot skip the ledger because the ledger is its input.
-- inventory_adjust (2026-10-08, the part form's count edit) INSERTs the 'adjustment' ledger row and lets
-- inventory_sync_balance_from_ledger move the balance; it locks the part FOR UPDATE and re-reads qty_on_hand to
-- confirm, but never UPDATEs it - which adjust_writes_ledger_not_balance below asserts from its source, so the
-- exclusion cannot quietly cover a future direct write.
SELECT 'adjust_writes_ledger_not_balance | ' ||
  (prosrc ILIKE '%INSERT INTO public.inventory_transactions%'
   AND prosrc !~* 'UPDATE\s+public\.inventory_items\s+SET')
FROM pg_proc WHERE proname = 'inventory_adjust';
-- an actual UPDATE ... inventory_items SET ... qty_on_hand statement, not the three words anywhere in a body: the
-- ILIKE form matched get_hive_board_dashboard (2026-10-14) - its source READS inventory_items.qty_on_hand and carries
-- "updated_at" - and reddened this recipe on a function that writes no stock at all
SELECT 'other_qty_writers | ' || count(*) FROM pg_proc
WHERE prosrc ~* 'UPDATE\s+(public\.)?inventory_items\s+SET[^;]*qty_on_hand'
  AND proname NOT IN ('inventory_deduct', 'inventory_restock',
                      'inventory_sync_balance_from_ledger', 'inventory_adjust');
