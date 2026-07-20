-- Fix: the integrations CMMS inventory import (integrations.html ~L1358) upserts inventory_items with
-- `onConflict: 'part_number,hive_id'`, but NO unique index on (part_number, hive_id) existed — only the
-- pkey (id) + non-unique indexes. So Postgres rejected the upsert with "there is no unique or exclusion
-- constraint matching the ON CONFLICT specification" → a supervisor's CMMS inventory import CRASHED
-- (the whole inventory batch failed). Confirmed live 2026-07-19 (per-page bughunt P3/P4).
--
-- This FULL unique index (not partial — a partial index would need a matching WHERE on the ON CONFLICT,
-- which supabase-js's bare `onConflict:'part_number,hive_id'` does not emit) does three things:
--   1. Makes the import's upsert work (ON CONFLICT (part_number, hive_id) now has a matching index).
--   2. Enforces the "one part_number per hive" business rule at the DB.
--   3. Closes the submitPart double-submit RACE — the client-only "A part with this Part Number already
--      exists" check (inventory.html) read cached state, so a fast double-click could pass it twice and
--      mint two rows; the DB now rejects the duplicate regardless of client timing.
-- Verified 0 existing (part_number, hive_id) duplicates before creation, so it builds cleanly.
-- part_number is NOT NULL; hive_id nullable → NULL hive_ids are distinct (multiple allowed), which is fine.

CREATE UNIQUE INDEX IF NOT EXISTS inventory_items_partnumber_hive_uidx
  ON public.inventory_items (part_number, hive_id);
