-- ─── Phase C-data — auth_uid backfill for 4 straggler tables ────────────────
--
-- PRODUCTION_FIXES.md #37 (Auth Migration Phase C-data).
--
-- Background:
--   Phase A audit's straggler scan against the live PRODUCTION database
--   (2026-05-10, run via Supabase Dashboard SQL Editor) found 19 rows across
--   4 tables where `auth_uid IS NULL` but `worker_name` matches a
--   `worker_profiles.display_name`. All 19 belong to a single worker — almost
--   certainly an early-testing account from before the auth flow was wired
--   into every page.
--
--   Once Phase E flips the L3 permissive policies (PRODUCTION_FIXES #36),
--   these 19 rows would become invisible to their owner because the auth-
--   gated SELECT/UPDATE/DELETE policies require `auth.uid() = auth_uid`.
--   This migration prevents that lockout class.
--
-- Straggler counts per table (live as of 2026-05-10):
--   pm_completions          10 (1 worker)
--   logbook                  5 (1 worker)
--   inventory_transactions   3 (1 worker)
--   marketplace_sellers      1 (1 worker)
--   ──────────────────────────
--   total                   19 stragglers, all by the same single owner
--
-- Fix:
--   For each table, UPDATE auth_uid by joining to worker_profiles via the
--   table's own identity column. Pattern matches the prior auth_uid backfill
--   migrations (20260430000004 onwards). Each UPDATE is idempotent — re-runs
--   are safe because the WHERE clause filters to auth_uid IS NULL only, so
--   already-backfilled rows are skipped.
--
-- Verification (run the same straggler scan after applying):
--   The temp-table scan from PRODUCTION_FIXES #37 should report 0 across all
--   four tables, leaving Phase E unblocked.

BEGIN;

-- pm_completions: worker_name → worker_profiles.display_name
UPDATE public.pm_completions t
SET    auth_uid = wp.auth_uid
FROM   public.worker_profiles wp
WHERE  t.worker_name = wp.display_name
  AND  t.auth_uid IS NULL;

-- logbook: worker_name → worker_profiles.display_name
UPDATE public.logbook t
SET    auth_uid = wp.auth_uid
FROM   public.worker_profiles wp
WHERE  t.worker_name = wp.display_name
  AND  t.auth_uid IS NULL;

-- inventory_transactions: worker_name → worker_profiles.display_name
UPDATE public.inventory_transactions t
SET    auth_uid = wp.auth_uid
FROM   public.worker_profiles wp
WHERE  t.worker_name = wp.display_name
  AND  t.auth_uid IS NULL;

-- marketplace_sellers: worker_name → worker_profiles.display_name
UPDATE public.marketplace_sellers t
SET    auth_uid = wp.auth_uid
FROM   public.worker_profiles wp
WHERE  t.worker_name = wp.display_name
  AND  t.auth_uid IS NULL;

COMMIT;
