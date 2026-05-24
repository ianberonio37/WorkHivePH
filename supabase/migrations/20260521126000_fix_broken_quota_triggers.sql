-- Fix broken hive_quota_* triggers (RAG Flywheel substrate prerequisite)
-- =======================================================================
-- Migration 20260511000003_hive_quotas.sql created triggers
-- (check_hive_quota_logbook, check_hive_quota_inv_tx) that read columns
-- max_rows_logbook + max_rows_inv_tx + max_storage_mb from hive_quotas.
--
-- Migration 20260520000004_drop_phantom_columns_safe.sql later DROPPED
-- those columns as phantom (no live consumer). The trigger functions
-- were NOT updated, so every INSERT on logbook / inventory_transactions
-- now fails with "column max_rows_logbook does not exist".
--
-- This blocks the 5-year synthetic history seeder (tools/seed_5y_synthetic_history.py)
-- which is the substrate for the RAG Flywheel.
--
-- Fix: DROP the orphaned triggers + functions. The phantom-column drop
-- already established that the quota gates were unused; removing the
-- triggers makes that explicit and unblocks INSERTs. If quotas are
-- needed later, a new design referencing the canonical billing-tier
-- table should land it cleanly.
--
-- Safe on both local (where columns are gone) and production (where
-- the drop migration has not yet been pushed — the trigger drops are
-- idempotent via IF EXISTS).

BEGIN;

DROP TRIGGER IF EXISTS trg_hive_quota_logbook ON public.logbook;
DROP TRIGGER IF EXISTS trg_hive_quota_inv_tx  ON public.inventory_transactions;

DROP FUNCTION IF EXISTS public.check_hive_quota_logbook();
DROP FUNCTION IF EXISTS public.check_hive_quota_inv_tx();

COMMIT;
