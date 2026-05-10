-- ─── Phase R.6: v_pf_truth canonical view ─────────────────────────────────────
-- Latest P-F interval per (hive, asset, parameter, fmea_mode_id) via DISTINCT ON.
-- Mirrors the v_weibull_truth pattern so AI agents reading canonical_sources can
-- pull P-F intervals via a single registered shape rather than trawling
-- pf_intervals directly.

CREATE OR REPLACE VIEW public.v_pf_truth AS
SELECT DISTINCT ON (hive_id, asset_id, parameter, COALESCE(fmea_mode_id::text, '_'))
  id AS pf_interval_id,
  hive_id,
  asset_id,
  fmea_mode_id,
  parameter,
  p_threshold,
  f_threshold,
  pf_days,
  recommended_interval_days,
  basis,
  generated_at
FROM public.pf_intervals
ORDER BY hive_id, asset_id, parameter, COALESCE(fmea_mode_id::text, '_'), generated_at DESC;

GRANT SELECT ON public.v_pf_truth TO anon, authenticated;

COMMENT ON VIEW public.v_pf_truth IS
  'Canonical P-F interval: latest row per (hive, asset, parameter, fmea_mode) via DISTINCT ON. Registered in canonical_sources as pf_truth.';

-- ─── Register pf_truth in canonical_sources ───────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('pf_truth', 'view', 'v_pf_truth', 'maintenance-expert', 'on_demand_recompute',
   'Canonical P-F interval per (asset, parameter). One row per most recent recompute. The recommended_interval_days column carries the inspection cadence per the RCM rule (P-F/2 standard, P-F/3 for safety-critical assets). Source of truth for the P-F tab on Asset Hub and AI agents asking about CBM cadence.',
   jsonb_build_object(
     'key', jsonb_build_array('pf_interval_id'),
     'hive_scoped', true,
     'distinct_on', jsonb_build_array('hive_id','asset_id','parameter','fmea_mode_id'),
     'basis_values', jsonb_build_array('P-F/2','P-F/3'),
     'parameter_examples', jsonb_build_array('vibration_mms','bearing_temp_c','oil_debris_ppm','pressure_bar'),
     'standards', jsonb_build_array('SAE JA1011','SAE JA1012','RCM Bathtub Curve','ISO 13381-1:2015')
   ),
   'Phase R.6 contract. The recommended_interval_days column is a positive integer; do not divide it again. When safety_critical=true the calculator already applied P-F/3.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes;
