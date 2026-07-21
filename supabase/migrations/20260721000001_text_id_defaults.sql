-- 20260721000001_text_id_defaults.sql
--
-- REAL BUG (found by validate_cmms_import_rollback, 2026-07-21): inventory_items.id is
-- text NOT NULL with NO default, and the CMMS inventory import (integrations.html) never
-- supplies an id -> every imported part row 23502-failed at RUNTIME. Until the import's
-- batches were error-checked (same arc), supabase-js swallowed the failure and the import
-- REPORTED SUCCESS. This is the logbook.id class from Arc K ("a NEWER path omitted the id
-- the older paths minted") biting a THIRD time.
--
-- Durable class fix per the data-engineer lesson: give the DB the id truth, so a future
-- insert path that forgets the client-side mint still works. id is an OPAQUE text PK with
-- already-mixed formats (seeder semantic codes 'AS-COF-12-AS', client Date.now() strings,
-- uuids) -- a uuid-format text default is consistent and only applies when id is absent.
--
-- Deliberately EXCLUDED (disposition, not oversight):
--   * achievement_definitions.id  -- semantic catalog slugs (migration-INSERT-only); a random
--     default would mint meaningless keys and mask a missing slug.
--   * schedule_items.id           -- dayplanner mints STABLE ids as its idempotency/dedup key;
--     a default would mask a broken stable-id path and turn re-syncs into duplicates.
--   * ops_db_size_history.id / parts_records.id -- bigint PKs; the right fix is an identity
--     sequence (a separate change), and their single writers always supply ids today.

alter table public.inventory_items       alter column id set default gen_random_uuid()::text;
alter table public.logbook               alter column id set default gen_random_uuid()::text;
alter table public.inventory_transactions alter column id set default gen_random_uuid()::text;
