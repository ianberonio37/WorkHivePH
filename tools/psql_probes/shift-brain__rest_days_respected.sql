-- rest_days_respected: the oracle asks that availability respect leave and rest days. The walked
-- finding (FIXED THIS WALK): the platform has NO leave or rest-day model for hive workers at all,
-- so the honest state is "nothing to respect yet" plus briefing wording that does not invent
-- headcounts. This probe pins the STRUCTURAL BASIS of that reasoning: no leave/rest/availability
-- columns exist on the worker-facing tables. THE DAY A LEAVE MODEL LANDS, THIS PROBE FAILS — which
-- is correct: the row must then be re-examined against a model that finally exists.
-- expect: rest_day_model_absent \| 0
-- expect: workers_present \| t
SELECT 'rest_day_model_absent | ' || count(*) FROM information_schema.columns
WHERE table_schema='public'
  AND table_name IN ('hive_members','worker_profiles','schedule_items','shift_plans')
  AND (column_name ILIKE '%leave%' OR column_name ILIKE '%rest_day%'
       OR column_name ILIKE '%day_off%' OR column_name ILIKE '%vacation%');
SELECT 'workers_present | ' || (count(*) > 0) FROM hive_members WHERE status='active';
