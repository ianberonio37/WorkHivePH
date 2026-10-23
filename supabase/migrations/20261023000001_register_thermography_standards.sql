-- Register the two thermography standards canonical/standards.json gained in the 2026-09-29 release.
--
-- WHY: the release gate's Tier-S drift check (test-data-seeder run_tests.py §22) found the file and the registry
-- apart: canonical/standards.json names iso_18434_1_2008 and neta_mts_2023, and canonical_standards holds neither,
-- so a citation of either would anchor to nothing. Same shape as 20260520000014 (IEC 60812): the file is the
-- source, the table is the anchor a validator resolves citations against.

BEGIN;

INSERT INTO public.canonical_standards (standard_id, body, number, version, discipline, title, contract) VALUES
  ('iso_18434_1_2008', 'ISO',  '18434-1', '2008', 'maintenance',
   'ISO 18434-1:2008 — Condition monitoring and diagnostics of machines — Thermography — Part 1: General procedures',
   '{"clauses": ["general_procedures"], "ref_count": 0}'::jsonb),
  -- body ANSI: it is published as ANSI/NETA MTS-2023, and canonical_standards_body_check names no NETA
  ('neta_mts_2023',    'ANSI', 'NETA MTS', '2023', 'electrical',
   'ANSI/NETA MTS-2023 — Maintenance Testing Specifications for Electrical Power Equipment and Systems',
   '{"clauses": ["100.18 thermographic survey"], "ref_count": 0}'::jsonb)
ON CONFLICT (standard_id) DO NOTHING;

COMMIT;
