-- Register ISO 20816-3, the standard the vibration work now cites (2026-10-27).
--
-- WHY: the KA-R refresh (2026-10-27) moved the vibration SOW, the vibration-isolation calculator and the python-api
-- vibration calc onto ISO 20816-3 for industrial machines (zones by machine group: 2.8 mm/s rms for 15-300 kW rigid),
-- keeping ISO 10816-1 for the Class I-IV zones. canonical_standards held iso_20816 and iso_20816_1 but not part 3, so
-- the canonical-anchor gate (L6) found three files citing a standard the registry cannot resolve. Same shape as the
-- 2026-05-12 foundation rows (iso_10816_3, iso_20816_1): id without the edition, the edition named in the title.

BEGIN;

INSERT INTO public.canonical_standards (standard_id, body, number, version, discipline, title, contract) VALUES
  ('iso_20816_3', 'ISO', '20816-3', '2022', 'mechanical',
   'ISO 20816-3:2022 — Mechanical vibration — Measurement and evaluation of machine vibration — Part 3: Industrial machines with a power rating above 15 kW and operating speeds between 120 r/min and 30 000 r/min',
   '{"clauses": ["evaluation zones by machine group and support"], "ref_count": 3}'::jsonb)
ON CONFLICT (standard_id) DO NOTHING;

COMMIT;
