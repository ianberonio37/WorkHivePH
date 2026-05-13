-- Phase 6 — Industry-Defining (long-horizon scaffolding).
--
-- The roadmap allocates 6-24 months and ~40+ sessions for Phase 6 across
-- eight sub-tracks (6A-6H) plus the Maturity-as-a-Service consulting wedge.
-- This migration ships the *data contracts* that downstream tracks build on,
-- so each sub-track becomes mechanical wiring rather than schema invention.
--
-- The ML training pipelines (6B Synthetic Twin Generator), hardware
-- integrations (6E Drone Inspection processing), financial partnerships
-- (6C Insurance Bridge underwriter agreements), and edge inference runtime
-- (6H Edge AI on phones) are explicitly out-of-scope here — those require
-- external work no migration can complete. We ship the schema today so
-- the integration day is wiring not modeling.
--
-- Builds in this migration:
--   6A. knowledge_graph_facts — triples (subject, predicate, object) with
--        confidence + source for GraphRAG. Distinct from asset_nodes/edges
--        which carry runtime hierarchy; this table carries semantic claims.
--   6E. drone_inspections — drone job records + photo set pointers + AI
--        analysis output pointer (NOT the inferences themselves — those go
--        through visual-defect-capture's existing pipeline).
--   6F. industry_standards — registry of standards the platform aligns to
--        (PSME, PEC, ASHRAE, ISO 14224, AIAG-VDA, etc.) with last_verified_at
--        + planned_review_at so the Standards Auto-Update Agent has a contract.
--   6D. hives.federated_benchmark_opted_in column — boolean opt-in for the
--        national-benchmarks data product. Default false; supervisor toggles.
--   6C. v_insurance_bridge_truth — composite underwriter view per hive.
--        Joins hive_readiness + hive_adoption_score + anomaly_signals into a
--        single row insurers can consume.
--   MaaS. consulting_engagements — Maturity-as-a-Service consulting tracker.
--        Records the engagements we run on hives to lift them up the stack.
--
-- Skills consulted:
--   architect (one fact-store per concern; insurance bridge as a view,
--     not a duplicated table; MaaS engagements as their own table)
--   data-engineer (knowledge_graph_facts uses pgvector embedding for
--     similarity-search retrieval, mirroring fault_knowledge pattern)
--   predictive-analytics (insurance view weights HRS 50% + adoption 30% +
--     anomaly load 20% — calibration left for actuarial review)
--   enterprise-compliance (federated opt-in is per-hive consent, not platform
--     default; consulting_engagements has audit trail of who-did-what-when)
--   multitenant-engineer (hive-scoped on every new table; insurance view
--     is service-role-read by default — partners get signed export, not
--     direct table access)

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 6A. knowledge_graph_facts — typed semantic claims with confidence + source
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.knowledge_graph_facts (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  -- Triple: subject_type/subject_ref / predicate / object_type/object_ref
  -- subject_type: 'asset' | 'failure_mode' | 'sop' | 'worker' | 'part' | 'lesson'
  subject_type    text        NOT NULL CHECK (subject_type ~ '^[a-z][a-z0-9_]{0,30}$'),
  subject_ref    text        NOT NULL,
  -- predicate: 'causes' | 'detects' | 'requires' | 'mitigates' | 'related_to' | ...
  predicate       text        NOT NULL CHECK (predicate ~ '^[a-z][a-z0-9_]{0,30}$'),
  object_type     text        NOT NULL CHECK (object_type ~ '^[a-z][a-z0-9_]{0,30}$'),
  object_ref      text        NOT NULL,
  -- Optional structured payload + free-text claim
  claim_text      text,
  payload         jsonb       NOT NULL DEFAULT '{}'::jsonb,
  -- Confidence + provenance
  confidence      numeric(4, 3) NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
  source_type     text        NOT NULL CHECK (source_type IN ('logbook', 'sop', 'standard', 'worker', 'ai_extraction', 'external_import')),
  source_ref      text,
  -- Embedding for similarity retrieval — vector(384) matches the platform
  -- TARGET_DIM in _shared/embedding-chain.ts (Voyage/Jina/nomic-embed-text
  -- truncated to 384). Same dimension as fault_knowledge / skill_knowledge /
  -- pm_knowledge so GraphRAG can join across corpora.
  embedding       vector(384),
  -- Lifecycle: a fact can be superseded by a newer fact (versioning)
  superseded_by   uuid        REFERENCES public.knowledge_graph_facts(id) ON DELETE SET NULL,
  active          boolean     NOT NULL DEFAULT true,
  created_by      text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.knowledge_graph_facts IS
  'Phase 6A — typed semantic-claim store with confidence + source + embedding. Triples (subject -> predicate -> object) so GraphRAG can traverse the hive''s domain knowledge. Distinct from asset_nodes (runtime hierarchy) and fault_knowledge (RAG corpus); this is the semantic ontology layer.';

CREATE INDEX IF NOT EXISTS idx_kgf_hive_active
  ON public.knowledge_graph_facts (hive_id, active, created_at DESC)
  WHERE active = true;

CREATE INDEX IF NOT EXISTS idx_kgf_subject
  ON public.knowledge_graph_facts (hive_id, subject_type, subject_ref);

CREATE INDEX IF NOT EXISTS idx_kgf_predicate
  ON public.knowledge_graph_facts (hive_id, predicate);

-- ────────────────────────────────────────────────────────────────────────────
-- 6E. drone_inspections — job + photo set + AI output pointer
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.drone_inspections (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id            uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  asset_node_id      uuid        REFERENCES public.asset_nodes(id) ON DELETE SET NULL,
  inspection_kind    text        NOT NULL CHECK (inspection_kind IN (
                       'visual_corrosion', 'thermal_hotspot', 'roof_audit',
                       'stack_audit', 'tank_audit', 'cable_tray', 'general'
                     )),
  scheduled_at       timestamptz,
  flown_at           timestamptz,
  pilot              text,
  drone_model        text,
  -- Photo set: array of Storage paths (signed URLs generated at read time)
  photo_paths        text[]      NOT NULL DEFAULT '{}',
  photo_count        integer     GENERATED ALWAYS AS (array_length(photo_paths, 1)) STORED,
  -- AI output pointer (links to fault_knowledge rows generated by the
  -- visual-defect-capture pipeline when each photo is classified)
  ai_outputs         jsonb       NOT NULL DEFAULT '[]'::jsonb,
  status             text        NOT NULL DEFAULT 'scheduled' CHECK (status IN (
                       'scheduled', 'in_flight', 'analyzed', 'reviewed', 'archived', 'cancelled'
                     )),
  reviewed_by        text,
  reviewed_at        timestamptz,
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.drone_inspections IS
  'Phase 6E — drone inspection job record. Photo paths point to Supabase Storage; AI inference happens through the existing visual-defect-capture pipeline (one defect per photo). This table holds the job-level metadata: who flew, when, what they inspected, lifecycle state.';

CREATE INDEX IF NOT EXISTS idx_drone_inspections_hive_status
  ON public.drone_inspections (hive_id, status, scheduled_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 6F. industry_standards — registry of standards the platform aligns to
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.industry_standards (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  standard_code      text        NOT NULL UNIQUE,
  family             text        NOT NULL CHECK (family IN (
                       'philippine', 'iso', 'iec', 'nfpa', 'ashrae', 'sae',
                       'aiag', 'ieee', 'astm', 'other'
                     )),
  title              text        NOT NULL,
  current_version    text,
  effective_year     smallint,
  jurisdiction       text,         -- 'PH', 'global', 'EU', ...
  last_verified_at   timestamptz NOT NULL DEFAULT now(),
  planned_review_at  date,
  source_url         text,
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.industry_standards IS
  'Phase 6F — registry of standards the platform aligns to. The Standards Auto-Update Agent reads planned_review_at and surfaces drift. Hive-agnostic (standards are global / regulatory, not per-hive).';

CREATE INDEX IF NOT EXISTS idx_industry_standards_family
  ON public.industry_standards (family, last_verified_at DESC);

-- Seed with the standards already referenced across the platform.
INSERT INTO public.industry_standards (standard_code, family, title, current_version, effective_year, jurisdiction, source_url) VALUES
  ('PSME 2024',         'philippine', 'Philippine Society of Mechanical Engineers Code',                   '2024 ed.', 2024, 'PH',     'https://www.psme.org.ph'),
  ('PEC 2017',          'philippine', 'Philippine Electrical Code Part 1',                                 '2017',     2017, 'PH',     'https://iiee.org.ph'),
  ('PSAE 2024',         'philippine', 'Philippine Society of Agricultural Engineers Code',                 '2024',     2024, 'PH',     'https://psae.org.ph'),
  ('ISO 14224:2016',    'iso',        'Petroleum, petrochemical and natural gas industries — Reliability and maintenance data', '2016', 2016, 'global', 'https://www.iso.org/standard/64076.html'),
  ('ISO 55000:2014',    'iso',        'Asset management — Overview, principles and terminology',           '2014',     2014, 'global', 'https://www.iso.org/standard/55088.html'),
  ('IEC 62305:2010',    'iec',        'Protection against lightning',                                      '2010',     2010, 'global', 'https://webstore.iec.ch/publication/6793'),
  ('NFPA 13:2025',      'nfpa',       'Standard for the Installation of Sprinkler Systems',                '2025',     2025, 'global', 'https://www.nfpa.org/codes-and-standards/all-codes-and-standards/list-of-codes-and-standards/detail?code=13'),
  ('ASHRAE 90.1:2022',  'ashrae',     'Energy Standard for Sites and Buildings Except Low-Rise Residential', '2022',  2022, 'global', 'https://www.ashrae.org'),
  ('SAE JA 1011:2009',  'sae',        'Evaluation Criteria for Reliability-Centered Maintenance Processes', '2009',    2009, 'global', 'https://www.sae.org/standards/content/ja1011_200908/'),
  ('AIAG-VDA FMEA:2019','aiag',       'AIAG & VDA FMEA Handbook',                                          '2019',     2019, 'global', 'https://www.aiag.org')
ON CONFLICT (standard_code) DO UPDATE
  SET title           = EXCLUDED.title,
      current_version = EXCLUDED.current_version,
      effective_year  = EXCLUDED.effective_year,
      jurisdiction    = EXCLUDED.jurisdiction,
      source_url      = EXCLUDED.source_url;

-- ────────────────────────────────────────────────────────────────────────────
-- 6D. hives.federated_benchmark_opted_in — per-hive consent column
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.hives
  ADD COLUMN IF NOT EXISTS federated_benchmark_opted_in boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS federated_opt_in_at          timestamptz,
  ADD COLUMN IF NOT EXISTS federated_opt_in_by          text;

COMMENT ON COLUMN public.hives.federated_benchmark_opted_in IS
  'Phase 6D — per-hive consent to contribute anonymised metrics to the national PH Industry Benchmarks data product. Default false; supervisor toggles.';

-- ────────────────────────────────────────────────────────────────────────────
-- 6C. v_insurance_bridge_truth — composite underwriter view per hive
-- ────────────────────────────────────────────────────────────────────────────
-- Combines HRS (maturity), adoption_risk (slide signal), and anomaly load
-- (active critical/warning signals count) into one number an insurer can
-- consume. Weighting is provisional and explicitly flagged for actuarial
-- review before any partner integration.

CREATE OR REPLACE VIEW public.v_insurance_bridge_truth AS
  SELECT
    h.id                                   AS hive_id,
    h.name                                 AS hive_name,
    hr.composite_score                     AS readiness_score,
    hr.current_stair                       AS maturity_stair,
    has.risk_score                         AS adoption_risk_score,
    has.risk_tier                          AS adoption_risk_tier,
    (SELECT count(*)
       FROM public.anomaly_signals an
       WHERE an.hive_id = h.id
         AND an.status = 'active'
         AND an.severity IN ('warning', 'critical'))     AS active_warning_count,
    (SELECT count(*)
       FROM public.anomaly_signals an
       WHERE an.hive_id = h.id
         AND an.status = 'active'
         AND an.severity = 'critical')                   AS active_critical_count,
    -- Composite underwriter score 0..100; higher = lower risk.
    -- HRS 50% + (100 - adoption_risk) 30% + (100 - clamped anomaly load) 20%.
    GREATEST(0, LEAST(100, (
        (COALESCE(hr.composite_score, 0)               * 50)
      + (100 - COALESCE(has.risk_score, 50))            * 30
      + (100 - LEAST(100, (SELECT count(*) * 20
                              FROM public.anomaly_signals an
                              WHERE an.hive_id = h.id
                                AND an.status = 'active'
                                AND an.severity IN ('warning', 'critical')))) * 20
    ) / 100))::smallint                                  AS underwriter_score,
    h.federated_benchmark_opted_in                       AS federated_opt_in,
    'v1-provisional'                                     AS model_version,
    now()                                                AS computed_at
  FROM public.hives h
  LEFT JOIN LATERAL (
    SELECT composite_score, current_stair
      FROM public.hive_readiness
      WHERE hive_id = h.id
      ORDER BY snapshot_date DESC
      LIMIT 1
  ) hr ON true
  LEFT JOIN LATERAL (
    SELECT risk_score, risk_tier
      FROM public.hive_adoption_score
      WHERE hive_id = h.id
      ORDER BY snapshot_date DESC
      LIMIT 1
  ) has ON true;

COMMENT ON VIEW public.v_insurance_bridge_truth IS
  'Phase 6C — composite underwriter view per hive. Joins HRS + adoption risk + anomaly load. Weighting is provisional (v1) and explicitly flagged for actuarial review before any partner integration. Partners read via signed export, not direct table access.';

GRANT SELECT ON public.v_insurance_bridge_truth TO authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- MaaS — consulting_engagements (Maturity-as-a-Service tracker)
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.consulting_engagements (
  id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id            uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  engagement_kind    text        NOT NULL CHECK (engagement_kind IN (
                       'readiness_assessment', 'stair_2_lift', 'stair_3_lift',
                       'pdpa_prep', 'soc2_prep', 'iso27001_prep', 'sso_onboarding',
                       'rcm_workshop', 'general'
                     )),
  starting_stair     smallint    CHECK (starting_stair IS NULL OR starting_stair BETWEEN 0 AND 4),
  target_stair       smallint    CHECK (target_stair IS NULL OR target_stair BETWEEN 0 AND 4),
  target_days        smallint,
  status             text        NOT NULL DEFAULT 'scheduled' CHECK (status IN (
                       'scheduled', 'in_progress', 'paused', 'completed', 'cancelled'
                     )),
  consultant_name    text,
  contract_value_php numeric(12, 2),
  started_at         timestamptz,
  completed_at       timestamptz,
  outcome_summary    text,
  evidence           jsonb       NOT NULL DEFAULT '{}'::jsonb,
  created_at         timestamptz NOT NULL DEFAULT now(),
  created_by         text
);

COMMENT ON TABLE public.consulting_engagements IS
  'Maturity-as-a-Service tracker (Phase 6 reframe addition). Records the consulting engagements we run on hives to lift them up the stack. Productisation surface that turns the methodology behind WorkHive''s readiness layer into a paid offering — "we will get you to Stair 3 in 90 days."';

CREATE INDEX IF NOT EXISTS idx_consulting_hive_status
  ON public.consulting_engagements (hive_id, status, started_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- RLS — hive-membership read; service-role writes only
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.knowledge_graph_facts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS kgf_read ON public.knowledge_graph_facts;
CREATE POLICY kgf_read ON public.knowledge_graph_facts FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );
DROP POLICY IF EXISTS kgf_insert_locked ON public.knowledge_graph_facts;
CREATE POLICY kgf_insert_locked ON public.knowledge_graph_facts FOR INSERT WITH CHECK (false);
DROP POLICY IF EXISTS kgf_update_locked ON public.knowledge_graph_facts;
CREATE POLICY kgf_update_locked ON public.knowledge_graph_facts FOR UPDATE USING (false) WITH CHECK (false);
DROP POLICY IF EXISTS kgf_delete_locked ON public.knowledge_graph_facts;
CREATE POLICY kgf_delete_locked ON public.knowledge_graph_facts FOR DELETE USING (false);
GRANT SELECT ON public.knowledge_graph_facts TO anon, authenticated;

ALTER TABLE public.drone_inspections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS drone_read ON public.drone_inspections;
CREATE POLICY drone_read ON public.drone_inspections FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );
DROP POLICY IF EXISTS drone_insert_locked ON public.drone_inspections;
CREATE POLICY drone_insert_locked ON public.drone_inspections FOR INSERT WITH CHECK (false);
DROP POLICY IF EXISTS drone_update_supervisor ON public.drone_inspections;
CREATE POLICY drone_update_supervisor ON public.drone_inspections FOR UPDATE
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = drone_inspections.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  )
  WITH CHECK (true);
GRANT SELECT, UPDATE ON public.drone_inspections TO anon, authenticated;

-- industry_standards: read-anyone (it's a platform-level catalog).
ALTER TABLE public.industry_standards ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS std_read ON public.industry_standards;
CREATE POLICY std_read ON public.industry_standards FOR SELECT USING (true);
DROP POLICY IF EXISTS std_write_locked ON public.industry_standards;
CREATE POLICY std_write_locked ON public.industry_standards FOR INSERT WITH CHECK (false);
GRANT SELECT ON public.industry_standards TO anon, authenticated;

ALTER TABLE public.consulting_engagements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS consult_read ON public.consulting_engagements;
CREATE POLICY consult_read ON public.consulting_engagements FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = consulting_engagements.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  );
DROP POLICY IF EXISTS consult_insert_locked ON public.consulting_engagements;
CREATE POLICY consult_insert_locked ON public.consulting_engagements FOR INSERT WITH CHECK (false);
GRANT SELECT ON public.consulting_engagements TO anon, authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- Realtime publication for live operator dashboards
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.knowledge_graph_facts REPLICA IDENTITY FULL;
ALTER PUBLICATION supabase_realtime ADD TABLE public.knowledge_graph_facts;

ALTER TABLE public.drone_inspections REPLICA IDENTITY FULL;
ALTER PUBLICATION supabase_realtime ADD TABLE public.drone_inspections;

-- ────────────────────────────────────────────────────────────────────────────
-- Canonical sources registration
-- ────────────────────────────────────────────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('knowledge_graph_facts_table', 'table', 'knowledge_graph_facts',
   'knowledge-manager', 'live',
   'Phase 6A — typed semantic-claim store (subject/predicate/object + confidence + source + embedding). Distinct from asset_nodes/edges (runtime hierarchy) and fault_knowledge (RAG corpus). GraphRAG traversal primitive.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true,
                      'embedding_dim', 384,
                      'subject_types', jsonb_build_array('asset', 'failure_mode', 'sop', 'worker', 'part', 'lesson'),
                      'phase_6_built', true),
   'Phase 6A of STRATEGIC_ROADMAP.'),

  ('drone_inspections_table', 'table', 'drone_inspections',
   'maintenance-expert', 'on-demand',
   'Phase 6E — drone inspection job records. Photo set + AI output pointer + lifecycle state. Inference itself runs through visual-defect-capture; this table holds metadata.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true,
                      'lifecycle', jsonb_build_array('scheduled', 'in_flight', 'analyzed', 'reviewed', 'archived', 'cancelled'),
                      'phase_6_built', true),
   'Phase 6E of STRATEGIC_ROADMAP.'),

  ('industry_standards_table', 'table', 'industry_standards',
   'standards-validator', 'monthly',
   'Phase 6F — registry of standards the platform aligns to. Standards Auto-Update Agent reads planned_review_at and surfaces drift. Hive-agnostic; platform-level.',
   jsonb_build_object('key', jsonb_build_array('standard_code'), 'hive_scoped', false,
                      'families', jsonb_build_array('philippine', 'iso', 'iec', 'nfpa', 'ashrae', 'sae', 'aiag', 'ieee', 'astm', 'other'),
                      'phase_6_built', true),
   'Phase 6F of STRATEGIC_ROADMAP.'),

  ('hives_federated_opt_in', 'column', 'hives.federated_benchmark_opted_in',
   'enterprise-compliance', 'on-demand',
   'Phase 6D — per-hive consent column for the national PH Industry Benchmarks data product. Default false; supervisor toggles; opt-in is logged with timestamp + actor.',
   jsonb_build_object('type', 'boolean', 'default', false, 'consent_audit', true,
                      'phase_6_built', true),
   'Phase 6D of STRATEGIC_ROADMAP.'),

  ('insurance_bridge', 'view', 'v_insurance_bridge_truth',
   'predictive-analytics', 'live',
   'Phase 6C — composite underwriter view per hive. HRS 50% + (100 - adoption_risk) 30% + (100 - clamped anomaly load) 20%. Weighting is provisional v1 and explicitly flagged for actuarial review before any partner integration.',
   jsonb_build_object('key', jsonb_build_array('hive_id'), 'higher_is_better', true,
                      'weighting', jsonb_build_object('readiness', 50, 'adoption', 30, 'anomaly', 20),
                      'calibration_status', 'provisional_pending_actuarial_review',
                      'phase_6_built', true),
   'Phase 6C of STRATEGIC_ROADMAP.'),

  ('consulting_engagements_table', 'table', 'consulting_engagements',
   'enterprise-compliance', 'on-demand',
   'Maturity-as-a-Service tracker (Phase 6 reframe addition). Productisation surface for the WorkHive methodology — "we will get you to Stair 3 in 90 days."',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true,
                      'engagement_kinds', jsonb_build_array('readiness_assessment', 'stair_2_lift', 'stair_3_lift', 'pdpa_prep', 'soc2_prep', 'iso27001_prep', 'sso_onboarding', 'rcm_workshop', 'general'),
                      'phase_6_built', true),
   'Phase 6 MaaS reframe addition.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind   = EXCLUDED.source_kind,
      source_name   = EXCLUDED.source_name,
      owner_skill   = EXCLUDED.owner_skill,
      freshness     = EXCLUDED.freshness,
      description   = EXCLUDED.description,
      contract      = EXCLUDED.contract,
      notes         = EXCLUDED.notes,
      registered_at = now();

COMMIT;
