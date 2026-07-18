-- Read-only role for Grafana to read GlitchTip's Postgres (G4.3 app-error observability, 2026-07-18).
-- Run against the GlitchTip DB only:
--   docker exec -i workhive_glitchtip_postgres psql -U glitchtip -d glitchtip -f - < this
-- GlitchTip (Django) has NO RLS, so a plain SELECT grant is sufficient (unlike the Supabase
-- grafana_reader which needs per-table policies). Password is the .env.mcp GRAFANA_PG_READER_PASSWORD
-- (same secret the Grafana datasource sends); set it out-of-band after first create. The re-run
-- branch deliberately does NOT reset the password (same clobber lesson as grafana_reader.sql).

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_reader') THEN
    CREATE ROLE grafana_reader WITH LOGIN PASSWORD 'CHANGE_ME_grafana_reader';
  ELSE
    ALTER ROLE grafana_reader WITH LOGIN;  -- ensure LOGIN, never reset the password on re-run
  END IF;
END
$$;

GRANT CONNECT ON DATABASE glitchtip TO grafana_reader;
GRANT USAGE ON SCHEMA public TO grafana_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO grafana_reader;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM grafana_reader;
