-- Tier B + C + D + E foundation registries (2026-05-12).
--
-- Phases 2-7 of the canonical layers initiative shipped as a single
-- coordinated migration:
--
--   Tier D-s: canonical_standards   (197 standards seeded)
--   Tier D-f: canonical_formulas    (6 maintenance formulas seeded)
--   Tier C  : canonical_agent_contracts (7 brain output JSON Schemas)
--   Tier B  : v_project_truth + v_knowledge_truth views
--   Tier E  : v_audit_unified view
--
-- Skills consulted: architect (registry FK contract), data-engineer
-- (UNION ALL views), maintenance-expert (ISO/SMRP/SAE taxonomy),
-- security (locked policies), platform-guardian (forward-only ratchet).

BEGIN;

-- =============================================================================
-- PART 1. Tier D-s: canonical_standards registry
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.canonical_standards (
  standard_id   text PRIMARY KEY,
  body          text NOT NULL
                CHECK (body IN ('ISO','IEC','SAE','ASHRAE','NFPA','NEC','IEEE','ANSI','ASTM','IESNA','OSHA','SMRP','SAEJA','ASME')),
  number        text NOT NULL,
  version       text NOT NULL DEFAULT '',
  discipline    text NOT NULL,
  title         text NOT NULL,
  contract      jsonb NOT NULL DEFAULT '{}'::jsonb,
  url           text,
  registered_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.canonical_standards IS
  'Tier D-s: every standards-body citation used across the platform. canonical_formulas rows reference these by standard_id. AI agents look up standards here for citations + scope.';

CREATE INDEX IF NOT EXISTS idx_canonical_standards_body ON public.canonical_standards (body);
CREATE INDEX IF NOT EXISTS idx_canonical_standards_disc ON public.canonical_standards (discipline);

GRANT SELECT ON public.canonical_standards TO anon, authenticated;
ALTER TABLE public.canonical_standards ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS canonical_standards_read ON public.canonical_standards;
CREATE POLICY canonical_standards_read ON public.canonical_standards FOR SELECT USING (true);
DROP POLICY IF EXISTS canonical_standards_locked ON public.canonical_standards;
CREATE POLICY canonical_standards_locked ON public.canonical_standards FOR ALL USING (false) WITH CHECK (false);

INSERT INTO public.canonical_standards (standard_id, body, number, version, discipline, title, contract) VALUES
  ('ansi_42', 'ANSI', '42', '', 'general', 'ANSI 42', '{"ref_count":1}'::jsonb),
  ('ansi_44', 'ANSI', '44', '', 'mechanical', 'ANSI 44', '{"ref_count":3}'::jsonb),
  ('ansi_55', 'ANSI', '55', '', 'mechanical', 'ANSI 55', '{"ref_count":2}'::jsonb),
  ('ansi_61', 'ANSI', '61', '', 'mechanical', 'ANSI 61', '{"ref_count":3}'::jsonb),
  ('ashrae_111', 'ASHRAE', '111', '', 'hvac', 'ASHRAE 111', '{"ref_count":1}'::jsonb),
  ('ashrae_15', 'ASHRAE', '15', '', 'hvac', 'ASHRAE 15', '{"ref_count":3}'::jsonb),
  ('ashrae_188', 'ASHRAE', '188', '', 'hvac', 'ASHRAE 188', '{"ref_count":1}'::jsonb),
  ('ashrae_2019', 'ASHRAE', '2019', '', 'hvac', 'ASHRAE 2019', '{"ref_count":2}'::jsonb),
  ('ashrae_2021', 'ASHRAE', '2021', '', 'hvac', 'ASHRAE 2021', '{"ref_count":13}'::jsonb),
  ('ashrae_2022', 'ASHRAE', '2022', '', 'hvac', 'ASHRAE 2022', '{"ref_count":3}'::jsonb),
  ('ashrae_2023', 'ASHRAE', '2023', '', 'hvac', 'ASHRAE 2023', '{"ref_count":4}'::jsonb),
  ('ashrae_52', 'ASHRAE', '52', '', 'hvac', 'ASHRAE 52', '{"ref_count":1}'::jsonb),
  ('ashrae_55', 'ASHRAE', '55', '', 'hvac', 'ASHRAE 55', '{"ref_count":2}'::jsonb),
  ('ashrae_62', 'ASHRAE', '62', '', 'hvac', 'ASHRAE 62', '{"ref_count":9}'::jsonb),
  ('ashrae_90', 'ASHRAE', '90', '', 'hvac', 'ASHRAE 90', '{"ref_count":11}'::jsonb),
  ('iec_60034_1', 'IEC', '60034-1', '', 'electrical', 'IEC 60034-1', '{"ref_count":1}'::jsonb),
  ('iec_60072', 'IEC', '60072', '', 'electrical', 'IEC 60072', '{"ref_count":1}'::jsonb),
  ('iec_60076', 'IEC', '60076', '', 'electrical', 'IEC 60076', '{"ref_count":2}'::jsonb),
  ('iec_60076_1', 'IEC', '60076-1', '', 'electrical', 'IEC 60076-1', '{"ref_count":5}'::jsonb),
  ('iec_60076_5', 'IEC', '60076-5', '', 'electrical', 'IEC 60076-5', '{"ref_count":1}'::jsonb),
  ('iec_60099_4', 'IEC', '60099-4', '', 'electrical', 'IEC 60099-4', '{"ref_count":2}'::jsonb),
  ('iec_60228', 'IEC', '60228', '', 'electrical', 'IEC 60228', '{"ref_count":2}'::jsonb),
  ('iec_60296', 'IEC', '60296', '', 'electrical', 'IEC 60296', '{"ref_count":1}'::jsonb),
  ('iec_60364', 'IEC', '60364', '', 'electrical', 'IEC 60364', '{"ref_count":4}'::jsonb),
  ('iec_60364_5', 'IEC', '60364-5', '', 'electrical', 'IEC 60364-5', '{"ref_count":3}'::jsonb),
  ('iec_60617', 'IEC', '60617', '', 'drawing_standards', 'IEC 60617', '{"ref_count":3}'::jsonb),
  ('iec_60617_04', 'IEC', '60617-04', '', 'drawing_standards', 'IEC 60617-04', '{"ref_count":2}'::jsonb),
  ('iec_60617_06', 'IEC', '60617-06', '', 'drawing_standards', 'IEC 60617-06', '{"ref_count":1}'::jsonb),
  ('iec_60617_11', 'IEC', '60617-11', '', 'drawing_standards', 'IEC 60617-11', '{"ref_count":1}'::jsonb),
  ('iec_60831', 'IEC', '60831', '', 'electrical', 'IEC 60831', '{"ref_count":1}'::jsonb),
  ('iec_60831_1', 'IEC', '60831-1', '', 'electrical', 'IEC 60831-1', '{"ref_count":3}'::jsonb),
  ('iec_60896_21', 'IEC', '60896-21', '', 'electrical', 'IEC 60896-21', '{"ref_count":1}'::jsonb),
  ('iec_60909', 'IEC', '60909', '', 'electrical', 'IEC 60909', '{"ref_count":4}'::jsonb),
  ('iec_60909_0', 'IEC', '60909-0', '', 'electrical', 'IEC 60909-0', '{"ref_count":1}'::jsonb),
  ('iec_60947', 'IEC', '60947', '', 'electrical', 'IEC 60947', '{"ref_count":2}'::jsonb),
  ('iec_61000', 'IEC', '61000', '', 'electrical', 'IEC 61000', '{"ref_count":1}'::jsonb),
  ('iec_61000_3', 'IEC', '61000-3', '', 'electrical', 'IEC 61000-3', '{"ref_count":5}'::jsonb),
  ('iec_61000_4', 'IEC', '61000-4', '', 'electrical', 'IEC 61000-4', '{"ref_count":1}'::jsonb),
  ('iec_61111', 'IEC', '61111', '', 'electrical', 'IEC 61111', '{"ref_count":1}'::jsonb),
  ('iec_61215', 'IEC', '61215', '', 'solar_pv', 'IEC 61215', '{"ref_count":3}'::jsonb),
  ('iec_61643_11', 'IEC', '61643-11', '', 'electrical', 'IEC 61643-11', '{"ref_count":2}'::jsonb),
  ('iec_61643_21', 'IEC', '61643-21', '', 'electrical', 'IEC 61643-21', '{"ref_count":2}'::jsonb),
  ('iec_61649', 'IEC', '61649', '', 'electrical', 'IEC 61649', '{"ref_count":5}'::jsonb),
  ('iec_61672', 'IEC', '61672', '', 'acoustics', 'IEC 61672', '{"ref_count":1}'::jsonb),
  ('iec_61672_1', 'IEC', '61672-1', '', 'acoustics', 'IEC 61672-1', '{"ref_count":3}'::jsonb),
  ('iec_61727', 'IEC', '61727', '', 'solar_pv', 'IEC 61727', '{"ref_count":2}'::jsonb),
  ('iec_61730', 'IEC', '61730', '', 'solar_pv', 'IEC 61730', '{"ref_count":2}'::jsonb),
  ('iec_62040_1', 'IEC', '62040-1', '', 'electrical', 'IEC 62040-1', '{"ref_count":2}'::jsonb),
  ('iec_62040_3', 'IEC', '62040-3', '', 'electrical', 'IEC 62040-3', '{"ref_count":4}'::jsonb),
  ('iec_62109', 'IEC', '62109', '', 'electrical', 'IEC 62109', '{"ref_count":1}'::jsonb),
  ('iec_62305', 'IEC', '62305', '', 'lightning_protection', 'IEC 62305', '{"ref_count":2}'::jsonb),
  ('iec_62305_1', 'IEC', '62305-1', '', 'lightning_protection', 'IEC 62305-1', '{"ref_count":3}'::jsonb),
  ('iec_62305_2', 'IEC', '62305-2', '', 'lightning_protection', 'IEC 62305-2', '{"ref_count":4}'::jsonb),
  ('iec_62305_3', 'IEC', '62305-3', '', 'lightning_protection', 'IEC 62305-3', '{"ref_count":4}'::jsonb),
  ('iec_62305_4', 'IEC', '62305-4', '', 'lightning_protection', 'IEC 62305-4', '{"ref_count":4}'::jsonb),
  ('iec_62548', 'IEC', '62548', '', 'solar_pv', 'IEC 62548', '{"ref_count":4}'::jsonb),
  ('iec_62548_2016', 'IEC', '62548', '2016', 'solar_pv', 'IEC 62548-2016', '{"ref_count":1}'::jsonb),
  ('iec_62561', 'IEC', '62561', '', 'electrical', 'IEC 62561', '{"ref_count":1}'::jsonb),
  ('iec_62930', 'IEC', '62930', '', 'electrical', 'IEC 62930', '{"ref_count":1}'::jsonb),
  ('ieee_1036', 'IEEE', '1036', '', 'electrical', 'IEEE 1036', '{"ref_count":3}'::jsonb),
  ('ieee_1036_2010', 'IEEE', '1036', '2010', 'electrical', 'IEEE 1036-2010', '{"ref_count":1}'::jsonb),
  ('ieee_1184', 'IEEE', '1184', '', 'electrical', 'IEEE 1184', '{"ref_count":4}'::jsonb),
  ('ieee_1184_2006', 'IEEE', '1184', '2006', 'electrical', 'IEEE 1184-2006', '{"ref_count":1}'::jsonb),
  ('ieee_141', 'IEEE', '141', '', 'electrical', 'IEEE 141', '{"ref_count":5}'::jsonb),
  ('ieee_142', 'IEEE', '142', '', 'electrical', 'IEEE 142', '{"ref_count":3}'::jsonb),
  ('ieee_142_2007', 'IEEE', '142', '2007', 'electrical', 'IEEE 142-2007', '{"ref_count":3}'::jsonb),
  ('ieee_1547', 'IEEE', '1547', '', 'electrical', 'IEEE 1547', '{"ref_count":1}'::jsonb),
  ('ieee_18', 'IEEE', '18', '', 'electrical', 'IEEE 18', '{"ref_count":4}'::jsonb),
  ('ieee_18_2012', 'IEEE', '18', '2012', 'electrical', 'IEEE 18-2012', '{"ref_count":1}'::jsonb),
  ('ieee_242', 'IEEE', '242', '', 'electrical', 'IEEE 242', '{"ref_count":1}'::jsonb),
  ('ieee_446', 'IEEE', '446', '', 'electrical', 'IEEE 446', '{"ref_count":5}'::jsonb),
  ('ieee_519', 'IEEE', '519', '', 'electrical', 'IEEE 519', '{"ref_count":2}'::jsonb),
  ('ieee_519_2022', 'IEEE', '519', '2022', 'electrical', 'IEEE 519-2022', '{"ref_count":5}'::jsonb),
  ('ieee_80', 'IEEE', '80', '', 'electrical', 'IEEE 80', '{"ref_count":4}'::jsonb),
  ('ieee_80_2013', 'IEEE', '80', '2013', 'electrical', 'IEEE 80-2013', '{"ref_count":3}'::jsonb),
  ('ieee_81', 'IEEE', '81', '', 'electrical', 'IEEE 81', '{"ref_count":2}'::jsonb),
  ('ieee_929', 'IEEE', '929', '', 'electrical', 'IEEE 929', '{"ref_count":1}'::jsonb),
  ('iesna_10', 'IESNA', '10', '', 'lighting', 'IESNA 10', '{"ref_count":1}'::jsonb),
  ('iso_01', 'ISO', '01', '', 'general', 'ISO 01', '{"ref_count":1}'::jsonb),
  ('iso_10628', 'ISO', '10628', '', 'general', 'ISO 10628', '{"ref_count":1}'::jsonb),
  ('iso_10767_1', 'ISO', '10767-1', '', 'hydraulic', 'ISO 10767-1', '{"ref_count":2}'::jsonb),
  ('iso_10816', 'ISO', '10816', '', 'mechanical', 'ISO 10816', '{"ref_count":3}'::jsonb),
  ('iso_10816_1', 'ISO', '10816-1', '', 'mechanical', 'ISO 10816-1', '{"ref_count":1}'::jsonb),
  ('iso_10816_3', 'ISO', '10816-3', '', 'mechanical', 'ISO 10816-3', '{"ref_count":3}'::jsonb),
  ('iso_11158', 'ISO', '11158', '', 'mechanical', 'ISO 11158', '{"ref_count":2}'::jsonb),
  ('iso_113', 'ISO', '113', '', 'general', 'ISO 113', '{"ref_count":1}'::jsonb),
  ('iso_11690', 'ISO', '11690', '', 'acoustics', 'ISO 11690', '{"ref_count":3}'::jsonb),
  ('iso_1217', 'ISO', '1217', '', 'mechanical', 'ISO 1217', '{"ref_count":3}'::jsonb),
  ('iso_1219', 'ISO', '1219', '', 'general', 'ISO 1219', '{"ref_count":1}'::jsonb),
  ('iso_13381_1', 'ISO', '13381-1', '', 'maintenance', 'ISO 13381-1', '{"ref_count":6}'::jsonb),
  ('iso_1402', 'ISO', '1402', '', 'hydraulic', 'ISO 1402', '{"ref_count":2}'::jsonb),
  ('iso_14224', 'ISO', '14224', '', 'maintenance', 'ISO 14224', '{"ref_count":13}'::jsonb),
  ('iso_14224_2016', 'ISO', '14224', '2016', 'maintenance', 'ISO 14224-2016', '{"ref_count":7}'::jsonb),
  ('iso_14520', 'ISO', '14520', '', 'fire', 'ISO 14520', '{"ref_count":3}'::jsonb),
  ('iso_14520_2015', 'ISO', '14520', '2015', 'fire', 'ISO 14520-2015', '{"ref_count":4}'::jsonb),
  ('iso_14520_7', 'ISO', '14520-7', '', 'fire', 'ISO 14520-7', '{"ref_count":1}'::jsonb),
  ('iso_14728', 'ISO', '14728', '', 'general', 'ISO 14728', '{"ref_count":1}'::jsonb),
  ('iso_15243', 'ISO', '15243', '', 'general', 'ISO 15243', '{"ref_count":1}'::jsonb),
  ('iso_16528', 'ISO', '16528', '', 'mechanical', 'ISO 16528', '{"ref_count":2}'::jsonb),
  ('iso_1940', 'ISO', '1940', '', 'mechanical', 'ISO 1940', '{"ref_count":2}'::jsonb),
  ('iso_20816', 'ISO', '20816', '', 'mechanical', 'ISO 20816', '{"ref_count":1}'::jsonb),
  ('iso_20816_1', 'ISO', '20816-1', '', 'mechanical', 'ISO 20816-1', '{"ref_count":3}'::jsonb),
  ('iso_21500', 'ISO', '21500', '', 'project_management', 'ISO 21500', '{"ref_count":5}'::jsonb),
  ('iso_21500_2021', 'ISO', '21500', '2021', 'project_management', 'ISO 21500-2021', '{"ref_count":2}'::jsonb),
  ('iso_21940', 'ISO', '21940', '', 'mechanical', 'ISO 21940', '{"ref_count":1}'::jsonb),
  ('iso_21940_11', 'ISO', '21940-11', '', 'mechanical', 'ISO 21940-11', '{"ref_count":3}'::jsonb),
  ('iso_22400_2', 'ISO', '22400-2', '', 'maintenance', 'ISO 22400-2', '{"ref_count":2}'::jsonb),
  ('iso_2372', 'ISO', '2372', '', 'mechanical', 'ISO 2372', '{"ref_count":2}'::jsonb),
  ('iso_266', 'ISO', '266', '', 'acoustics', 'ISO 266', '{"ref_count":2}'::jsonb),
  ('iso_281', 'ISO', '281', '', 'mechanical', 'ISO 281', '{"ref_count":4}'::jsonb),
  ('iso_281_2007', 'ISO', '281', '2007', 'mechanical', 'ISO 281-2007', '{"ref_count":5}'::jsonb),
  ('iso_286', 'ISO', '286', '', 'mechanical', 'ISO 286', '{"ref_count":2}'::jsonb),
  ('iso_2982', 'ISO', '2982', '', 'general', 'ISO 2982', '{"ref_count":1}'::jsonb),
  ('iso_3046', 'ISO', '3046', '', 'mechanical', 'ISO 3046', '{"ref_count":1}'::jsonb),
  ('iso_3046_1', 'ISO', '3046-1', '', 'mechanical', 'ISO 3046-1', '{"ref_count":3}'::jsonb),
  ('iso_354', 'ISO', '354', '', 'general', 'ISO 354', '{"ref_count":1}'::jsonb),
  ('iso_3745', 'ISO', '3745', '', 'acoustics', 'ISO 3745', '{"ref_count":2}'::jsonb),
  ('iso_4014', 'ISO', '4014', '', 'general', 'ISO 4014', '{"ref_count":1}'::jsonb),
  ('iso_4032', 'ISO', '4032', '', 'general', 'ISO 4032', '{"ref_count":1}'::jsonb),
  ('iso_4190_6', 'ISO', '4190-6', '', 'general', 'ISO 4190-6', '{"ref_count":1}'::jsonb),
  ('iso_4301', 'ISO', '4301', '', 'general', 'ISO 4301', '{"ref_count":1}'::jsonb),
  ('iso_4399', 'ISO', '4399', '', 'general', 'ISO 4399', '{"ref_count":1}'::jsonb),
  ('iso_4406', 'ISO', '4406', '', 'mechanical', 'ISO 4406', '{"ref_count":2}'::jsonb),
  ('iso_4413', 'ISO', '4413', '', 'hydraulic', 'ISO 4413', '{"ref_count":3}'::jsonb),
  ('iso_4413_2010', 'ISO', '4413', '2010', 'hydraulic', 'ISO 4413-2010', '{"ref_count":3}'::jsonb),
  ('iso_4414', 'ISO', '4414', '', 'general', 'ISO 4414', '{"ref_count":1}'::jsonb),
  ('iso_4427', 'ISO', '4427', '', 'mechanical', 'ISO 4427', '{"ref_count":3}'::jsonb),
  ('iso_4435', 'ISO', '4435', '', 'general', 'ISO 4435', '{"ref_count":1}'::jsonb),
  ('iso_5348', 'ISO', '5348', '', 'mechanical', 'ISO 5348', '{"ref_count":2}'::jsonb),
  ('iso_54', 'ISO', '54', '', 'general', 'ISO 54', '{"ref_count":1}'::jsonb),
  ('iso_55000', 'ISO', '55000', '', 'maintenance', 'ISO 55000', '{"ref_count":1}'::jsonb),
  ('iso_55000_2014', 'ISO', '55000', '2014', 'maintenance', 'ISO 55000-2014', '{"ref_count":4}'::jsonb),
  ('iso_55001', 'ISO', '55001', '', 'maintenance', 'ISO 55001', '{"ref_count":2}'::jsonb),
  ('iso_6020', 'ISO', '6020', '', 'hydraulic', 'ISO 6020', '{"ref_count":2}'::jsonb),
  ('iso_6020_2', 'ISO', '6020-2', '', 'hydraulic', 'ISO 6020-2', '{"ref_count":2}'::jsonb),
  ('iso_6022', 'ISO', '6022', '', 'general', 'ISO 6022', '{"ref_count":2}'::jsonb),
  ('iso_6194', 'ISO', '6194', '', 'general', 'ISO 6194', '{"ref_count":1}'::jsonb),
  ('iso_6336', 'ISO', '6336', '', 'general', 'ISO 6336', '{"ref_count":1}'::jsonb),
  ('iso_639_1', 'ISO', '639-1', '', 'general', 'ISO 639-1', '{"ref_count":3}'::jsonb),
  ('iso_6789', 'ISO', '6789', '', 'general', 'ISO 6789', '{"ref_count":1}'::jsonb),
  ('iso_6789_1', 'ISO', '6789-1', '', 'general', 'ISO 6789-1', '{"ref_count":1}'::jsonb),
  ('iso_6789_2', 'ISO', '6789-2', '', 'general', 'ISO 6789-2', '{"ref_count":1}'::jsonb),
  ('iso_7010', 'ISO', '7010', '', 'general', 'ISO 7010', '{"ref_count":1}'::jsonb),
  ('iso_7091', 'ISO', '7091', '', 'general', 'ISO 7091', '{"ref_count":1}'::jsonb),
  ('iso_76', 'ISO', '76', '', 'general', 'ISO 76', '{"ref_count":2}'::jsonb),
  ('iso_7870_2', 'ISO', '7870-2', '', 'general', 'ISO 7870-2', '{"ref_count":2}'::jsonb),
  ('iso_8528', 'ISO', '8528', '', 'mechanical', 'ISO 8528', '{"ref_count":1}'::jsonb),
  ('iso_8528_1', 'ISO', '8528-1', '', 'mechanical', 'ISO 8528-1', '{"ref_count":4}'::jsonb),
  ('iso_8573', 'ISO', '8573', '', 'pneumatic', 'ISO 8573', '{"ref_count":2}'::jsonb),
  ('iso_8573_1', 'ISO', '8573-1', '', 'pneumatic', 'ISO 8573-1', '{"ref_count":3}'::jsonb),
  ('iso_8601', 'ISO', '8601', '', 'general', 'ISO 8601', '{"ref_count":3}'::jsonb),
  ('iso_898', 'ISO', '898', '', 'mechanical', 'ISO 898', '{"ref_count":1}'::jsonb),
  ('iso_898_1', 'ISO', '898-1', '', 'mechanical', 'ISO 898-1', '{"ref_count":4}'::jsonb),
  ('iso_898_2', 'ISO', '898-2', '', 'mechanical', 'ISO 898-2', '{"ref_count":1}'::jsonb),
  ('iso_9613', 'ISO', '9613', '', 'acoustics', 'ISO 9613', '{"ref_count":1}'::jsonb),
  ('iso_9613_1', 'ISO', '9613-1', '', 'acoustics', 'ISO 9613-1', '{"ref_count":1}'::jsonb),
  ('iso_9613_2', 'ISO', '9613-2', '', 'acoustics', 'ISO 9613-2', '{"ref_count":3}'::jsonb),
  ('iso_9906', 'ISO', '9906', '', 'general', 'ISO 9906', '{"ref_count":1}'::jsonb),
  ('nec_2014', 'NEC', '2014', '', 'electrical', 'NEC 2014', '{"ref_count":1}'::jsonb),
  ('nec_2020', 'NEC', '2020', '', 'electrical', 'NEC 2020', '{"ref_count":2}'::jsonb),
  ('nec_2023', 'NEC', '2023', '', 'electrical', 'NEC 2023', '{"ref_count":1}'::jsonb),
  ('nec_220', 'NEC', '220', '', 'electrical', 'NEC 220', '{"ref_count":1}'::jsonb),
  ('nec_240', 'NEC', '240', '', 'electrical', 'NEC 240', '{"ref_count":1}'::jsonb),
  ('nec_250', 'NEC', '250', '', 'electrical', 'NEC 250', '{"ref_count":1}'::jsonb),
  ('nec_310', 'NEC', '310', '', 'electrical', 'NEC 310', '{"ref_count":3}'::jsonb),
  ('nec_392', 'NEC', '392', '', 'electrical', 'NEC 392', '{"ref_count":4}'::jsonb),
  ('nec_430', 'NEC', '430', '', 'electrical', 'NEC 430', '{"ref_count":1}'::jsonb),
  ('nec_630', 'NEC', '630', '', 'electrical', 'NEC 630', '{"ref_count":1}'::jsonb),
  ('nfpa_101', 'NFPA', '101', '', 'fire', 'NFPA 101', '{"ref_count":1}'::jsonb),
  ('nfpa_110', 'NFPA', '110', '', 'fire', 'NFPA 110', '{"ref_count":4}'::jsonb),
  ('nfpa_12', 'NFPA', '12', '', 'fire', 'NFPA 12', '{"ref_count":1}'::jsonb),
  ('nfpa_13', 'NFPA', '13', '', 'fire', 'NFPA 13', '{"ref_count":4}'::jsonb),
  ('nfpa_13_2022', 'NFPA', '13', '2022', 'fire', 'NFPA 13-2022', '{"ref_count":3}'::jsonb),
  ('nfpa_14', 'NFPA', '14', '', 'fire', 'NFPA 14', '{"ref_count":1}'::jsonb),
  ('nfpa_170', 'NFPA', '170', '', 'fire', 'NFPA 170', '{"ref_count":1}'::jsonb),
  ('nfpa_20', 'NFPA', '20', '', 'fire', 'NFPA 20', '{"ref_count":4}'::jsonb),
  ('nfpa_20_2022', 'NFPA', '20', '2022', 'fire', 'NFPA 20-2022', '{"ref_count":2}'::jsonb),
  ('nfpa_2001', 'NFPA', '2001', '', 'fire', 'NFPA 2001', '{"ref_count":3}'::jsonb),
  ('nfpa_2001_2022', 'NFPA', '2001', '2022', 'fire', 'NFPA 2001-2022', '{"ref_count":4}'::jsonb),
  ('nfpa_25', 'NFPA', '25', '', 'fire', 'NFPA 25', '{"ref_count":2}'::jsonb),
  ('nfpa_30', 'NFPA', '30', '', 'fire', 'NFPA 30', '{"ref_count":1}'::jsonb),
  ('nfpa_37', 'NFPA', '37', '', 'fire', 'NFPA 37', '{"ref_count":1}'::jsonb),
  ('nfpa_70', 'NFPA', '70', '', 'fire', 'NFPA 70', '{"ref_count":3}'::jsonb),
  ('nfpa_72', 'NFPA', '72', '', 'fire', 'NFPA 72', '{"ref_count":4}'::jsonb),
  ('nfpa_72_2022', 'NFPA', '72', '2022', 'fire', 'NFPA 72-2022', '{"ref_count":2}'::jsonb),
  ('nfpa_780', 'NFPA', '780', '', 'fire', 'NFPA 780', '{"ref_count":3}'::jsonb),
  ('nfpa_780_2023', 'NFPA', '780', '2023', 'fire', 'NFPA 780-2023', '{"ref_count":2}'::jsonb),
  ('nfpa_90', 'NFPA', '90', '', 'fire', 'NFPA 90', '{"ref_count":2}'::jsonb),
  ('nfpa_92', 'NFPA', '92', '', 'fire', 'NFPA 92', '{"ref_count":4}'::jsonb),
  ('nfpa_92_2021', 'NFPA', '92', '2021', 'fire', 'NFPA 92-2021', '{"ref_count":2}'::jsonb),
  ('osha_1910', 'OSHA', '1910', '', 'safety', 'OSHA 1910', '{"ref_count":2}'::jsonb),
  ('osha_1926', 'OSHA', '1926', '', 'safety', 'OSHA 1926', '{"ref_count":1}'::jsonb),
  ('osha_29', 'OSHA', '29', '', 'safety', 'OSHA 29', '{"ref_count":3}'::jsonb),
  ('osha_85', 'OSHA', '85', '', 'safety', 'OSHA 85', '{"ref_count":1}'::jsonb),
  ('saeja_1011', 'SAEJA', '1011', '', 'maintenance', 'SAEJA 1011', '{"ref_count":11}'::jsonb),
  ('saeja_1011_2009', 'SAEJA', '1011', '2009', 'maintenance', 'SAEJA 1011-2009', '{"ref_count":1}'::jsonb),
  ('saeja_1012', 'SAEJA', '1012', '', 'maintenance', 'SAEJA 1012', '{"ref_count":2}'::jsonb)
ON CONFLICT (standard_id) DO UPDATE
  SET body=EXCLUDED.body, number=EXCLUDED.number, version=EXCLUDED.version,
      discipline=EXCLUDED.discipline, title=EXCLUDED.title, contract=EXCLUDED.contract;


-- =============================================================================
-- PART 2. Tier D-f: canonical_formulas registry + 6 maintenance formulas
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.canonical_formulas (
  formula_id     text PRIMARY KEY,
  name           text NOT NULL,
  domain         text NOT NULL,
  standard_ids   text[] NOT NULL DEFAULT '{}',
  library_source text NOT NULL DEFAULT '',
  inputs         jsonb NOT NULL DEFAULT '[]'::jsonb,
  outputs        jsonb NOT NULL DEFAULT '[]'::jsonb,
  formula_text   text NOT NULL DEFAULT '',
  description    text NOT NULL DEFAULT '',
  registered_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.canonical_formulas IS
  'Tier D-f: every derivation attributed to a formula_id + standard_ids + library_source. Python calc_* fns annotated with # formula: <id>.';

CREATE INDEX IF NOT EXISTS idx_canonical_formulas_domain ON public.canonical_formulas (domain);
GRANT SELECT ON public.canonical_formulas TO anon, authenticated;
ALTER TABLE public.canonical_formulas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS canonical_formulas_read ON public.canonical_formulas;
CREATE POLICY canonical_formulas_read ON public.canonical_formulas FOR SELECT USING (true);
DROP POLICY IF EXISTS canonical_formulas_locked ON public.canonical_formulas;
CREATE POLICY canonical_formulas_locked ON public.canonical_formulas FOR ALL USING (false) WITH CHECK (false);

INSERT INTO public.canonical_formulas (formula_id, name, domain, standard_ids, library_source, inputs, outputs, formula_text, description) VALUES
('mtbf_iso_14224', 'Mean Time Between Failures', 'maintenance',
 ARRAY['iso_14224'], 'sql:get_mtbf_by_machine',
 '[{"name":"hive_id","type":"uuid"},{"name":"period_days","type":"int"}]'::jsonb,
 '[{"name":"mtbf_days","unit":"days","type":"numeric"}]'::jsonb,
 'MTBF = sum(uptime) / failure_count',
 'ISO 14224:2016 sec 9.3'),
('mttr_iso_14224', 'Mean Time To Repair', 'maintenance',
 ARRAY['iso_14224'], 'sql:get_mttr_by_machine',
 '[{"name":"hive_id","type":"uuid"},{"name":"period_days","type":"int"}]'::jsonb,
 '[{"name":"mttr_hours","unit":"hours","type":"numeric"}]'::jsonb,
 'MTTR = sum(downtime_hours) / repair_count',
 'ISO 14224:2016 sec 9.4'),
('oee_iso_22400', 'Overall Equipment Effectiveness', 'maintenance',
 ARRAY['iso_22400_2'], 'python:python-api/analytics/descriptive.py:calc_oee',
 '[{"name":"logbook_entries","type":"list"},{"name":"period_days","type":"int"}]'::jsonb,
 '[{"name":"oee_pct","unit":"percent","type":"numeric"}]'::jsonb,
 'OEE = Availability * Performance * Quality',
 'ISO 22400-2:2014'),
('availability_iso_14224', 'Availability', 'maintenance',
 ARRAY['iso_14224'], 'python:python-api/analytics/descriptive.py:calc_availability',
 '[{"name":"logbook_entries","type":"list"},{"name":"period_days","type":"int"}]'::jsonb,
 '[{"name":"availability_pct","unit":"percent","type":"numeric"}]'::jsonb,
 'Availability = MTBF / (MTBF + MTTR)',
 'ISO 14224:2016'),
('pm_compliance_smrp', 'PM Compliance', 'maintenance',
 ARRAY['saeja_1011'], 'sql:v_pm_compliance_truth',
 '[{"name":"hive_id","type":"uuid"}]'::jsonb,
 '[{"name":"compliance_pct","unit":"percent","type":"numeric"}]'::jsonb,
 'Compliance = completed_on_time / scheduled',
 'SMRP 3.5 + SAE JA 1011'),
('rcm_consequence_saeja_1011', 'RCM Failure Consequence Distribution', 'maintenance',
 ARRAY['saeja_1011'], 'python:python-api/analytics/diagnostic.py:calc_rcm_consequence',
 '[{"name":"logbook_entries","type":"list"}]'::jsonb,
 '[{"name":"distribution","type":"object"}]'::jsonb,
 'Categorize each failure into safety/production/environment/cost/quality',
 'SAE JA 1011 RCM consequence taxonomy')
ON CONFLICT (formula_id) DO UPDATE
  SET name=EXCLUDED.name, domain=EXCLUDED.domain, standard_ids=EXCLUDED.standard_ids,
      library_source=EXCLUDED.library_source, inputs=EXCLUDED.inputs, outputs=EXCLUDED.outputs,
      formula_text=EXCLUDED.formula_text, description=EXCLUDED.description;


-- =============================================================================
-- PART 3. Tier C: canonical_agent_contracts + 7 brain output schemas
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.canonical_agent_contracts (
  contract_id   text PRIMARY KEY,
  agent         text NOT NULL,
  version       int  NOT NULL DEFAULT 1,
  json_schema   jsonb NOT NULL,
  consumers     text[] NOT NULL DEFAULT '{}',
  registered_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.canonical_agent_contracts IS
  'Tier C: JSON Schema registry for AI/brain outputs. Locks the response shape so multiple consumers can rely on identical fields. Versioned per agent.';

CREATE INDEX IF NOT EXISTS idx_canonical_agent_contracts_agent ON public.canonical_agent_contracts (agent);
GRANT SELECT ON public.canonical_agent_contracts TO anon, authenticated;
ALTER TABLE public.canonical_agent_contracts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS canonical_agent_contracts_read ON public.canonical_agent_contracts;
CREATE POLICY canonical_agent_contracts_read ON public.canonical_agent_contracts FOR SELECT USING (true);
DROP POLICY IF EXISTS canonical_agent_contracts_locked ON public.canonical_agent_contracts;
CREATE POLICY canonical_agent_contracts_locked ON public.canonical_agent_contracts FOR ALL USING (false) WITH CHECK (false);

INSERT INTO public.canonical_agent_contracts (contract_id, agent, version, json_schema, consumers) VALUES
('analytics_action_plan_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["summary","priorities"],"properties":{"summary":{"type":"string"},"priorities":{"type":"array","items":{"type":"object","required":["asset","action","urgency"],"properties":{"asset":{"type":"string"},"action":{"type":"string"},"why":{"type":"string"},"urgency":{"type":"string","enum":["CRITICAL","HIGH","MEDIUM","LOW"]},"eta":{"type":"string"}}}}}}'::jsonb,
 ARRAY['analytics.html','shift-brain.html','hive.html']),
('next_failure_forecast_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["predictions"],"properties":{"predictions":{"type":"array","items":{"type":"object","required":["machine","predicted_next","risk"],"properties":{"machine":{"type":"string"},"predicted_next":{"type":"string","format":"date"},"risk":{"type":"string","enum":["HIGH","MEDIUM","LOW"]},"basis":{"type":"string"}}}}}}'::jsonb,
 ARRAY['analytics.html','predictive.html','asset-hub.html']),
('parts_stockout_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["reorder"],"properties":{"reorder":{"type":"array","items":{"type":"object","required":["part_name","urgency","suggested_order"],"properties":{"part_name":{"type":"string"},"urgency":{"type":"string","enum":["CRITICAL","HIGH","MEDIUM"]},"suggested_order":{"type":"integer"},"days_until_stockout":{"type":"integer"},"basis":{"type":"string"}}}}}}'::jsonb,
 ARRAY['analytics.html','inventory.html','parts-tracker.html']),
('health_score_v1', 'batch-risk-scoring', 1,
 '{"type":"object","required":["asset","health_score","mtbf_days"],"properties":{"asset":{"type":"string"},"health_score":{"type":"number","minimum":0,"maximum":1},"mtbf_days":{"type":["number","null"]},"risk_level":{"type":"string","enum":["low","medium","high","critical"]},"top_factors":{"type":"array","items":{"type":"object"}}}}'::jsonb,
 ARRAY['predictive.html','asset-hub.html','analytics.html','shift-brain.html']),
('anomaly_baseline_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["assets"],"properties":{"assets":{"type":"array","items":{"type":"object","required":["machine","quality_flag"],"properties":{"machine":{"type":"string"},"quality_flag":{"type":"string","enum":["OK","STALE","ANOMALY"]},"baseline_mean":{"type":"number"},"baseline_std":{"type":"number"},"deviation_sigma":{"type":"number"}}}}}}'::jsonb,
 ARRAY['analytics.html','asset-hub.html']),
('parts_spike_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["spikes"],"properties":{"spikes":{"type":"array","items":{"type":"object","required":["part_name","spike_factor"],"properties":{"part_name":{"type":"string"},"spike_factor":{"type":"number"},"recent_consumption":{"type":"integer"},"baseline_consumption":{"type":"integer"}}}}}}'::jsonb,
 ARRAY['analytics.html','inventory.html']),
('priority_ranking_v1', 'analytics-orchestrator', 1,
 '{"type":"object","required":["ranking"],"properties":{"ranking":{"type":"array","items":{"type":"object","required":["asset","priority_score"],"properties":{"asset":{"type":"string"},"priority_score":{"type":"number","minimum":0,"maximum":1},"contributing_factors":{"type":"array","items":{"type":"string"}}}}}}}'::jsonb,
 ARRAY['analytics.html','shift-brain.html','asset-hub.html'])
ON CONFLICT (contract_id) DO UPDATE
  SET agent=EXCLUDED.agent, version=EXCLUDED.version, json_schema=EXCLUDED.json_schema, consumers=EXCLUDED.consumers;


-- =============================================================================
-- PART 4. Tier B: v_project_truth + v_knowledge_truth
-- =============================================================================

CREATE OR REPLACE VIEW public.v_project_truth AS
SELECT
  p.id                          AS project_id,
  p.hive_id,
  p.name,
  p.type,
  p.status,
  p.priority,
  p.budget_pesos,
  p.start_date,
  p.target_end_date,
  p.actual_end_date,
  p.created_at,
  p.updated_at,
  (SELECT count(*) FROM public.project_items pi
     WHERE pi.project_id = p.id) AS item_count,
  (SELECT count(*) FROM public.project_items pi
     WHERE pi.project_id = p.id AND pi.status = 'done') AS items_done,
  (SELECT coalesce(sum(pi.estimated_cost_pesos), 0)::numeric FROM public.project_items pi
     WHERE pi.project_id = p.id) AS estimated_total_pesos,
  (SELECT max(ppl.logged_at) FROM public.project_progress_logs ppl
     WHERE ppl.project_id = p.id) AS last_progress_at,
  (SELECT count(*) FROM public.project_change_orders pco
     WHERE pco.project_id = p.id AND pco.status = 'approved') AS approved_change_orders,
  (SELECT count(*) FROM public.project_links pl
     WHERE pl.project_id = p.id) AS link_count
FROM public.projects p
WHERE p.status != 'archived';

COMMENT ON VIEW public.v_project_truth IS
  'Tier B canonical project rollup. Per project: counts + cost + change-order summary. Replaces ad-hoc joins of projects + project_items + project_progress_logs + project_change_orders.';
GRANT SELECT ON public.v_project_truth TO anon, authenticated;


CREATE OR REPLACE VIEW public.v_knowledge_truth AS
  SELECT 'fault'::text AS source, id, hive_id, content, embedding, created_at FROM public.fault_knowledge
  UNION ALL
  SELECT 'skill',   id, hive_id, content, embedding, created_at FROM public.skill_knowledge
  UNION ALL
  SELECT 'pm',      id, hive_id, content, embedding, created_at FROM public.pm_knowledge
  UNION ALL
  SELECT 'bom',     id, hive_id, content, embedding, created_at FROM public.bom_knowledge
  UNION ALL
  SELECT 'calc',    id, hive_id, content, embedding, created_at FROM public.calc_knowledge
  UNION ALL
  SELECT 'project', id, hive_id, content, embedding, created_at FROM public.project_knowledge;

COMMENT ON VIEW public.v_knowledge_truth IS
  'Tier B canonical RAG retrieval view. UNION ALL of all *_knowledge tables for unified pgvector semantic search.';
GRANT SELECT ON public.v_knowledge_truth TO anon, authenticated;


-- =============================================================================
-- PART 5. Tier E: v_audit_unified
-- =============================================================================

CREATE OR REPLACE VIEW public.v_audit_unified AS
  SELECT 'hive'::text AS audit_source, id, hive_id, worker_name, action, target_type, target_id, payload, created_at FROM public.hive_audit_log
  UNION ALL
  SELECT 'cmms',       id, hive_id, worker_name, action, target_type, target_id, payload, created_at FROM public.cmms_audit_log
  UNION ALL
  SELECT 'automation', id, hive_id, NULL::text, event_type, NULL::text, NULL::uuid, payload, created_at FROM public.automation_log
  UNION ALL
  SELECT 'gateway',    id, hive_id, NULL::text, route, 'edge_fn'::text, NULL::uuid, jsonb_build_object('status', status, 'latency_ms', latency_ms), created_at FROM public.gateway_audit_log;

COMMENT ON VIEW public.v_audit_unified IS
  'Tier E canonical audit trail. UNION ALL of hive_audit_log + cmms_audit_log + automation_log + gateway_audit_log.';
GRANT SELECT ON public.v_audit_unified TO anon, authenticated;


-- =============================================================================
-- PART 6. Register the new Tier B + E views in canonical_sources
-- =============================================================================

INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, description, contract, notes) VALUES
('project_truth', 'view', 'v_project_truth', 'architect', 'realtime',
 'Per project: counts + cost rollup + last-progress + change-order summary.',
 jsonb_build_object('key', jsonb_build_array('project_id'), 'hive_scoped', true,
                    'replaces_direct_reads_of', jsonb_build_array('projects','project_items','project_progress_logs','project_change_orders')),
 'Tier B. Used by project-manager + project-report + analytics-orchestrator project rollup.'),
('knowledge_truth', 'view', 'v_knowledge_truth', 'ai-engineer', 'realtime',
 'UNION ALL of all 6 *_knowledge tables for unified pgvector RAG retrieval.',
 jsonb_build_object('sources', jsonb_build_array('fault','skill','pm','bom','calc','project'), 'dim', 1536, 'hive_scoped', true),
 'Tier B. AMC + semantic-search edge fns read this single view.'),
('audit_unified', 'view', 'v_audit_unified', 'security', 'realtime',
 'UNION ALL of hive_audit_log + cmms_audit_log + automation_log + gateway_audit_log.',
 jsonb_build_object('sources', jsonb_build_array('hive','cmms','automation','gateway'), 'hive_scoped', true, 'append_only', true),
 'Tier E. audit-log.html + compliance reports read this canonical instead of 4 raw tables.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind=EXCLUDED.source_kind, source_name=EXCLUDED.source_name, owner_skill=EXCLUDED.owner_skill,
      freshness=EXCLUDED.freshness, description=EXCLUDED.description, contract=EXCLUDED.contract,
      notes=EXCLUDED.notes, registered_at=now();

COMMIT;
