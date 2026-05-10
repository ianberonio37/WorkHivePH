-- Reliability Engineering Workbench Phase R.1: foundation schema.
--
-- Four tables backing the per-asset Reliability tab on Asset Hub (Path A
-- from RELIABILITY_WORKBENCH_PLAN.md). Every table is keyed by canonical
-- asset_id (from asset_nodes via the v_asset_truth view) and registered in
-- canonical_sources after the views land.
--
--   rcm_fmea_modes     -- one row per failure mode per asset (S/O/D + RPN)
--   rcm_strategies     -- one row per FMEA mode mapped to the JA1011 decision
--   weibull_fits       -- one row per Weibull MLE fit (asset + failure mode)
--   pf_intervals       -- one row per P-F calc (asset + condition param)
--
-- Plus three canonical views (v_fmea_truth, v_rcm_truth, v_weibull_truth)
-- registered in canonical_sources so AI agents query through one shape.
--
-- Skills consulted: maintenance-expert (RCM JA1011, FMEA AIAG-VDA 2019 S/O/D
-- rubric, ISO 14224 hierarchy reuse), predictive-analytics (Weibull beta/eta
-- contract, P-F / 2 default rule), architect (canonical sources + view +
-- RLS pattern from Phase A), data-engineer (composite indexes at creation
-- time, generated columns for RPN), multitenant-engineer (hive-membership-
-- join policy), security (CHECK constraints on score ranges, supervisor
-- approval gate via approved_at).

BEGIN;

-- ─── 1. FMEA matrix rows ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.rcm_fmea_modes (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id            uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  asset_id           uuid NOT NULL REFERENCES public.asset_nodes(id) ON DELETE CASCADE,
  function_text      text NOT NULL,
  failure_mode       text NOT NULL,
  effect_text        text,
  cause_text         text,
  severity           smallint CHECK (severity   BETWEEN 1 AND 10),
  occurrence         smallint CHECK (occurrence BETWEEN 1 AND 10),
  detection          smallint CHECK (detection  BETWEEN 1 AND 10),
  rpn                smallint GENERATED ALWAYS AS (
                       COALESCE(severity, 0) * COALESCE(occurrence, 0) * COALESCE(detection, 0)
                     ) STORED,
  consequence_class  text CHECK (consequence_class IN
                       ('safety','production','environment','cost','quality') OR consequence_class IS NULL),
  source             text NOT NULL DEFAULT 'manual'
                     CHECK (source IN ('manual','ai_logbook','ai_template','imported')),
  ai_confidence      numeric CHECK (ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)),
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  created_by         text,
  approved_by        text,
  approved_at        timestamptz,
  CONSTRAINT rcm_fmea_modes_unique_per_function UNIQUE (hive_id, asset_id, function_text, failure_mode)
);

COMMENT ON TABLE public.rcm_fmea_modes IS
  'FMEA matrix rows per asset. RPN = severity * occurrence * detection (generated column). source = manual / ai_logbook / ai_template / imported. Engineer must approve (set approved_at) before RPN counts in dashboards.';

CREATE INDEX IF NOT EXISTS idx_fmea_modes_hive_asset
  ON public.rcm_fmea_modes (hive_id, asset_id);
CREATE INDEX IF NOT EXISTS idx_fmea_modes_rpn
  ON public.rcm_fmea_modes (hive_id, rpn DESC);
CREATE INDEX IF NOT EXISTS idx_fmea_modes_source
  ON public.rcm_fmea_modes (hive_id, source);

-- ─── 2. RCM strategies (JA1011 decision per failure mode) ─────────────────────

CREATE TABLE IF NOT EXISTS public.rcm_strategies (
  id                              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id                         uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  fmea_mode_id                    uuid NOT NULL REFERENCES public.rcm_fmea_modes(id) ON DELETE CASCADE,
  decision                        text NOT NULL CHECK (decision IN (
                                    'run_to_failure',
                                    'scheduled_on_condition',
                                    'scheduled_restoration',
                                    'scheduled_discard',
                                    'failure_finding',
                                    'redesign_required'
                                  )),
  task_text                       text,
  interval_days                   integer CHECK (interval_days IS NULL OR interval_days > 0),
  rationale                       text,
  weibull_fit_id                  uuid,
  pf_interval_id                  uuid,
  written_to_pm_scope_item_id     uuid REFERENCES public.pm_scope_items(id) ON DELETE SET NULL,
  source                          text NOT NULL DEFAULT 'manual'
                                  CHECK (source IN ('manual','ai_suggested','imported')),
  ai_confidence                   numeric CHECK (ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)),
  created_at                      timestamptz NOT NULL DEFAULT now(),
  updated_at                      timestamptz NOT NULL DEFAULT now(),
  approved_by                     text,
  approved_at                     timestamptz
);

