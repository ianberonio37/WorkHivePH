-- Create a read-only Postgres role for Grafana.
-- Run against LOCAL Supabase only:
--   psql "postgres://postgres:postgres@127.0.0.1:54322/postgres" -f infra/mcp/grafana/grafana_reader.sql
--
-- The password here must match GRAFANA_PG_READER_PASSWORD in infra/mcp/.env.mcp.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_reader') THEN
    CREATE ROLE grafana_reader WITH LOGIN PASSWORD 'CHANGE_ME_grafana_reader';
  ELSE
    ALTER ROLE grafana_reader WITH LOGIN PASSWORD 'CHANGE_ME_grafana_reader';
  END IF;
END
$$;

GRANT CONNECT ON DATABASE postgres TO grafana_reader;
GRANT USAGE ON SCHEMA public TO grafana_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_reader;

-- Explicitly DENY everything else.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM grafana_reader;
