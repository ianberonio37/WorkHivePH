-- Q4 (partial) -- Free-Tier Quota Roadmap: per-day AI ceiling alongside the hourly cap.
-- ==================================================================================
-- FREE_TIER_QUOTA_ROADMAP Phase Q4: "add a daily AI cap alongside the hourly one."
-- The LLM is the SCARCEST free-tier resource (Groq ~9,000 req/day SHARED across ALL
-- hives — see §6 10k math: ~0.9 req/user/day). The existing gate (_shared/rate-limit.ts
-- checkAIRateLimit) enforces only a rolling 1-HOUR window; a hive could sit just under
-- the hourly cap all day and still drain a huge slice of the shared daily budget.
--
-- This adds a second, DAILY rolling window to the counter tables. The edge-function gate
-- (checkAIRateLimit / checkSoloRateLimit) reads day_count/day_window_start and denies when
-- the per-day ceiling is hit, independently of the hourly window. Backward-compatible:
-- day_count defaults 0, day_window_start NULL => treated as a fresh day on first call.

BEGIN;

ALTER TABLE public.ai_rate_limits
  ADD COLUMN IF NOT EXISTS day_count        integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS day_window_start timestamptz;

ALTER TABLE public.ai_user_rate_limits
  ADD COLUMN IF NOT EXISTS day_count        integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS day_window_start timestamptz;

COMMENT ON COLUMN public.ai_rate_limits.day_count IS
  'Q4: rolling per-day AI call count (per hive). Reset when day_window_start ages past 24h.';
COMMENT ON COLUMN public.ai_user_rate_limits.day_count IS
  'Q4: rolling per-day AI call count (per identity). Reset when day_window_start ages past 24h.';

-- ── Q4 file-ingest caps: pdf_jobs per-file size + per-hive jobs/day ──────────────
-- PDF ingestion is the most expensive write (it embeds EVERY chunk via the LLM/embed
-- chain). The edge fn (pdf-ingest) already rejects >200 chunks at PROCESS time, but only
-- AFTER a giant chunks_json is stored. These triggers bound it at INSERT: a chunk cap
-- (mirrors MAX_CHUNKS_PER_JOB=200) before the row is stored, and a per-hive jobs/day cap
-- (reusing the Q2 generic check_daily_row_cap; identity = uploaded_by).
CREATE OR REPLACE FUNCTION public.cap_pdf_job_size()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  n := CASE WHEN jsonb_typeof(NEW.chunks_json) = 'array'
            THEN jsonb_array_length(NEW.chunks_json) ELSE 0 END;
  IF n > 200 THEN
    RAISE EXCEPTION 'PDF too large: % chunks exceeds the 200-chunk limit. Split the document.', n
      USING ERRCODE = '54000', HINT = 'pdf_chunks';
  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_pdf_job_size() OWNER TO postgres;
DROP TRIGGER IF EXISTS trg_cap_pdf_job_size ON public.pdf_jobs;
CREATE TRIGGER trg_cap_pdf_job_size BEFORE INSERT ON public.pdf_jobs
  FOR EACH ROW EXECUTE FUNCTION public.cap_pdf_job_size();

DROP TRIGGER IF EXISTS trg_daily_cap_pdf_jobs ON public.pdf_jobs;
CREATE TRIGGER trg_daily_cap_pdf_jobs BEFORE INSERT ON public.pdf_jobs
  FOR EACH ROW EXECUTE FUNCTION public.check_daily_row_cap('20', 'created_at', 'uploaded_by', '10');

COMMIT;