COMMENT ON TABLE public.rcm_strategies IS
  'RCM strategy per FMEA failure mode per SAE JA1011 decision tree. written_to_pm_scope_item_id links the recommended task back to the PM Scheduler; null until the engineer applies it.';

CREATE INDEX IF NOT EXISTS idx_rcm_strategies_hive
  ON public.rcm_strategies (hive_id, decision);
CREATE INDEX IF NOT EXISTS idx_rcm_strategies_fmea
  ON public.rcm_strategies (fmea_mode_id);

-- ─── 3. Weibull fits ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.weibull_fits (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id             uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  asset_id            uuid NOT NULL REFERENCES public.asset_nodes(id) ON DELETE CASCADE,
  fmea_mode_id        uuid REFERENCES public.rcm_fmea_modes(id) ON DELETE SET NULL,
  beta                numeric,
  eta_days            numeric,
  failure_pattern     text CHECK (failure_pattern IN ('infant','random','wearout','insufficient_data')),
  n_failures          integer NOT NULL DEFAULT 0,
  n_censored          integer NOT NULL DEFAULT 0,
  fit_method          text NOT NULL DEFAULT 'mle_lifelines'
                      CHECK (fit_method IN ('mle_lifelines','mle_newton','lsq','mrr')),
  log_likelihood      numeric,
  source_window_days  integer NOT NULL DEFAULT 365,
  generated_at        timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.weibull_fits IS
  'Weibull MLE fit per asset (and optionally per failure mode). beta < 1 = infant mortality; beta = 1 = random; beta > 1 = wear-out. Default fit_method is mle_lifelines (Python Analytics API endpoint /reliability/weibull wrapping lifelines.WeibullFitter).';

CREATE INDEX IF NOT EXISTS idx_weibull_fits_hive_asset
  ON public.weibull_fits (hive_id, asset_id, generated_at DESC);

-- ─── 4. P-F intervals ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.pf_intervals (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id                     uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  asset_id                    uuid NOT NULL REFERENCES public.asset_nodes(id) ON DELETE CASCADE,
  fmea_mode_id                uuid REFERENCES public.rcm_fmea_modes(id) ON DELETE SET NULL,
  parameter                   text NOT NULL,
  p_threshold                 numeric NOT NULL,
  f_threshold                 numeric NOT NULL,
  pf_days                     numeric NOT NULL CHECK (pf_days > 0),
  recommended_interval_days   integer NOT NULL CHECK (recommended_interval_days > 0),
  basis                       text NOT NULL DEFAULT 'P-F/2',
  generated_at                timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.pf_intervals IS
  'P-F interval per asset per condition-monitoring parameter (vibration_mm_s, bearing_temp_c, oil_debris_ppm, etc.). recommended_interval_days defaults to pf_days / 2 (the standard rule); P-F / 3 used for safety-critical assets.';

CREATE INDEX IF NOT EXISTS idx_pf_intervals_hive_asset
  ON public.pf_intervals (hive_id, asset_id, generated_at DESC);

-- ─── 5. updated_at triggers ──────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.tg_rcm_touch_updated()
RETURNS trigger AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rcm_fmea_modes_touch_updated  ON public.rcm_fmea_modes;
CREATE TRIGGER rcm_fmea_modes_touch_updated
  BEFORE UPDATE ON public.rcm_fmea_modes
  FOR EACH ROW EXECUTE FUNCTION public.tg_rcm_touch_updated();

DROP TRIGGER IF EXISTS rcm_strategies_touch_updated ON public.rcm_strategies;
CREATE TRIGGER rcm_strategies_touch_updated
  BEFORE UPDATE ON public.rcm_strategies
  FOR EACH ROW EXECUTE FUNCTION public.tg_rcm_touch_updated();

-- ─── 6. Grants ───────────────────────────────────────────────────────────────

GRANT SELECT, INSERT, UPDATE, DELETE ON public.rcm_fmea_modes  TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.rcm_strategies  TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.weibull_fits    TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.pf_intervals    TO anon, authenticated;

-- ─── 7. RLS ──────────────────────────────────────────────────────────────────

ALTER TABLE public.rcm_fmea_modes  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rcm_strategies  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.weibull_fits    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pf_intervals    ENABLE ROW LEVEL SECURITY;

-- Read: any active hive member.

DROP POLICY IF EXISTS rcm_fmea_modes_read ON public.rcm_fmea_modes;
CREATE POLICY rcm_fmea_modes_read ON public.rcm_fmea_modes FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS rcm_strategies_read ON public.rcm_strategies;
CREATE POLICY rcm_strategies_read ON public.rcm_strategies FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS weibull_fits_read ON public.weibull_fits;
CREATE POLICY weibull_fits_read ON public.weibull_fits FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS pf_intervals_read ON public.pf_intervals;
CREATE POLICY pf_intervals_read ON public.pf_intervals FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- Write: members can insert / update / delete in their own hive (engineer
-- approval gate is enforced via approved_at column, not by RLS, so an
-- unapproved row still belongs to the hive but does not count in dashboards).

DROP POLICY IF EXISTS rcm_fmea_modes_write ON public.rcm_fmea_modes;
CREATE POLICY rcm_fmea_modes_write ON public.rcm_fmea_modes FOR ALL
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS rcm_strategies_write ON public.rcm_strategies;
CREATE POLICY rcm_strategies_write ON public.rcm_strategies FOR ALL
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- weibull_fits and pf_intervals are written by the Python-API-backed edge
-- functions running as service_role. Authenticated users get read-only via
-- the SELECT policies above; manual writes are locked to keep the math
-- output trustworthy.

DROP POLICY IF EXISTS weibull_fits_write ON public.weibull_fits;
CREATE POLICY weibull_fits_write ON public.weibull_fits FOR ALL
  USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS pf_intervals_write ON public.pf_intervals;
CREATE POLICY pf_intervals_write ON public.pf_intervals FOR ALL
  USING (false) WITH CHECK (false);

-- ─── 8. Realtime publication ─────────────────────────────────────────────────

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_publication_tables WHERE pubname = 'supabase_realtime' AND tablename = 'rcm_fmea_modes') THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.rcm_fmea_modes';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_publication_tables WHERE pubname = 'supabase_realtime' AND tablename = 'rcm_strategies') THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.rcm_strategies';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_publication_tables WHERE pubname = 'supabase_realtime' AND tablename = 'weibull_fits') THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.weibull_fits';
  END IF;
