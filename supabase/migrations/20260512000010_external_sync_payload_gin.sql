-- JSONB GIN index on external_sync.sync_payload (closes PRODUCTION_FIXES #58).
--
-- The CMMS sync flow stores per-row payload metadata in
-- `external_sync.sync_payload jsonb`. The integrations page + cmms-sync
-- edge function query this column with `->>` projections to look up
-- "did we already sync this entity?" and to surface field-level
-- mismatches. Without a GIN index those queries do a full-table scan.
-- At 1k rows it's invisible; at 100k+ rows (a large hive's first import)
-- the integrations page hangs for seconds.
--
-- GIN is the right index for JSONB equality and `?`/`?&`/`?|` operators
-- (key-presence, containment). path_ops is narrower and faster for the
-- containment pattern we use most (`sync_payload @> '{"key": "value"}'`).
-- Default opclass jsonb_ops covers all JSONB operators; path_ops covers
-- only `@>` but is ~30% smaller. Going with default jsonb_ops here for
-- forward compatibility with future `?` lookups.
--
-- Skills consulted: data-engineer (JSONB index opclass trade-off),
-- performance (table-scan threshold at 100k rows), KPI_ENGINE.md
-- Phase 1.3 deferred-until-forced rule (this is the trigger).

BEGIN;

CREATE INDEX IF NOT EXISTS idx_external_sync_sync_payload_gin
  ON public.external_sync USING GIN (sync_payload);

COMMENT ON INDEX public.idx_external_sync_sync_payload_gin IS
  'GIN index on sync_payload jsonb. Closes PRODUCTION_FIXES #58. Required for the CMMS integrations page when external_sync grows past ~10k rows; supports `@>`, `?`, `?&`, `?|` operators.';

-- Audit row so we can see this landed on first apply.

DO $$
DECLARE
  cnt bigint;
BEGIN
  SELECT count(*) INTO cnt FROM public.external_sync;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
    INSERT INTO public.automation_log (job_name, status, detail)
    VALUES (
      'external_sync_payload_gin',
      'success',
      format('GIN index created on external_sync.sync_payload. Table row count at apply: %s.', cnt)
    );
  END IF;
END
$$;

COMMIT;
