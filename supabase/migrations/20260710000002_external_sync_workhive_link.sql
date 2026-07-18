-- CMMS Integrations PDDA F1005: link each synced external work order to the WorkHive
-- logbook row it created.
--
-- BEFORE: cmms-push-completion resolved the CMMS work order to close by
--   external_sync WHERE machine = X ORDER BY last_synced_at DESC LIMIT 1
-- so a machine with several OPEN work orders always pushed "Closed" to whichever WO
-- synced most recently — potentially the WRONG AUFNR/WONUM (corrupting the customer's
-- SAP/Maximo). The `logbook_id` the caller passed was never used to disambiguate.
--
-- AFTER: external_sync.workhive_id stores the logbook row id that a sync/webhook created
-- for this work order, so push-completion can resolve the EXACT work order by
-- workhive_id = logbook_id (falling back to machine+newest only for legacy rows with no
-- link). Nullable + partial index; back-compatible with existing rows.

alter table external_sync add column if not exists workhive_id uuid;

create index if not exists external_sync_workhive_id_idx
  on external_sync (workhive_id) where workhive_id is not null;
