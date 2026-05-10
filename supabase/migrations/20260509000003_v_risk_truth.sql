-- Canonical Sources Phase A.3: v_risk_truth view.
--
-- Single read path for asset risk scores. Latest score per (hive_id, asset_name)
-- using DISTINCT ON, with the canonical asset_id (uuid) joined in from
-- asset_nodes when name resolution succeeds. Consumers stop doing their own
-- dedup-to-latest math; the view does it once.
--
-- The Phase 5a model rebuild (richer composite scoring with structured
-- top_factors and asset-class normalisation) writes through asset_risk_scores
-- as today; v_risk_truth surfaces whatever the writer produces. The view
-- contract is independent of the model implementation.
--
-- Note on hive_id NULL: predictive.html supports solo mode (no hive). The
-- view exposes those rows too because asset_risk_scores.hive_id is nullable
-- and consumers filter explicitly. RLS inheritance from asset_risk_scores
-- handles the auth gate.
--
-- Skills consulted: predictive-analytics (latest-per-asset dedup is the
-- canonical pattern; 6-factor model rebuild is Phase 5a, separate),
-- architect (canonical view + registry pattern), data-engineer (DISTINCT ON
-- pattern, narrow selects).

BEGIN;

CREATE OR REPLACE VIEW public.v_risk_truth AS
SELECT DISTINCT ON (rs.hive_id, rs.asset_name)
  n.id                       AS asset_id,            -- canonical uuid (NULL when not yet resolved)
  rs.hive_id,
  rs.asset_name,
  rs.risk_score,                                      -- 0..1
  rs.risk_level,                                      -- 'low'|'medium'|'high'|'critical'
  rs.health_score,
  rs.mtbf_days,
  rs.days_until_failure,
  rs.top_factors,                                     -- jsonb (Phase 5a will structure this)
  rs.components,
  rs.model_version,
  rs.generated_at
FROM public.asset_risk_scores rs
LEFT JOIN public.asset_nodes n
       ON n.hive_id = rs.hive_id
      AND (lower(n.tag) = lower(rs.asset_name) OR lower(n.name) = lower(rs.asset_name))
      AND n.status = 'approved'
ORDER BY rs.hive_id, rs.asset_name, rs.generated_at DESC;

COMMENT ON VIEW public.v_risk_truth IS
  'Canonical risk score view. Latest score per (hive_id, asset_name) with canonical asset_id resolved via asset_nodes. Registered in canonical_sources as domain=risk_truth. Phase 5a model rebuild changes the writer; the view contract is stable.';

GRANT SELECT ON public.v_risk_truth TO anon, authenticated;

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'risk_truth',
  'view',
  'v_risk_truth',
  'predictive-analytics',
  'daily_13_pht',
  'Latest risk score per asset (DISTINCT ON hive_id, asset_name). Bridges to canonical asset_id via name match against asset_nodes. Source of truth for Asset Hub risk badge, predictive.html ranking, Shift Brain top-risk list, and the parts-staging recommender high-risk filter.',
  jsonb_build_object(
    'key', jsonb_build_array('hive_id', 'asset_name'),
    'hive_scoped', true,
    'solo_mode_supported', true,
    'risk_score_range', jsonb_build_array(0, 1),
    'risk_levels', jsonb_build_array('low','medium','high','critical'),
    'phase_5a_followup', 'top_factors will become a structured array of {factor, weight, contribution} after the 6-factor model rebuild lands. Consumers should read top_factors as a jsonb array regardless of internal shape.'
  ),
  'Phase A.3 contract. Phase 5a (model rebuild) is a separate effort that writes richer top_factors but does not change the view shape.'
)
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes,
      registered_at = now();

COMMIT;
