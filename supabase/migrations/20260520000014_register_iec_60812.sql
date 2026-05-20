-- Register IEC 60812 in canonical_standards.
--
-- WHY: validate_canonical_anchor L6 (Tier D-s) flagged 2 un-anchored
-- references introduced when analytics-orchestrator and asset-brain-query
-- AI prompts started citing IEC 60812 (FMEA) for risk-score grounding.
--
-- Both `iec_60812` and the year-qualified `iec_60812_2018` get registered
-- (the validator normalises citations to lowercase + underscores, so each
-- form needs its own row to be a clean anchor).

BEGIN;

INSERT INTO public.canonical_standards (standard_id, body, number, version, discipline, title, contract) VALUES
  ('iec_60812',      'IEC', '60812', '',     'reliability', 'IEC 60812 — Failure Modes and Effects Analysis (FMEA and FMECA)',      '{"clauses": ["6.3 RPN", "8.4 severity"], "ref_count": 2}'::jsonb),
  ('iec_60812_2018', 'IEC', '60812', '2018', 'reliability', 'IEC 60812:2018 — Failure Modes and Effects Analysis (FMEA and FMECA)', '{"clauses": ["6.3 RPN", "8.4 severity"], "ref_count": 1}'::jsonb)
ON CONFLICT (standard_id) DO NOTHING;

COMMIT;
