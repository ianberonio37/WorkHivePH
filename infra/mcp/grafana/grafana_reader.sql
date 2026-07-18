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

-- RLS read path for the observability signal (Arc T/T4+T5 DEFECT FIX, 2026-07-17).
-- A GRANT SELECT is NOT enough when the table has RLS enabled: wh_traces' only
-- policy (wh_traces_hive_read) is scoped to `authenticated` with a JWT hive_id
-- match, so grafana_reader (not authenticated, no BYPASSRLS, no matching policy)
-- saw ZERO rows under default-deny RLS. That silently blinded BOTH the SLO
-- dashboard panels AND the wh_slo_edge_errors alert (its rawSql reads wh_traces
-- directly; v_wh_traces_slo is security_invoker=on so it inherits the same
-- blindness) -> the alert could NEVER fire on real edge errors. Found by the live
-- fault-injection walk; the static provisioning gate only checked the wiring
-- parses, not that the datasource role can READ through RLS.
--
-- Fix: a dedicated SELECT policy so the trusted, read-only, password-gated
-- monitoring role can read the platform telemetry it exists to observe. Platform
-- golden-signals are cross-hive by nature. This does NOT weaken client-facing
-- hardening: anon/authenticated are untouched; only grafana_reader (an internal
-- infra role used solely by the local Grafana datasource) gains the read. Scoped
-- to wh_traces (the SLO source) — least-privilege, not a blanket BYPASSRLS.
DROP POLICY IF EXISTS wh_traces_grafana_slo_read ON public.wh_traces;
CREATE POLICY wh_traces_grafana_slo_read
  ON public.wh_traces
  FOR SELECT
  TO grafana_reader
  USING (true);

-- OPERATOR-CONSOLE → GRAFANA arc (P1, 2026-07-18): the founder-console observe
-- sections move to Grafana panels, so grafana_reader needs the SAME least-privilege
-- read path on every operator-observability table (each is RLS-blind to it today —
-- measured: analytics_events 7081→0, ai_cost_log 451→0, hive_readiness 7→0,
-- marketplace_sellers 14→0, marketplace_listings 27→24, and hive_audit_log /
-- platform_feedback ERROR because their public policies call functions the reader
-- can't execute). Same rule as wh_traces: a GRANT SELECT is a no-op under RLS; the
-- monitoring role needs a policy. Cross-hive is correct — these are PLATFORM metrics
-- for the founder, not tenant data. Still least-privilege (per-table, SELECT-only,
-- NOT a blanket BYPASSRLS that would expose api_keys/login_attempts/sessions). For
-- the security_invoker views (v_hive_readiness_truth → hive_readiness,
-- v_marketplace_orders_truth → marketplace_orders/listings) the policy is on the
-- BASE tables, since the view runs as the invoking grafana_reader.
DO $grafana_p1$
DECLARE t text;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_reader') THEN
    FOREACH t IN ARRAY ARRAY[
      'analytics_events', 'ai_cost_log', 'hive_readiness', 'marketplace_orders',
      'marketplace_listings', 'marketplace_sellers', 'marketplace_disputes',
      'hive_audit_log', 'platform_feedback', 'ops_artifact_metrics',
      'ai_reply_feedback', 'agentic_rag_traces',  -- P3 AI-observability pages
      'hives'                                      -- G2 Founder-Home $hive template variable
    ] LOOP
      IF EXISTS (SELECT 1 FROM information_schema.tables
                 WHERE table_schema = 'public' AND table_name = t) THEN
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_grafana_read', t);
        EXECUTE format(
          'CREATE POLICY %I ON public.%I FOR SELECT TO grafana_reader USING (true)',
          t || '_grafana_read', t);
      END IF;
    END LOOP;
    -- hive_audit_log_select_supervisor + platform_feedback admin policies are
    -- roles={public} (so they apply to grafana_reader) and call these functions;
    -- without EXECUTE the reader's SELECT ERRORs during RLS evaluation. They return
    -- false/empty for the no-auth reader, so the *_grafana_read policy is what grants
    -- the row read — this just lets policy evaluation complete without a hard error.
    GRANT EXECUTE ON FUNCTION public.is_platform_admin() TO grafana_reader;
    GRANT EXECUTE ON FUNCTION public.user_supervisor_hive_ids() TO grafana_reader;
  END IF;
END
$grafana_p1$;

-- G4 CRON-HEALTH (other observability, 2026-07-18): make the pg_cron run history
-- observable. pg_cron restricts cron.job / cron.job_run_details to the job OWNER, so
-- a GRANT USAGE ON SCHEMA cron + GRANT SELECT still returns 0 rows for grafana_reader
-- (it doesn't own the jobs). The durable fix is the postgres-owned view
-- public.v_cron_health (migration 20260718000002) which runs as its owner and exposes
-- the run history read-only. grafana_reader only needs SELECT on that view (NOT cron
-- schema access). This surfaced 27+ SILENT failed cron runs in the last 7 days.
GRANT SELECT ON public.v_cron_health TO grafana_reader;
