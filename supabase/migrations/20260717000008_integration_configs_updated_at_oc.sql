-- integrations P6 concurrent-edit fix (bug-hunt roadmap, 2026-07-17, found via live probe).
-- integration_configs is a SHARED per-hive connector config (any supervisor edits it) updated by
-- `.update(row).eq('id', ...)` with NO optimistic-concurrency guard and NO updated_at column — two
-- supervisors editing the same connector concurrently silently overwrite each other (lost-update).
-- Add updated_at + the canonical touch trigger; the client save then guards on it (editConfig snapshots
-- updated_at; saveSyncConfig adds .eq('updated_at', snapshot) + a conflict message). Same pattern as
-- pm_assets (mig 000005).
ALTER TABLE public.integration_configs ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DROP TRIGGER IF EXISTS tg_integration_configs_touch_updated ON public.integration_configs;
CREATE TRIGGER tg_integration_configs_touch_updated
  BEFORE UPDATE ON public.integration_configs
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
