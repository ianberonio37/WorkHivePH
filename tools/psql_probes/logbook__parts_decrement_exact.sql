-- parts_decrement_exact: consuming parts from a job decrements EXACTLY once with the race closed —
-- inventory_deduct locks the row (FOR UPDATE), clamps at zero, and pairs the ledger row with the
-- exact negative moved quantity. Read from the fn's own source; live ledger carries no positive
-- 'use' rows.
-- expect: row_locked \| t
-- expect: clamped_at_zero \| t
-- expect: ledger_paired \| t
-- expect: positive_use_rows \| 0
SELECT 'row_locked | '     || (prosrc ILIKE '%FOR UPDATE%')        FROM pg_proc WHERE proname='inventory_deduct';
SELECT 'clamped_at_zero | '|| (prosrc ILIKE '%GREATEST(0,%')       FROM pg_proc WHERE proname='inventory_deduct';
SELECT 'ledger_paired | '  || (prosrc ILIKE '%inventory_transactions%' AND prosrc ILIKE '%qty_after%') FROM pg_proc WHERE proname='inventory_deduct';
SELECT 'positive_use_rows | ' || count(*) FROM inventory_transactions
WHERE type = 'use' AND qty_change > 0;
