-- consumption_names_part: BOTH consumption paths (inventory's Use modal and logbook's parts_used)
-- go through the ONE shared RPC inventory_deduct — the deduction always names its part, and there
-- is no second writer that could skip the ledger. The fn is present, writes the transaction with
-- the item id, and no OTHER function updates qty_on_hand.
-- expect: rpc_present \| t
-- expect: rpc_writes_ledger \| t
-- expect: other_qty_writers \| 0
SELECT 'rpc_present | ' || EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'inventory_deduct');
SELECT 'rpc_writes_ledger | ' ||
  (prosrc ILIKE '%inventory_transactions%' AND prosrc ILIKE '%item_id%')
FROM pg_proc WHERE proname = 'inventory_deduct';
-- exclusions WITH their mechanism (a bare name-list silently converts violations into passes):
-- inventory_deduct / inventory_restock are the two consumption/restock paths under test;
-- inventory_sync_balance_from_ledger writes qty_on_hand FROM the ledger (the DI §10.5 seesaw
-- reconciler) — it cannot skip the ledger because the ledger is its input.
SELECT 'other_qty_writers | ' || count(*) FROM pg_proc
WHERE prosrc ILIKE '%UPDATE%inventory_items%qty_on_hand%'
  AND proname NOT IN ('inventory_deduct', 'inventory_restock',
                      'inventory_sync_balance_from_ledger');
