-- Analytics calc_* Tier D-f registration (2026-05-12).
-- Registers the 23 remaining calc_* functions across analytics/
-- descriptive.py, diagnostic.py, predictive.py, prescriptive.py.

BEGIN;

INSERT INTO public.canonical_formulas (formula_id, name, domain, standard_ids, library_source, inputs, outputs, formula_text, description) VALUES
  ('failure_frequency_smrp_5', 'Failure Frequency', 'maintenance', ARRAY['saeja_1011'], 'python:python-api/analytics/descriptive.py:calc_failure_frequency', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('downtime_pareto_iso_14224', 'Downtime Pareto', 'maintenance', ARRAY['iso_14224'], 'python:python-api/analytics/descriptive.py:calc_downtime_pareto', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('parts_consumption_smrp_4', 'Parts Consumption', 'maintenance', ARRAY['saeja_1011'], 'python:python-api/analytics/descriptive.py:calc_parts_consumption', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('consequence_distribution_saeja_1011', 'Consequence Distribution', 'maintenance', ARRAY['saeja_1011'], 'python:python-api/analytics/descriptive.py:calc_consequence_distribution', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('repeat_failures_iso_14224', 'Repeat Failures', 'maintenance', ARRAY['iso_14224'], 'python:python-api/analytics/descriptive.py:calc_repeat_failures', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('failure_mode_dist_iso_14224', 'Failure Mode Distribution', 'maintenance', ARRAY['iso_14224'], 'python:python-api/analytics/diagnostic.py:calc_failure_mode_distribution', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('pm_failure_corr_spearman', 'Pm Failure Correlation', 'maintenance', ARRAY[]::text[], 'python:python-api/analytics/diagnostic.py:calc_pm_failure_correlation', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('skill_mttr_corr_spearman', 'Skill Mttr Correlation', 'maintenance', ARRAY[]::text[], 'python:python-api/analytics/diagnostic.py:calc_skill_mttr_correlation', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('parts_avail_impact', 'Parts Availability Impact', 'maintenance', ARRAY[]::text[], 'python:python-api/analytics/diagnostic.py:calc_parts_availability_impact', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('repeat_failure_cluster', 'Repeat Failure Clustering', 'maintenance', ARRAY['iso_14224'], 'python:python-api/analytics/diagnostic.py:calc_repeat_failure_clustering', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('engineering_validation', 'Engineering Validation', 'maintenance', ARRAY[]::text[], 'python:python-api/analytics/diagnostic.py:calc_engineering_validation', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('next_failure_iso_13381', 'Next Failure Dates', 'predictive_maintenance', ARRAY['iso_13381_1'], 'python:python-api/analytics/predictive.py:calc_next_failure_dates', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('pm_due_calendar', 'Pm Due Calendar', 'maintenance', ARRAY['saeja_1011'], 'python:python-api/analytics/predictive.py:calc_pm_due_calendar', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('parts_stockout_forecast', 'Parts Stockout', 'maintenance', ARRAY[]::text[], 'python:python-api/analytics/predictive.py:calc_parts_stockout', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('failure_trend_smrp_5', 'Failure Trend', 'maintenance', ARRAY[]::text[], 'python:python-api/analytics/predictive.py:calc_failure_trend', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('health_score_iso_13381', 'Health Scores', 'predictive_maintenance', ARRAY['iso_13381_1'], 'python:python-api/analytics/predictive.py:calc_health_scores', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('anomaly_baseline_stddev', 'Anomaly Baseline', 'predictive_maintenance', ARRAY[]::text[], 'python:python-api/analytics/predictive.py:calc_anomaly_baseline', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('parts_spike_zscore', 'Parts Consumption Spike', 'maintenance', ARRAY[]::text[], 'python:python-api/analytics/predictive.py:calc_parts_consumption_spike', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('priority_ranking_iso_55000', 'Priority Ranking', 'maintenance', ARRAY['iso_55000'], 'python:python-api/analytics/prescriptive.py:calc_priority_ranking', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('pm_interval_opt_saeja_1011', 'Pm Interval Optimization', 'maintenance', ARRAY['saeja_1011'], 'python:python-api/analytics/prescriptive.py:calc_pm_interval_optimization', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('technician_assignment_smrp_5', 'Technician Assignment', 'maintenance', ARRAY['saeja_1011'], 'python:python-api/analytics/prescriptive.py:calc_technician_assignment', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('parts_reorder_smrp_4', 'Parts Reorder', 'maintenance', ARRAY['saeja_1011'], 'python:python-api/analytics/prescriptive.py:calc_parts_reorder', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.'),
  ('training_gaps_smrp_5', 'Training Gaps', 'maintenance', ARRAY['saeja_1011'], 'python:python-api/analytics/prescriptive.py:calc_training_gaps', '[]'::jsonb, '[]'::jsonb, '', 'Analytics formula registered as Tier D-f.')
ON CONFLICT (formula_id) DO UPDATE
  SET name=EXCLUDED.name, domain=EXCLUDED.domain, standard_ids=EXCLUDED.standard_ids,
      library_source=EXCLUDED.library_source, inputs=EXCLUDED.inputs, outputs=EXCLUDED.outputs,
      formula_text=EXCLUDED.formula_text, description=EXCLUDED.description;

COMMIT;
