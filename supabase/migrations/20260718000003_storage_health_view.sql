-- 20260718000003_storage_health_view.sql
--
-- Grafana G4.4 (other observability, 2026-07-18): make object-storage usage OBSERVABLE.
-- storage.objects has RLS (tenant-scoped), so grafana_reader can't read it directly and
-- a per-object read would expose paths anyway. This postgres-owned view (security_invoker
-- OFF -> runs as owner, sees all buckets) exposes only AGGREGATES per bucket: object count,
-- total bytes (from the object metadata), and newest upload. Storage is billed and creeps
-- silently; a per-bucket size + growth panel + a threshold alert catches it early.
-- Read-only; grafana_reader is GRANTed SELECT in infra/mcp/grafana/grafana_reader.sql.

CREATE OR REPLACE VIEW public.v_storage_health AS
  SELECT bucket_id,
         count(*)                                            AS objects,
         coalesce(sum((metadata->>'size')::bigint), 0)       AS bytes,
         max(created_at)                                     AS newest_at
  FROM storage.objects
  GROUP BY bucket_id;

-- self-heal prod/local drift (2026-07-18): grafana_reader is created by the side-file
-- infra/mcp/grafana/grafana_reader.sql, which prod has not run yet. Grant only when the role exists.
-- The view is created above regardless; only the Grafana monitoring role reads it, never the app.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_reader') THEN
    GRANT SELECT ON public.v_storage_health TO grafana_reader;
  END IF;
END $$;
