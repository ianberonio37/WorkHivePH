-- 20260724000001 — fault_knowledge AI provenance (AI6 · agentic write accountability)
--
-- FOUND (2026-07-24, dimension-expansion flywheel loop 21): `visual-defect-capture` writes
-- MODEL-GENERATED diagnostic content (draft.problem / root_cause / action / knowledge) into
-- fault_knowledge stamped `worker_name = <the signed-in human>`, with NO field marking it as
-- AI-generated. fault_knowledge is then read back by `intelligence-api`, `intelligence-report`
-- and `semantic-search` (RPC search_fault_knowledge) — so a model's own inference re-enters the
-- knowledge base and RAG indistinguishable from human field experience, attributed to a named
-- technician who never wrote it. Two harms: (1) ACCOUNTABILITY — a worker's name sits on a
-- diagnosis they may disagree with; (2) EPISTEMIC CONTAMINATION — AI output gets cited back as
-- field-verified ground truth, a self-reinforcing loop.
--
-- FIX MIRRORS THE CONVENTION THE PLATFORM ALREADY USES rather than inventing one:
-- `rcm_fmea_modes` already distinguishes source='manual' vs source='ai_logbook' while keeping
-- created_by = the human (who triggered it) and ai_confidence alongside. fault_knowledge simply
-- never got that column. Same shape here.
--
-- BACKFILL IS HONEST: all 554 existing rows pre-date the AI capture path (maintenance_type is
-- NULL on every one of them — they came from logbook/seed), so DEFAULT 'manual' states a fact,
-- it does not launder unknown rows as human-authored.

ALTER TABLE public.fault_knowledge
  ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'manual',
  ADD COLUMN IF NOT EXISTS ai_model text,
  ADD COLUMN IF NOT EXISTS ai_confidence numeric;

-- Constrain to the known provenance vocabulary (extend deliberately, not by typo).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fault_knowledge_source_check'
  ) THEN
    ALTER TABLE public.fault_knowledge
      ADD CONSTRAINT fault_knowledge_source_check
      CHECK (source IN ('manual', 'ai_visual_capture', 'cmms_import'));
  END IF;
END $$;

COMMENT ON COLUMN public.fault_knowledge.source IS
  'Provenance of this knowledge row: manual (a human wrote it), ai_visual_capture '
  '(drafted by visual-defect-capture from a photo), cmms_import (imported from an external CMMS). '
  'worker_name stays the human who CAPTURED it; source says who AUTHORED it. Readers (RAG, '
  'intelligence reports, UI) must not present an ai_* row as human field experience.';
COMMENT ON COLUMN public.fault_knowledge.ai_model IS
  'Model that generated the row when source is ai_*; NULL for manual rows.';
COMMENT ON COLUMN public.fault_knowledge.ai_confidence IS
  'Model self-reported confidence (0-1) when source is ai_*; NULL for manual rows. Mirrors '
  'rcm_fmea_modes.ai_confidence.';

-- Retrieval paths filter/label by provenance; keep that cheap.
CREATE INDEX IF NOT EXISTS idx_fault_knowledge_source
  ON public.fault_knowledge (hive_id, source);
