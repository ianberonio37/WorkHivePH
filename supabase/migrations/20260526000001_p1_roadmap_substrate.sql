-- P1 roadmap substrate (2026-05-26)
-- New tables + RPCs for:
--   1. ai_cache              — hash-keyed LLM response cache (deterministic prompts)
--   2. ai_user_rate_limits   — per-user budget inside the per-hive bucket
--   3. wh_traces             — optional trace-id index (for cross-fn correlation)
--   4. wh_health_status      — last-known health per surface (read-only by frontend)
--
-- All four are additive. None replace existing tables. RLS: service role
-- write only. Reads are scoped per table.

-- ── 1. ai_cache ─────────────────────────────────────────────────────────────
-- canonical-allow: infrastructure/cache table; not a user-facing data source. LLM response cache (hash-keyed) is internal-only and doesn't surface in any v_*_truth view.
CREATE TABLE IF NOT EXISTS public.ai_cache (
  key            TEXT        PRIMARY KEY,
  model          TEXT        NOT NULL,
  response_json  JSONB       NOT NULL,
  tokens_in      INTEGER,
  tokens_out     INTEGER,
  hit_count      INTEGER     NOT NULL DEFAULT 0,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at     TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ai_cache_expires_at_idx ON public.ai_cache (expires_at);
CREATE INDEX IF NOT EXISTS ai_cache_model_idx      ON public.ai_cache (model);

ALTER TABLE public.ai_cache ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_cache_service_all ON public.ai_cache;
CREATE POLICY ai_cache_service_all ON public.ai_cache
  FOR ALL TO service_role
  USING (true) WITH CHECK (true);

-- RPC to bump hit_count without an UPDATE roundtrip from the caller.
CREATE OR REPLACE FUNCTION public.ai_cache_bump(p_key TEXT)
RETURNS VOID
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  UPDATE public.ai_cache SET hit_count = hit_count + 1 WHERE key = p_key;
$$;

REVOKE ALL ON FUNCTION public.ai_cache_bump(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.ai_cache_bump(TEXT) TO service_role;

-- Sweeper RPC — called by pg_cron weekly to evict expired rows.
CREATE OR REPLACE FUNCTION public.ai_cache_sweep_expired()
RETURNS INTEGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE n INTEGER;
BEGIN
  DELETE FROM public.ai_cache WHERE expires_at < now();
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$$;

REVOKE ALL ON FUNCTION public.ai_cache_sweep_expired() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.ai_cache_sweep_expired() TO service_role;


-- ── 2. ai_user_rate_limits ──────────────────────────────────────────────────
-- canonical-allow: rate-limit counter table; not a data source. Per-user bucket inside the per-hive rate-limit gate.
CREATE TABLE IF NOT EXISTS public.ai_user_rate_limits (
  user_id        TEXT        PRIMARY KEY,
  hive_id        TEXT,
  call_count     INTEGER     NOT NULL DEFAULT 0,
  window_start   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_user_rl_hive_idx ON public.ai_user_rate_limits (hive_id);

ALTER TABLE public.ai_user_rate_limits ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_user_rl_service_all ON public.ai_user_rate_limits;
CREATE POLICY ai_user_rl_service_all ON public.ai_user_rate_limits
  FOR ALL TO service_role
  USING (true) WITH CHECK (true);


-- ── 3. wh_traces ────────────────────────────────────────────────────────────
-- canonical-allow: observability spine table; not a data source. Trace-id index for cross-fn request correlation, consumed only by agentic_rag_observability dashboard.
-- Optional thin index of every trace_id observed in the last 7 days. Lets
-- the obs dashboard (Phase 8 agentic_rag_observability extension) follow a
-- single user request across multiple edge fns.
CREATE TABLE IF NOT EXISTS public.wh_traces (
  trace_id    TEXT        NOT NULL,
  route       TEXT        NOT NULL,
  hive_id     TEXT,
  user_id     TEXT,
  status      INTEGER,
  latency_ms  INTEGER,
  model_chain TEXT[],
  error_code  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (trace_id, route, created_at)
);

CREATE INDEX IF NOT EXISTS wh_traces_created_at_idx ON public.wh_traces (created_at DESC);
CREATE INDEX IF NOT EXISTS wh_traces_hive_idx       ON public.wh_traces (hive_id, created_at DESC);
CREATE INDEX IF NOT EXISTS wh_traces_trace_idx      ON public.wh_traces (trace_id);

ALTER TABLE public.wh_traces ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS wh_traces_service_all ON public.wh_traces;
CREATE POLICY wh_traces_service_all ON public.wh_traces
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS wh_traces_hive_read ON public.wh_traces;
CREATE POLICY wh_traces_hive_read ON public.wh_traces
  FOR SELECT TO authenticated
  USING (hive_id = current_setting('request.jwt.claims', true)::json->>'hive_id');


-- ── 4. wh_health_status ─────────────────────────────────────────────────────
-- canonical-allow: operational status table; not a data source. Last-known health snapshot per surface, populated by edge-fn /health probes.
-- Last-known health per surface area (edge fn or page). Updated by
-- voice-health and per-fn /health pings. Lets the platform-health dashboard
-- render real status without polling N endpoints from the frontend.
CREATE TABLE IF NOT EXISTS public.wh_health_status (
  surface       TEXT        PRIMARY KEY,
  status        TEXT        NOT NULL CHECK (status IN ('ok', 'degraded', 'down')),
  latency_ms    INTEGER,
  detail        JSONB,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.wh_health_status ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS wh_health_service_all ON public.wh_health_status;
CREATE POLICY wh_health_service_all ON public.wh_health_status
  FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS wh_health_public_read ON public.wh_health_status;
CREATE POLICY wh_health_public_read ON public.wh_health_status
  FOR SELECT TO authenticated, anon USING (true);


-- ── GRANTs ──────────────────────────────────────────────────────────────────
-- Required for RLS-enabled tables — without explicit GRANT the anon and
-- authenticated roles get 401 from PostgREST even when RLS policies allow
-- the row read. Service role bypasses RLS so it doesn't need explicit GRANT
-- here, but we add it for symmetry with existing migrations.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.ai_cache             TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.ai_user_rate_limits  TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wh_traces            TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.wh_health_status     TO anon, authenticated;


-- ── Canonical sources registration ──────────────────────────────────────────
-- Register all 4 new tables in canonical_sources so the L1 fuel-anchor gate
-- recognizes them. They are infrastructure tables (not data sources users
-- query directly), so contract metadata is minimal.
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('ai_cache_infra', 'table', 'ai_cache', 'ai-engineer', 'realtime',
   'Hash-keyed LLM response cache (deterministic prompts). Internal-only.',
   jsonb_build_object('key', jsonb_build_array('key'), 'hive_scoped', false, 'ttl_default_seconds', 86400),
   'Populated by _shared/cache.ts. Swept by ai_cache_sweep_expired RPC.'),
  ('rate_limit_infra', 'table', 'ai_user_rate_limits', 'ai-engineer', 'realtime',
   'Per-user hourly budget counter inside the per-hive rate-limit bucket.',
   jsonb_build_object('key', jsonb_build_array('user_id'), 'hive_scoped', true, 'window', '1 hour'),
   'Populated by _shared/rate-limit.ts checkUserRateLimit.'),
  ('observability_infra', 'table', 'wh_traces', 'devops', 'realtime',
   'Cross-fn trace-id index for request correlation. Hive-scoped RLS read.',
   jsonb_build_object('key', jsonb_build_array('trace_id', 'route', 'created_at'), 'hive_scoped', true, 'retention_days', 7),
   'Optional write — only fns that opt in record traces here.'),
  ('observability_infra_health', 'table', 'wh_health_status', 'devops', 'realtime',
   'Last-known health snapshot per surface area (edge fn or page).',
   jsonb_build_object('key', jsonb_build_array('surface'), 'hive_scoped', false, 'public_readable', true),
   'Populated by /health probes via _shared/health.ts.')
ON CONFLICT DO NOTHING;
