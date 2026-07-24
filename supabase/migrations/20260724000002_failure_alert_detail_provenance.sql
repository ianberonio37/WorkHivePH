-- 20260724000002 — failure_signature_alerts.detail_source (AI6 · agentic write accountability)
--
-- FOUND (2026-07-24, dimension-expansion flywheel loop 21, by tools/validate_ai_write_provenance.py):
-- `failure-signature-scan` DETECTS deterministically (rule_id + evidence — genuinely accountable),
-- but the `alert_detail` prose a supervisor actually READS ("what to do NOW") is written by an LLM
-- via generateAlertDetail(). Nothing on the row says so. Worse, that helper silently falls back to
-- a canned string when the AI call fails or returns empty — so today an alert_detail can be either
-- model analysis or a template, and the row cannot tell you which. A supervisor acting on that
-- text deserves to know which one they are reading.
--
-- Deliberately NOT reusing `source`: on fault_knowledge/rcm_fmea_modes `source` describes who
-- authored the RECORD. Here the record is rule-authored and only the DETAIL FIELD is AI-authored —
-- a different claim, so it gets its own honest column rather than overloading an existing one.

-- DEFAULT IS 'unknown', NOT 'rule'. Back-filling pre-existing rows as 'rule' would assert that a
-- deterministic template wrote text an LLM may well have written — and a supervisor TRUSTS a rule
-- more than a model, so that mislabel errs toward OVER-trust, the exact harm this column exists to
-- prevent. Rows written before provenance was tracked are honestly 'unknown'; only rows written by
-- the current code claim 'ai' or 'rule'.
ALTER TABLE public.failure_signature_alerts
  ADD COLUMN IF NOT EXISTS detail_source text NOT NULL DEFAULT 'unknown';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'failure_signature_alerts_detail_source_check'
  ) THEN
    ALTER TABLE public.failure_signature_alerts
      ADD CONSTRAINT failure_signature_alerts_detail_source_check
      CHECK (detail_source IN ('ai', 'rule', 'unknown'));
  END IF;
END $$;

COMMENT ON COLUMN public.failure_signature_alerts.detail_source IS
  'Who wrote alert_detail: ai (LLM-generated guidance), rule (deterministic fallback template), or '
  'unknown (written before provenance was tracked). The ALERT itself is always rule-derived — see '
  'rule_id + evidence. Never default an untracked row to rule: that over-claims determinism for '
  'text a model may have produced.';
