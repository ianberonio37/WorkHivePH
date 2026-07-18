-- P6 concurrent-edit fix (bug-hunt roadmap, 2026-07-17, found via live DB probe).
-- pm_assets had NO `updated_at` column, yet pm-scheduler.html's asset-edit path reads/writes it
-- for optimistic concurrency:
--   _pmAssetUpdatedAt = currentAsset.updated_at || null;   // always null (no column)
--   .update({ ...updates, updated_at: now })               // phantom-column write
--   if (_pmAssetUpdatedAt) q = q.eq('updated_at', snap);    // SKIPPED (null) -> OC is a DEAD no-op
-- Net: two supervisors editing the same PM asset silently overwrite each other (lost-update),
-- and the client OC "guard" that looked present in static analysis never fired. The client code
-- is already correct — it only needed the column to exist. Reuse the canonical touch_updated_at()
-- trigger (same pattern as logbook / resume_documents / asset_nodes) so the DB is authoritative.
ALTER TABLE public.pm_assets ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DROP TRIGGER IF EXISTS tg_pm_assets_touch_updated ON public.pm_assets;
CREATE TRIGGER tg_pm_assets_touch_updated
  BEFORE UPDATE ON public.pm_assets
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
