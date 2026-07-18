-- Q6 (2026-07-05): GLOBAL platform-wide LLM budget guard — the org-shared-pool layer.
--
-- WHY (grounded 2026-07-05, Step 0): every existing rate-limit gate keys on hive_id
-- (checkAIRateLimit), (hive,user) (checkUserRateLimit), identity (checkSoloRateLimit),
-- or (hive,route) (checkRouteRateLimit). NONE of them protect the ONE resource that
-- actually binds first at scale: the LLM provider budget is ORG-LEVEL — a single Groq/
-- Cerebras/Gemini/etc. key shared across ALL hives and users. Verified free-tier limits
-- (2026): Groq 30 RPM / 1,000 RPD good-models (org-level, whichever hits first); the
-- 19-model / 5-provider chain aggregates to ~10-30K quality calls/day IF load-balanced,
-- but a synchronized burst (07:00 shift-start) saturates every provider's per-MINUTE
-- window at once (~100-150 RPM aggregate). Per-hive 300/day + solo 100/day caps do NOT
-- sum-protect that shared pool — 40 hives each doing 300/day = 12,000/day > the pool.
--
-- This adds the missing GLOBAL layer: one singleton counter row + an ATOMIC consume
-- function (row-locked; correct under the concurrent burst it exists to smooth — unlike
-- the per-tenant read-then-upsert gates, a single hot row MUST be atomic).
--
-- TWO windows + a burst-smoother policy:
--   * day_count   >= WH_GLOBAL_RPD  -> circuit-breaker: deny ALL classes (pool exhausted)
--   * minute_count>= WH_GLOBAL_RPM  -> burst wall: SHED background/deferrable calls, PASS
--                                      interactive (voice) — spreads the spike by shedding
--                                      only latency-tolerant load.
-- Telemetry columns (shed_count_today / deny_count_today) are the "time to add a provider
-- or go paid" signal — they count how often the platform hit its shared ceiling today.

CREATE TABLE IF NOT EXISTS public.ai_global_budget (
  id                  text PRIMARY KEY DEFAULT 'global',
  minute_count        int  NOT NULL DEFAULT 0,
  minute_window_start timestamptz,
  day_count           int  NOT NULL DEFAULT 0,
  day_window_start    timestamptz,
  shed_count_today    int  NOT NULL DEFAULT 0,   -- background calls shed by the minute-smoother today
  deny_count_today    int  NOT NULL DEFAULT 0,   -- calls denied by the daily circuit-breaker today
  updated_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ai_global_budget_singleton CHECK (id = 'global')
);

-- Chain-depth telemetry columns (idempotent — ADD IF NOT EXISTS so re-applying to an
-- already-created local table also gets them). These answer "are we routinely served by
-- DEEP fallback models = the primary providers are exhausted / quality is decaying =
-- time to add a provider or go paid" — a distinct signal from shed/deny (ceiling-hit).
-- depth = index of the winning model in the canonical PROVIDER_CHAIN (0 = best/primary).
ALTER TABLE public.ai_global_budget ADD COLUMN IF NOT EXISTS depth_samples_today int NOT NULL DEFAULT 0;
ALTER TABLE public.ai_global_budget ADD COLUMN IF NOT EXISTS depth_sum_today     int NOT NULL DEFAULT 0;  -- avg depth = sum/samples
ALTER TABLE public.ai_global_budget ADD COLUMN IF NOT EXISTS max_depth_today     int NOT NULL DEFAULT 0;

-- Seed the singleton row so the first consume never races on INSERT.
INSERT INTO public.ai_global_budget (id) VALUES ('global') ON CONFLICT (id) DO NOTHING;

-- Atomic consume: row-locked read-modify-write in ONE statement. Returns the decision
-- + remaining headroom. SECURITY DEFINER so the anon/authenticated edge role can call it
-- without direct table grants; search_path pinned (no schema-injection surface).
CREATE OR REPLACE FUNCTION public.consume_ai_global_budget(
  p_rpm int,
  p_rpd int,
  p_is_background boolean
) RETURNS TABLE(allowed boolean, scope text, minute_remaining int, day_remaining int)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  r              public.ai_global_budget%ROWTYPE;
  v_minute_fresh boolean;
  v_day_fresh    boolean;
  v_min          int;
  v_day          int;
  v_shed         int;
  v_deny         int;
