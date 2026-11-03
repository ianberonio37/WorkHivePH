-- Register the three standards Wave ED's engineering-design fixes now cite (2026-11-03).
--
-- WHY: the engineering-design wave (G1/B1, 2026-11-01..02) put three standards into the calculator's guides, its
-- reports and the BOM/SOW agent: ISO 8528-5 for a generator set's voltage-dip limit on motor starting (class G2, 20%),
-- ISO 1940-1 for the balancing grades the vibration guide quotes beside ISO 21940-11, and NEC Article 460 for the
-- capacitor bank's conductor and protection sizing (460.8, 135% of rated current). canonical_standards holds the parent
-- documents (iso_8528, iso_1940) and the NEC articles the other agents cite (220/240/250/310/392/430/630), but not these
-- three, so the canonical-anchor gate (L6) found files citing a standard the registry cannot resolve. Same shape as the
-- sibling rows: id without the edition, body + number, the discipline, ref_count = files citing it today.

BEGIN;

INSERT INTO public.canonical_standards (standard_id, body, number, version, discipline, title, contract) VALUES
  ('iso_8528_5', 'ISO', '8528-5', '2018', 'electrical',
   'ISO 8528-5:2018 — Reciprocating internal combustion engine driven alternating current generating sets — Part 5: Generating sets',
   '{"clauses": ["transient voltage deviation on load acceptance by performance class (G1-G4)"], "ref_count": 2}'::jsonb),
  ('iso_1940_1', 'ISO', '1940-1', '2003', 'mechanical',
   'ISO 1940-1:2003 — Mechanical vibration — Balance quality requirements for rotors in a constant (rigid) state (superseded by ISO 21940-11)',
   '{"clauses": ["balance quality grades G by machine type (Table 1)"], "ref_count": 2}'::jsonb),
  ('nec_460', 'NEC', '460', '2023', 'electrical',
   'NEC Article 460 — Capacitors (PEC 2017 Article 4.60)',
   '{"clauses": ["460.8 conductor ampacity not less than 135% of the capacitor rated current, and its overcurrent protection"], "ref_count": 1}'::jsonb)
ON CONFLICT (standard_id) DO NOTHING;

COMMIT;
