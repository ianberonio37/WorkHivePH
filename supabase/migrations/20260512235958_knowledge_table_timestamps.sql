-- Add created_at columns to skill_knowledge + pm_knowledge.
--
-- Discovered during the 2026-05-13 walkthrough applying Phase 4 to a fresh
-- local stack: v_knowledge_freshness_truth UNIONs fault_knowledge +
-- skill_knowledge + pm_knowledge expecting created_at on each, but only
-- fault_knowledge had the column. The view fails with "column created_at
-- does not exist" on the skill_knowledge and pm_knowledge SELECT clauses.
--
-- This is a forward-only column addition. DEFAULT now() so existing rows
-- get a sane timestamp (the actual creation date is lost on legacy rows,
-- but freshness calculations stay sensible: rows backfilled at migration
-- time look "fresh" to the freshness view, which is the correct default
-- for an analytics surface).
--
-- The timestamp is intentionally before today's 20260513* sequence so this
-- migration sorts ahead of Phase 4 (which depends on the columns).

BEGIN;

ALTER TABLE public.skill_knowledge
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE public.pm_knowledge
  ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_skill_knowledge_created
  ON public.skill_knowledge (hive_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pm_knowledge_created
  ON public.pm_knowledge (hive_id, created_at DESC);

COMMIT;
