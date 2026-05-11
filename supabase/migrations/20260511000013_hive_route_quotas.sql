-- hive_route_quotas -- per-(hive, route) hourly call caps.
--
-- Closes Phase 2.2 of the roadmap. The existing hive_quotas table tracks
-- ROW-COUNT caps (max rows per table). This new table tracks CALL-RATE
-- caps per route, so a chatty AI route doesn't competing with cheap
-- read routes under one global cap.
--
-- The rate-limit helper looks up (hive_id, route) -> hourly_cap; if no
-- row exists, it falls back to DEFAULT_RATE_LIMIT_PER_HOUR=50. Adding a
-- row LOWERS or RAISES the cap from the default.

CREATE TABLE IF NOT EXISTS public.hive_route_quotas (
  hive_id        uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  route          text NOT NULL,                                       -- 'ai-gateway', 'asset-brain-query', 'voice-transcribe', etc.
  hourly_cap     integer NOT NULL CHECK (hourly_cap > 0),
  enforce        boolean NOT NULL DEFAULT true,                       -- false = log-only, true = block at cap
  notes          text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (hive_id, route)
);

CREATE INDEX IF NOT EXISTS idx_hive_route_quotas_route
  ON public.hive_route_quotas (route);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.hive_route_quotas TO anon, authenticated;

ALTER TABLE public.hive_route_quotas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hive_route_quotas_read  ON public.hive_route_quotas;
DROP POLICY IF EXISTS hive_route_quotas_write ON public.hive_route_quotas;

-- Read: hive members can see their own hive's per-route caps.
CREATE POLICY hive_route_quotas_read ON public.hive_route_quotas
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = hive_route_quotas.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Writes go through service role (admin / billing layer).
CREATE POLICY hive_route_quotas_write ON public.hive_route_quotas
  FOR ALL USING (false) WITH CHECK (false);


-- hive_route_calls -- rolling counter for per-route enforcement.
-- The rate-limit helper increments (hive_id, route, hour_bucket); the
-- counter zero-resets when hour_bucket rolls over. Composite PK keeps
-- it small (one row per (hive, route, hour) max).

CREATE TABLE IF NOT EXISTS public.hive_route_calls (
  hive_id      uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  route        text NOT NULL,
  hour_bucket  timestamptz NOT NULL,                                  -- date_trunc('hour', now())
  call_count   integer NOT NULL DEFAULT 0,
  updated_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (hive_id, route, hour_bucket)
);

-- Hot-path: rate-limit lookup keys.
CREATE INDEX IF NOT EXISTS idx_hive_route_calls_bucket
  ON public.hive_route_calls (hour_bucket DESC);

GRANT SELECT, INSERT, UPDATE ON public.hive_route_calls TO anon, authenticated;

ALTER TABLE public.hive_route_calls ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hive_route_calls_read  ON public.hive_route_calls;
DROP POLICY IF EXISTS hive_route_calls_write ON public.hive_route_calls;

CREATE POLICY hive_route_calls_read ON public.hive_route_calls
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = hive_route_calls.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Writes through service role.
CREATE POLICY hive_route_calls_write ON public.hive_route_calls
  FOR ALL USING (false) WITH CHECK (false);


-- Retention: drop rows older than 48 hours (only the current hour is
-- consulted; 24h tail is for dashboard "calls last 24h" queries).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule('hive-route-calls-retention');
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule(
      'hive-route-calls-retention',
      '45 4 * * *',
      $cron$
      DELETE FROM public.hive_route_calls
       WHERE hour_bucket < now() - INTERVAL '48 hours';
      $cron$
    );
  END IF;
EXCEPTION WHEN OTHERS THEN
  NULL;
END
$$;
