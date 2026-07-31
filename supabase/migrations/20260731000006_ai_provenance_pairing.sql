-- 20260731000006_ai_provenance_pairing.sql
--
-- AI WRITE ACCOUNTABILITY. `fault_knowledge` carries source / ai_model / ai_confidence, and NOTHING paired
-- them: probed 2026-07-31, both directions were accepted —
--   * source='ai_visual_capture' with ai_model NULL  -> an AI diagnosis with no record of WHICH model said it
--   * source='manual' with ai_model='gemini-2.0-flash' -> a human entry wearing an AI badge
--
-- That is the AI6 class: the platform's AI checks grade the ANSWER (is it right, is it grounded, is it safe)
-- and none grade the ACT — who wrote this row, and under whose name. A maintenance record is read months
-- later by someone deciding whether to trust it; "a machine suggested this" and "a technician saw this" are
-- different claims and must not be interchangeable.
--
-- A CHECK, not a trigger, because the rule is a property of the ROW and needs no context to decide. It is an
-- equivalence in BOTH directions: an ai_* source requires a model, and a non-ai source must not carry one.
-- All 3,811 existing rows are source='manual' with ai_model NULL, so (false = false) holds and the constraint
-- validates without a rewrite.

BEGIN;

ALTER TABLE public.fault_knowledge
  ADD CONSTRAINT fault_knowledge_ai_provenance_pairing
  CHECK ((source LIKE 'ai\_%') = (ai_model IS NOT NULL));

COMMENT ON CONSTRAINT fault_knowledge_ai_provenance_pairing ON public.fault_knowledge IS
  'AI6 accountability: an ai_* sourced row MUST name the model that produced it, and a human/import row must '
  'NOT claim one. Knowledge is read months later by someone deciding whether to trust it - "a machine '
  'suggested this" and "a technician saw this" are different claims.';

COMMIT;
