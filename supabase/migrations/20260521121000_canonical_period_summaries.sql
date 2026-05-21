-- Canonical Period Summaries (Phase 2 of AGENTIC_RAG_ROADMAP.md)
--
-- The hierarchical chunking foundation: pre-computed Daily → Weekly →
-- Monthly → Quarterly → Yearly natural-language + structured digests
-- per hive per asset. The mechanism that makes 5-year-horizon queries
-- tractable on free-tier LLMs: agentic-rag-loop's Retriever pulls the
-- appropriate level (yearly for 5y queries, monthly for 6mo queries)
-- instead of dumping 50,000 raw logbook rows into the model's context.
--
-- Access pattern is primarily structured (filter by hive_id + asset_tag +
-- level + period_end), not vector. The embedding column is nullable for
-- a future cross-period semantic search lane; it does not block the core
-- hierarchical retrieval flow.
--
-- Free-tier constraint: structured stats (summary_json) computed
-- deterministically in TypeScript/Python; only the 1-2 paragraph
-- summary_text is generated via the free-tier callAI chain.

-- canonical-allow: infrastructure rollup cache for agentic RAG hierarchical retrieval — not a user-facing truth source
CREATE TABLE IF NOT EXISTS public.canonical_period_summaries (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  asset_tag       text,                            -- nullable: hive-level rollups
  level           text NOT NULL CHECK (level IN ('day','week','month','quarter','year')),
  period_start    date NOT NULL,
  period_end      date NOT NULL,
  summary_text    text NOT NULL,                   -- 1-2 paragraph natural-language digest
  summary_json    jsonb NOT NULL,                  -- {failure_count, mtbf_days, mttr_h, top_assets, top_root_causes, pm_overdue, downtime_h}
  embedding       vector(384),                     -- nullable: filled by future enrichment pass
  source_row_ids  uuid[],                          -- traceability back to logbook rows
  standard_cites  text[],                          -- e.g. ['ISO 14224:2016#7.1', 'ISO 22400-2:2014#5.3.1']
  generated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (hive_id, asset_tag, level, period_start)
);

CREATE INDEX IF NOT EXISTS idx_cps_hive_level_period ON public.canonical_period_summaries (hive_id, level, period_end DESC);
CREATE INDEX IF NOT EXISTS idx_cps_asset_level      ON public.canonical_period_summaries (asset_tag, level, period_end DESC);
CREATE INDEX IF NOT EXISTS idx_cps_period_start    ON public.canonical_period_summaries (period_start DESC);
-- ivfflat index on embedding deferred until the column is populated (empty
-- ivfflat is wasteful). Add when the enrichment pass completes first run.

GRANT SELECT, INSERT, UPDATE ON public.canonical_period_summaries TO anon, authenticated;

ALTER TABLE public.canonical_period_summaries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS cps_read   ON public.canonical_period_summaries;
DROP POLICY IF EXISTS cps_insert ON public.canonical_period_summaries;
DROP POLICY IF EXISTS cps_update ON public.canonical_period_summaries;

CREATE POLICY cps_read ON public.canonical_period_summaries
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND hive_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = canonical_period_summaries.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Inserts and updates only via service role (the hierarchical-summarizer
-- edge function uses SUPABASE_SERVICE_ROLE_KEY). Block direct anon/auth
-- writes so consumers cannot poison the canonical summaries.
CREATE POLICY cps_insert ON public.canonical_period_summaries
  FOR INSERT WITH CHECK (false);
CREATE POLICY cps_update ON public.canonical_period_summaries
  FOR UPDATE USING (false);