BEGIN
  -- Ensure the singleton exists, then take a row lock so concurrent callers serialize
  -- on exactly this one row (the whole point — a shared counter must not lose updates).
  INSERT INTO public.ai_global_budget(id) VALUES ('global') ON CONFLICT (id) DO NOTHING;
  SELECT * INTO r FROM public.ai_global_budget WHERE id = 'global' FOR UPDATE;

  v_minute_fresh := r.minute_window_start IS NOT NULL AND r.minute_window_start >= now() - interval '60 seconds';
  v_day_fresh    := r.day_window_start    IS NOT NULL AND r.day_window_start    >= now() - interval '24 hours';
  v_min  := CASE WHEN v_minute_fresh THEN r.minute_count ELSE 0 END;
  v_day  := CASE WHEN v_day_fresh    THEN r.day_count    ELSE 0 END;
  -- shed/deny telemetry resets together with the day window.
  v_shed := CASE WHEN v_day_fresh THEN r.shed_count_today ELSE 0 END;
  v_deny := CASE WHEN v_day_fresh THEN r.deny_count_today ELSE 0 END;

  -- (1) Daily circuit-breaker — the org-wide pool is exhausted; deny EVERY class.
  IF v_day >= p_rpd THEN
    UPDATE public.ai_global_budget SET
      minute_count        = v_min,
      minute_window_start = CASE WHEN v_minute_fresh THEN r.minute_window_start ELSE now() END,
      day_count           = v_day,
      day_window_start    = CASE WHEN v_day_fresh THEN r.day_window_start ELSE now() END,
      shed_count_today    = v_shed,
      deny_count_today    = v_deny + 1,
      updated_at          = now()
    WHERE id = 'global';
    RETURN QUERY SELECT false, 'global-day'::text, GREATEST(0, p_rpm - v_min), 0;
    RETURN;
  END IF;

  -- (2) Per-minute burst wall — shed DEFERRABLE (background) load, let interactive through.
  IF v_min >= p_rpm AND p_is_background THEN
    UPDATE public.ai_global_budget SET
      minute_count        = v_min,
      minute_window_start = CASE WHEN v_minute_fresh THEN r.minute_window_start ELSE now() END,
      day_count           = v_day,
      day_window_start    = CASE WHEN v_day_fresh THEN r.day_window_start ELSE now() END,
      shed_count_today    = v_shed + 1,
      deny_count_today    = v_deny,
      updated_at          = now()
    WHERE id = 'global';
    RETURN QUERY SELECT false, 'global-minute'::text, 0, GREATEST(0, p_rpd - v_day);
    RETURN;
  END IF;

  -- (3) Allowed — consume one unit of BOTH windows (interactive calls over the minute
  -- wall still count so the day budget stays accurate; they are simply not shed).
  UPDATE public.ai_global_budget SET
    minute_count        = (CASE WHEN v_minute_fresh THEN v_min ELSE 0 END) + 1,
    minute_window_start = CASE WHEN v_minute_fresh THEN r.minute_window_start ELSE now() END,
    day_count           = v_day + 1,
    day_window_start    = CASE WHEN v_day_fresh THEN r.day_window_start ELSE now() END,
    shed_count_today    = v_shed,
    deny_count_today    = v_deny,
    updated_at          = now()
  WHERE id = 'global';
  RETURN QUERY SELECT true, NULL::text, GREATEST(0, p_rpm - v_min - 1), GREATEST(0, p_rpd - v_day - 1);
END;
$fn$;

GRANT EXECUTE ON FUNCTION public.consume_ai_global_budget(int, int, boolean) TO anon, authenticated, service_role;

COMMENT ON TABLE public.ai_global_budget IS
  'Q6 2026-07-05: singleton platform-wide LLM budget counter (org-shared pool). The layer above per-hive/per-user/per-solo gates — those key on a tenant and cannot protect the ONE shared provider budget. minute_count=burst wall, day_count=daily circuit-breaker, shed/deny_today=ceiling-hit telemetry, depth_*_today=chain-depth (quality-decay) telemetry.';

-- Chain-depth telemetry recorder. Fire-and-forget from callAI's onServed hook when a
-- model serves an answer. p_depth = winning model's index in the canonical PROVIDER_CHAIN
-- (0 = primary). Rolls the depth aggregates with the SAME day window consume manages, so
-- avg/max depth are always "today". Cheap single-row upsert; never blocks the answer path.
CREATE OR REPLACE FUNCTION public.record_ai_chain_depth(p_depth int)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
  r           public.ai_global_budget%ROWTYPE;
  v_day_fresh boolean;
BEGIN
  IF p_depth IS NULL OR p_depth < 0 THEN RETURN; END IF;
  INSERT INTO public.ai_global_budget(id) VALUES ('global') ON CONFLICT (id) DO NOTHING;
  SELECT * INTO r FROM public.ai_global_budget WHERE id = 'global' FOR UPDATE;
  v_day_fresh := r.day_window_start IS NOT NULL AND r.day_window_start >= now() - interval '24 hours';

  IF v_day_fresh THEN
    UPDATE public.ai_global_budget SET
      depth_samples_today = r.depth_samples_today + 1,
      depth_sum_today     = r.depth_sum_today + p_depth,
      max_depth_today     = GREATEST(r.max_depth_today, p_depth),
      updated_at          = now()
    WHERE id = 'global';
  ELSE
    -- day window rolled (or never started) — reset the depth aggregates to just this sample.
    UPDATE public.ai_global_budget SET
      depth_samples_today = 1,
      depth_sum_today     = p_depth,
      max_depth_today     = p_depth,
      updated_at          = now()
    WHERE id = 'global';
  END IF;
END;
$fn$;

GRANT EXECUTE ON FUNCTION public.record_ai_chain_depth(int) TO anon, authenticated, service_role;