END
$$;

-- REPLICA IDENTITY FULL on the row-volume-low tables so DELETE filters by
-- hive_id work cleanly (per realtime-engineer skill).
ALTER TABLE public.rcm_fmea_modes  REPLICA IDENTITY FULL;
ALTER TABLE public.rcm_strategies  REPLICA IDENTITY FULL;
ALTER TABLE public.weibull_fits    REPLICA IDENTITY FULL;

-- ─── 9. Canonical views ──────────────────────────────────────────────────────

CREATE OR REPLACE VIEW public.v_fmea_truth AS
SELECT
  m.id              AS fmea_mode_id,
  m.hive_id,
  m.asset_id,
  n.tag             AS asset_tag,
  n.name            AS asset_name,
  n.iso_class,
  n.criticality     AS asset_criticality,
  m.function_text,
  m.failure_mode,
  m.effect_text,
  m.cause_text,
  m.severity, m.occurrence, m.detection, m.rpn,
  m.consequence_class,
  m.source, m.ai_confidence,
  m.created_at, m.updated_at, m.approved_at, m.approved_by
FROM public.rcm_fmea_modes m
LEFT JOIN public.asset_nodes n ON n.id = m.asset_id
WHERE m.approved_at IS NOT NULL;

CREATE OR REPLACE VIEW public.v_rcm_truth AS
SELECT
  s.id              AS strategy_id,
  s.hive_id,
  s.fmea_mode_id,
  m.asset_id,
  s.decision,
  s.task_text,
  s.interval_days,
  s.rationale,
  s.weibull_fit_id,
  s.pf_interval_id,
  s.written_to_pm_scope_item_id,
  s.source, s.ai_confidence,
  s.created_at, s.updated_at, s.approved_at
FROM public.rcm_strategies s
JOIN public.rcm_fmea_modes m ON m.id = s.fmea_mode_id
WHERE s.approved_at IS NOT NULL;

