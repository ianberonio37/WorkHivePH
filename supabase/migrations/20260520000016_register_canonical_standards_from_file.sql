-- Sync canonical_standards DB with canonical/standards.json file.
--
-- WHY: run_tests.py s_canonical_tier_s_drift (Data Tests gate) caught 19
-- standards declared in canonical/standards.json that were NOT yet in the
-- canonical_standards DB table. The file is the source-of-truth for
-- platform-curated Tier-S standards; the DB carries the legacy bulk import
-- from migration 20260512000013 + my IEC 60812 followup. They need to agree
-- so AI agents that JOIN against canonical_standards always resolve
-- citations the formula registry references.
--
-- First: extend the body CHECK constraint to admit bodies the original
-- enum missed (API / NEMA / PMI for industry bodies; ACADEMIC for classical
-- equations like Darcy-Weisbach 1857, Weibull 1951, Z-score; WORKHIVE for
-- platform-internal pseudo-standards like Adoption Risk, Skill Tier Model).
-- This is a strict superset of the original enum — no existing row breaks.
--
-- Second: INSERT 19 missing rows ON CONFLICT DO NOTHING so re-runs after a
-- supabase db reset are idempotent.

BEGIN;

ALTER TABLE public.canonical_standards
  DROP CONSTRAINT IF EXISTS canonical_standards_body_check;

ALTER TABLE public.canonical_standards
  ADD CONSTRAINT canonical_standards_body_check
  CHECK (body IN (
    'ISO','IEC','SAE','ASHRAE','NFPA','NEC','IEEE','ANSI','ASTM',
    'IESNA','OSHA','SMRP','SAEJA','ASME',
    -- Added 2026-05-20 for file<->DB sync:
    'API','NEMA','PMI','ACADEMIC','WORKHIVE'
  ));

INSERT INTO public.canonical_standards (standard_id, body, number, version, discipline, title, contract) VALUES
  ('iso_22400_2_2014',                  'ISO',       '22400-2',          '2014', 'manufacturing',     'ISO 22400-2:2014',                  '{"short_name": "ISO 22400-2:2014", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('nakajima_tpm_1988',                 'ACADEMIC',  'tpm',              '1988', 'manufacturing',     'Nakajima TPM (1988)',               '{"short_name": "Nakajima TPM (1988)", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('sae_ja1011',                        'SAEJA',     '1011',             '2009', 'reliability',       'SAE JA1011',                        '{"short_name": "SAE JA1011", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('smrp_metrics_v5',                   'SMRP',      'metrics',          'v5',   'reliability',       'SMRP Best Practices v5.0',          '{"short_name": "SMRP Best Practices v5.0", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('iec_60812_2018',                    'IEC',       '60812',            '2018', 'reliability',       'IEC 60812:2018',                    '{"short_name": "IEC 60812:2018", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('darcy_weisbach',                    'ACADEMIC',  'darcy-weisbach',   '1857', 'mechanical',        'Darcy-Weisbach',                    '{"short_name": "Darcy-Weisbach", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('api_610_2018',                      'API',       '610',              '2018', 'mechanical',        'API 610:2018',                      '{"short_name": "API 610:2018", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('nema_mg_1_2021',                    'NEMA',      'MG-1',             '2021', 'electrical',        'NEMA MG 1:2021',                    '{"short_name": "NEMA MG 1:2021", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('ashrae_90_1_2022',                  'ASHRAE',    '90.1',             '2022', 'hvac',              'ASHRAE 90.1:2022',                  '{"short_name": "ASHRAE 90.1:2022", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('asme_b31_3_2022',                   'ASME',      'B31.3',            '2022', 'mechanical',        'ASME B31.3:2022',                   '{"short_name": "ASME B31.3:2022", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('pmbok_evm',                         'PMI',       'PMBOK',            '7',    'project_management', 'PMBOK 7th',                         '{"short_name": "PMBOK 7th", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('z_score_anomaly',                   'ACADEMIC',  'z-score',          '1900', 'reliability',       'Z-Score Anomaly',                   '{"short_name": "Z-Score Anomaly", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('weibull_pf_analysis',               'ACADEMIC',  'weibull',          '1951', 'reliability',       'Weibull Reliability Analysis',      '{"short_name": "Weibull Reliability Analysis", "platform_internal": false, "workhive_seed": true}'::jsonb),
  ('platform_adoption_observability',   'WORKHIVE',  'adoption-risk',    'v1',   'platform_internal', 'WorkHive Adoption Risk',            '{"short_name": "WorkHive Adoption Risk", "platform_internal": true, "workhive_seed": true}'::jsonb),
  ('platform_marketplace_seller_score', 'WORKHIVE',  'seller-score',     'v1',   'platform_internal', 'WorkHive Marketplace Seller Score', '{"short_name": "WorkHive Marketplace Seller Score", "platform_internal": true, "workhive_seed": true}'::jsonb),
  ('platform_health_score',             'WORKHIVE',  'platform-health',  'v1',   'platform_internal', 'WorkHive Platform Health',          '{"short_name": "WorkHive Platform Health", "platform_internal": true, "workhive_seed": true}'::jsonb),
  ('platform_skill_tier_model',         'WORKHIVE',  'skill-tier',       'v1',   'platform_internal', 'WorkHive Skill Tier Model',         '{"short_name": "WorkHive Skill Tier Model", "platform_internal": true, "workhive_seed": true}'::jsonb),
  ('platform_achievement_tiers',        'WORKHIVE',  'achievement-tier', 'v1',   'platform_internal', 'WorkHive Achievement Tier Model',   '{"short_name": "WorkHive Achievement Tier Model", "platform_internal": true, "workhive_seed": true}'::jsonb),
  ('platform_maturity_stair',           'WORKHIVE',  'stair-model',      'v1',   'platform_internal', 'WorkHive Stair Model',              '{"short_name": "WorkHive Stair Model", "platform_internal": true, "workhive_seed": true}'::jsonb)
ON CONFLICT (standard_id) DO NOTHING;

COMMIT;
