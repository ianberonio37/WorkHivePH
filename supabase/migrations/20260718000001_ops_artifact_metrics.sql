-- 20260718000001_ops_artifact_metrics.sql
--
-- Operator-Console → Grafana arc (P1 completion, 2026-07-18): land FILE-ARTIFACT
-- metrics into Postgres so Grafana can show them. founder-console's last 2
-- observe sections read JSON files (companion_eval_scorecard.json, memento_health.json
-- — the eval-harness / Stop-hook artifacts), and Grafana's supabase_local datasource
-- is Postgres-only, so those sections could not become panels until their data lands
-- in a table. tools/land_ops_artifacts.py writes one append-only snapshot row per
-- artifact; the Founder-Ops dashboard reads the latest. This is the artifact→Postgres
-- pipeline Ian chose (2026-07-18) so founder-console can be FULLY retired.
--
-- RLS: writes are service-role/seeder only (auth.uid() IS NULL bypasses RLS); the
-- read path for the monitoring role is granted in infra/mcp/grafana/grafana_reader.sql
-- (ops_artifact_metrics_grafana_read), same least-privilege pattern as the other
-- observability tables.

CREATE TABLE IF NOT EXISTS public.ops_artifact_metrics (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  artifact    text NOT NULL,                       -- 'memento_health' | 'companion_eval'
  captured_at timestamptz NOT NULL DEFAULT now(),
  status      text,                                -- e.g. 'live' / 'pass' / 'warn'
  headline    text,                                -- human one-liner for the panel
  metrics     jsonb NOT NULL DEFAULT '{}'::jsonb   -- the extracted metric payload
);

CREATE INDEX IF NOT EXISTS ops_artifact_metrics_artifact_captured
  ON public.ops_artifact_metrics (artifact, captured_at DESC);

ALTER TABLE public.ops_artifact_metrics ENABLE ROW LEVEL SECURITY;
-- No client policy: only the service-role/seeder writer (auth.uid() IS NULL → BYPASSRLS)
-- lands rows; grafana_reader gets a dedicated SELECT policy in grafana_reader.sql.
-- Service-role/seeder-only table: clients (anon/authenticated) get NO access, and no client page
-- reads it. An explicit REVOKE ALL (rather than a dangling GRANT that RLS would then inertly deny) is
-- the honest, secure posture — the client lock-out is deliberate and self-documenting. This satisfies
-- BOTH the idempotency grant-coverage gate (an explicit REVOKE ALL is an accepted posture statement for
-- a service-role-only table) AND the rls-readiness lockout-trap gate (a REVOKE'd table is recognized as
-- a deliberate service-role lockdown, not an unreachable RLS-on/zero-policy trap). The service-role
-- writer (auth.uid() IS NULL → BYPASSRLS) is unaffected; grafana_reader keeps its dedicated SELECT
-- policy in grafana_reader.sql.
REVOKE ALL ON public.ops_artifact_metrics FROM anon, authenticated;