CREATE OR REPLACE VIEW public.v_weibull_truth AS
SELECT DISTINCT ON (hive_id, asset_id, COALESCE(fmea_mode_id::text, '_'))
  id AS fit_id, hive_id, asset_id, fmea_mode_id,
  beta, eta_days, failure_pattern,
  n_failures, n_censored, fit_method, log_likelihood,
  source_window_days, generated_at
FROM public.weibull_fits
ORDER BY hive_id, asset_id, COALESCE(fmea_mode_id::text, '_'), generated_at DESC;

GRANT SELECT ON public.v_fmea_truth     TO anon, authenticated;
GRANT SELECT ON public.v_rcm_truth      TO anon, authenticated;
GRANT SELECT ON public.v_weibull_truth  TO anon, authenticated;

COMMENT ON VIEW public.v_fmea_truth IS
  'Canonical FMEA: only approved rows, joined to asset_nodes for tag/name/iso_class. Registered in canonical_sources as fmea_truth.';
COMMENT ON VIEW public.v_rcm_truth IS
  'Canonical RCM strategy: only approved rows, joined to FMEA mode for asset_id resolution. Registered in canonical_sources as rcm_truth.';
COMMENT ON VIEW public.v_weibull_truth IS
  'Canonical Weibull fit: latest fit per (hive, asset, fmea_mode) via DISTINCT ON. Registered in canonical_sources as weibull_truth.';

-- ─── 10. Register the three new truths ───────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('fmea_truth', 'view', 'v_fmea_truth', 'maintenance-expert', 'realtime',
   'Canonical FMEA matrix per asset. Filters to approved rows only; joins asset_nodes for tag/name/iso_class. Source of truth for the Reliability tab on Asset Hub, the print-ready Reliability Report, and AI agents asking about failure modes.',
   jsonb_build_object(
     'key', jsonb_build_array('fmea_mode_id'),
     'hive_scoped', true,
     'approved_only', true,
     'rpn_range', jsonb_build_array(1, 1000),
     'source_values', jsonb_build_array('manual','ai_logbook','ai_template','imported'),
     'standards', jsonb_build_array('SAE J1739','MIL-STD-1629A','AIAG-VDA 2019','ISO 14224')
   ),
   'Phase R.1 contract. Engineer approval (approved_at) gates the view, so unapproved rows do not count in dashboards. AI-generated rows must still be approved before RPN counts.'),

  ('rcm_truth', 'view', 'v_rcm_truth', 'maintenance-expert', 'realtime',
   'Canonical RCM strategy per FMEA failure mode per SAE JA1011 decision tree. Output: one of run_to_failure / scheduled_on_condition / scheduled_restoration / scheduled_discard / failure_finding / redesign_required. written_to_pm_scope_item_id links the recommended task back to PM Scheduler.',
   jsonb_build_object(
     'key', jsonb_build_array('strategy_id'),
     'hive_scoped', true,
     'approved_only', true,
     'decisions', jsonb_build_array('run_to_failure','scheduled_on_condition','scheduled_restoration','scheduled_discard','failure_finding','redesign_required'),
     'standards', jsonb_build_array('SAE JA1011','SAE JA1012','ATA MSG-3')
   ),
   'Phase R.1 contract. Strategy decision must reference one of the six JA1011-compliant outputs. Linked PM scope item (written_to_pm_scope_item_id) is null until the engineer applies via PM Scheduler.'),

  ('weibull_truth', 'view', 'v_weibull_truth', 'predictive-analytics', 'weekly_recompute',
   'Latest Weibull MLE fit per (hive, asset, failure mode) via DISTINCT ON. Default fit_method is mle_lifelines (Python Analytics API endpoint /reliability/weibull wrapping lifelines.WeibullFitter for native censored-data support).',
   jsonb_build_object(
     'key', jsonb_build_array('fit_id'),
     'hive_scoped', true,
     'method_default', 'mle_lifelines',
     'pattern_classification', jsonb_build_object(
       'beta_lt_1', 'infant',
       'beta_eq_1', 'random',
       'beta_gt_1', 'wearout'
     ),
     'standards', jsonb_build_array('IEC 61649','MIL-HDBK-189C')
   ),
   'Phase R.1 contract. Weibull recompute frequency is weekly to keep AI cost low; engineers can trigger an on-demand refit from the Weibull tab.')
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
