-- Add hive_id to inventory_transactions
-- The application code already tries to save hive_id on every transaction
-- but the column didn't exist — Supabase was silently dropping it.
-- This migration makes hive_id actually persist so analytics can filter
-- transactions by hive instead of worker_name.

-- Step 1: Add the column (nullable — existing rows default to NULL)
ALTER TABLE inventory_transactions
  ADD COLUMN IF NOT EXISTS hive_id uuid REFERENCES hives(id) ON DELETE SET NULL;

-- Step 2: Index for analytics queries filtered by hive
CREATE INDEX IF NOT EXISTS idx_inv_txns_hive_type_date
  ON inventory_transactions (hive_id, type, created_at DESC)
  WHERE type = 'use';

-- Step 3: Backfill existing rows where possible
-- Match transactions to a hive via the item they reference
-- (inventory_items.hive_id → inventory_transactions.item_id)
UPDATE inventory_transactions t
SET hive_id = i.hive_id
FROM inventory_items i
WHERE t.item_id = i.id
  AND t.hive_id IS NULL
  AND i.hive_id IS NOT NULL;

-- Note: rows with no matching inventory_items record stay NULL —
-- these are solo-mode transactions with no hive association.
