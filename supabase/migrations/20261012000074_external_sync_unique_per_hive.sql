-- ★ONE HIVE'S CMMS ORDER COULD OVERWRITE ANOTHER'S (2026-10-12, UFAI edge walk W4409).
--
-- external_sync was unique on (system_type, external_id, entity_type) - no hive_id. A CMMS order number is unique only
-- inside ONE company's CMMS (SAP order numbers start in the same ranges everywhere), and every writer upserts ON that
-- key: so when a second hive synced an order with the same number, cmms-sync and cmms-webhook-receiver (service role)
-- updated the FIRST hive's row - moving it, with its F1005 link to a logbook entry, into the other tenant - and
-- integrations.html's import (the person's session) was refused by RLS on the other hive's row, failing that batch.
-- Proven in a rolled-back transaction: the order row ended up belonging to the second hive, one row for both.
-- The key now includes the hive. Every onConflict (cmms-sync, cmms-webhook-receiver, integrations.html, the seeder's
-- cmms_importer) names hive_id in the same change. hive_id has no NULLs (0 of 14 locally) and every writer supplies it,
-- so it becomes NOT NULL: a NULL would make the new key unenforceable.

begin;

alter table public.external_sync alter column hive_id set not null;

alter table public.external_sync
  drop constraint if exists external_sync_system_type_external_id_entity_type_key;
alter table public.external_sync
  drop constraint if exists external_sync_hive_system_external_entity_key;
alter table public.external_sync
  add constraint external_sync_hive_system_external_entity_key
  unique (hive_id, system_type, external_id, entity_type);

commit;

notify pgrst, 'reload schema';
