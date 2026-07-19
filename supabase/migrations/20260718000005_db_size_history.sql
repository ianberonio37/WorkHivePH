-- 20260718000004_db_size_history.sql
--
-- Grafana G4.4b (other observability, 2026-07-18): DB + storage size TREND over time.
-- The DB-health board shows point-in-time size; the trend (is it creeping? how fast?)
-- needs history. This tiny append-only table gets one row/day from a pg_cron job
-- (snapshot_db_size), so the Grafana time-series fills in as days pass. The snapshot
-- job is pure SQL (no net.http_post) so it won't fail like the outbound crons — and it
-- shows up on the cron-health board itself (nice self-monitoring loop).

CREATE TABLE IF NOT EXISTS public.ops_db_size_history (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  captured_at  timestamptz NOT NULL DEFAULT now(),
  db_bytes     bigint      NOT NULL,
  storage_bytes bigint     NOT NULL DEFAULT 0,
  table_count  int         NOT NULL DEFAULT 0
);

-- Observability infra, not tenant data: RLS on, no app-role access; only the read-only
-- Grafana monitoring role reads it (policy added in grafana_reader.sql).
ALTER TABLE public.ops_db_size_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.ops_db_size_history FROM anon, authenticated;

CREATE OR REPLACE FUNCTION public.snapshot_db_size() RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_catalog AS $$
  INSERT INTO public.ops_db_size_history (captured_at, db_bytes, storage_bytes, table_count)
  SELECT now(),
         pg_database_size(current_database()),
         COALESCE((SELECT sum(bytes) FROM public.v_storage_health), 0),
         (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public');
$$;

-- Daily snapshot at 00:10. Idempotent: only schedule if not already present.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron')
     AND NOT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'ops-db-size-snapshot-daily') THEN
    PERFORM cron.schedule('ops-db-size-snapshot-daily', '10 0 * * *',
                          'select public.snapshot_db_size()');
  END IF;
END $$;

-- Seed one row now so the panel isn't empty (the series grows daily thereafter).
SELECT public.snapshot_db_size();

-- Guarded grant (grafana_reader is created by the side-file infra/mcp/grafana/grafana_reader.sql).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_reader') THEN
    GRANT SELECT ON public.ops_db_size_history TO grafana_reader;
  END IF;
END $$;

-- Register in canonical_sources (fuel registry) so the Canonical Anchor gate sees this new table.
INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, description) VALUES
  ('ops_db_size_history', 'table', 'ops_db_size_history', 'devops', 'on_snapshot',
   'DB + storage size trend history (Grafana G4.4b): one append-only row/day from the snapshot_db_size() pg_cron job. Observability infra, RLS on, anon/authenticated REVOKE''d; grafana_reader reads it for the DB-health trend board.'),
  ('v_storage_health', 'view', 'v_storage_health', 'devops', 'realtime',
   'Grafana storage-health engine view (migration 20260718000003): per-bucket storage byte totals for the DB-health observability board; read by grafana_reader. Registered here alongside the Grafana observability fuel table.')
ON CONFLICT (domain) DO NOTHING;
