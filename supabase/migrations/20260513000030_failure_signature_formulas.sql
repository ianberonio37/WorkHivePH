-- Register the 3 failure-signature-scan detection rules in canonical_formulas
-- as Tier D-f entries (companion to the existing repeat_failures_iso_14224
-- entry from 20260512000015). Walkthrough 2026-05-13 caught that the
-- Pattern Alerts panel on hive.html renders cards labelled
-- escalating_frequency / multi_symptom / missed_pm with confident
-- thresholds, but only repeat_failure had a formula anchor — so the other
-- three rules were detection logic with no traceable contract.
--
-- Each entry points to the edge function rule branch as the library source,
-- standard = ISO 14224 (failure data taxonomy + reliability metric
-- definitions). description = the literal trigger condition lifted from
-- the edge fn doc comment so a supervisor or auditor can trace the alert
-- back to a verifiable rule.

BEGIN;

INSERT INTO public.canonical_formulas (formula_id, name, domain, standard_ids, library_source, inputs, outputs, formula_text, description) VALUES
  ('escalating_frequency_iso_14224',
   'Escalating Failure Frequency',
   'maintenance',
   ARRAY['iso_14224'],
   'edge:supabase/functions/failure-signature-scan/index.ts:detectEscalatingFrequency',
   '[]'::jsonb,
   '[]'::jsonb,
   'failures(last_30d) > failures(prior_60d) * 0.5',
   'Pre-failure detection rule. Fires when the failure count in the last 30 days exceeds half the count from the prior 60 days — i.e. failure rate is accelerating. ISO 14224 §9.5.2 reliability rate trending.'),

  ('multi_symptom_iso_14224',
   'Multi-Symptom Concurrence',
   'maintenance',
   ARRAY['iso_14224'],
   'edge:supabase/functions/failure-signature-scan/index.ts:detectMultiSymptom',
   '[]'::jsonb,
   '[]'::jsonb,
   'distinct(root_cause_category) on machine within 30d >= 2',
   'Pre-failure detection rule. Fires when a single machine has 2 or more distinct root-cause categories in 30 days, suggesting a deeper systemic issue rather than an isolated mode. ISO 14224 §9.3.1 failure mode taxonomy.'),

  ('missed_pm_iso_14224',
   'Missed PM with Breakdown',
   'maintenance',
   ARRAY['iso_14224'],
   'edge:supabase/functions/failure-signature-scan/index.ts:detectMissedPM',
   '[]'::jsonb,
   '[]'::jsonb,
   'machine.pm_overdue == true AND breakdown_count(last_30d) >= 1',
   'Pre-failure detection rule. Fires when a PM-overdue asset has also had a breakdown in the last 30 days — flagging the PM gap as a contributing factor. ISO 14224 §9.4 preventive maintenance compliance.')
ON CONFLICT (formula_id) DO UPDATE
  SET name=EXCLUDED.name, domain=EXCLUDED.domain, standard_ids=EXCLUDED.standard_ids,
      library_source=EXCLUDED.library_source, inputs=EXCLUDED.inputs, outputs=EXCLUDED.outputs,
      formula_text=EXCLUDED.formula_text, description=EXCLUDED.description;

COMMIT;
