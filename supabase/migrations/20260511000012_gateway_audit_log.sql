-- gateway_audit_log -- one row per platform-gateway invocation.
--
-- Closes Phase 2.3 of the roadmap. Compliance (ISO 27001 / SOC 2) wants
-- "who called what, when, from where" for every API touch. The platform-
-- gateway writes one row per request after rate-limit + auth pass, so
-- audit log captures the request even when the downstream fn fails.
--
-- Retention is 365 days (compliance-suggested). Cleanup cron registered
-- in the same migration.

CREATE TABLE IF NOT EXISTS public.gateway_audit_log (
  id              bigserial PRIMARY KEY,
  hive_id         uuid REFERENCES public.hives(id) ON DELETE SET NULL,
  worker_name     text,
  auth_uid        uuid,
  route           text NOT NULL,                                     -- which downstream fn was invoked
  request_id      text,                                              -- client-supplied request UUID for tracing
  method          text NOT NULL DEFAULT 'POST',
  status_code     integer,                                           -- HTTP status returned to caller
  latency_ms      integer,
  ip_hash         text,                                              -- sha-256(client_ip) for compliance
  ua_fingerprint  text,                                              -- sha-256(user-agent)
  error_class     text,                                              -- only set on non-2xx
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gateway_audit_hive_created
  ON public.gateway_audit_log (hive_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_gateway_audit_route_created
  ON public.gateway_audit_log (route, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_gateway_audit_failures
  ON public.gateway_audit_log (route, status_code, created_at DESC)
  WHERE status_code >= 400;
CREATE INDEX IF NOT EXISTS idx_gateway_audit_created
  ON public.gateway_audit_log (created_at DESC);

GRANT SELECT, INSERT ON public.gateway_audit_log TO anon, authenticated;

ALTER TABLE public.gateway_audit_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS gateway_audit_read   ON public.gateway_audit_log;
DROP POLICY IF EXISTS gateway_audit_insert ON public.gateway_audit_log;

-- Read: hive members can read their own hive's audit trail.
CREATE POLICY gateway_audit_read ON public.gateway_audit_log
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND hive_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = gateway_audit_log.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Insert: gateway uses service role; block anon/auth direct inserts.
CREATE POLICY gateway_audit_insert ON public.gateway_audit_log
  FOR INSERT WITH CHECK (false);


-- 365-day retention cron at 04:30 UTC (after agent-memory-retention).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule('gateway-audit-retention');
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule(
      'gateway-audit-retention',
      '30 4 * * *',
      $cron$
      DELETE FROM public.gateway_audit_log
       WHERE created_at < now() - INTERVAL '365 days';
      $cron$
    );
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;
