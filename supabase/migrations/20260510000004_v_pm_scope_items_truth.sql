-- ─── v_pm_scope_items_truth canonical view ───────────────────────────────────
-- Truth-scattering fix for the pm_scope_items hotspot. validate_silo_monitor
-- flagged 8 distinct consumer files reading the underlying table; each one
-- reimplemented the same per-scope-item due-date math (anchor_date or last
-- completion + frequency_days). The view bakes in:
--
-- 1. Bridge to pm_assets — asset_name / tag_id / category / criticality /
--    location come for free; consumers no longer JOIN themselves.
-- 2. frequency_days — the standard mapping (Monthly=30, Quarterly=90,
--    Semi-Annual=180, Yearly=365). Currently hardcoded in JS in pm-scheduler.html
--    AND hive.html, drift candidate.
-- 3. last_completed_at / last_completed_by — latest pm_completions row per
--    scope_item via LATERAL join, so consumers stop fetching the entire
--    completions table and grouping client-side.
-- 4. next_due_date / days_until_due / is_overdue / is_due_soon — derived
--    flags that hive.html, alert-hub.html, pm-scheduler.html each compute
--    independently with slightly different rules. One place, one definition.

DROP VIEW IF EXISTS public.v_pm_scope_items_truth;

CREATE VIEW public.v_pm_scope_items_truth AS
SELECT
  scope_item_id,
  scope_item_id AS id,             -- drop-in compat for `.eq('id', ...)` callers
  hive_id,
  pm_asset_id,
  pm_asset_id   AS asset_id,        -- drop-in compat for `.in('asset_id', ...)` callers
  item_text, frequency, anchor_date,
  is_custom, created_at,
  asset_name, asset_tag, asset_category, asset_criticality, asset_location,
  frequency_days,
  last_completed_at, last_completed_by,
  next_due_date,
  (next_due_date - CURRENT_DATE)                            AS days_until_due,
  (next_due_date < CURRENT_DATE)                            AS is_overdue,
  (next_due_date BETWEEN CURRENT_DATE
                    AND (CURRENT_DATE + INTERVAL '14 days')::date) AS is_due_soon
FROM (
  SELECT
    s.id            AS scope_item_id,
    s.hive_id,
    s.asset_id      AS pm_asset_id,
    s.item_text,
    s.frequency,
    s.anchor_date,
    s.is_custom,
    s.created_at,
    pa.asset_name,
    pa.tag_id       AS asset_tag,
    pa.category     AS asset_category,
    pa.criticality  AS asset_criticality,
    pa.location     AS asset_location,
    CASE s.frequency
      WHEN 'Monthly'     THEN 30
      WHEN 'Quarterly'   THEN 90
      WHEN 'Semi-Annual' THEN 180
      WHEN 'Yearly'      THEN 365
      ELSE 90
    END             AS frequency_days,
    last_pc.last_completed_at,
    last_pc.last_completed_by,
    (COALESCE(last_pc.last_completed_at::date, s.anchor_date, s.created_at::date)
     + (CASE s.frequency
          WHEN 'Monthly'     THEN INTERVAL '30 days'
          WHEN 'Quarterly'   THEN INTERVAL '90 days'
          WHEN 'Semi-Annual' THEN INTERVAL '180 days'
          WHEN 'Yearly'      THEN INTERVAL '365 days'
          ELSE INTERVAL '90 days'
        END))::date AS next_due_date
  FROM public.pm_scope_items s
  LEFT JOIN public.pm_assets pa ON pa.id = s.asset_id
  LEFT JOIN LATERAL (
    SELECT pc.completed_at AS last_completed_at,
           pc.worker_name  AS last_completed_by
    FROM public.pm_completions pc
    WHERE pc.scope_item_id = s.id
      AND pc.status = 'done'
    ORDER BY pc.completed_at DESC
    LIMIT 1
  ) last_pc ON TRUE
) sub;

GRANT SELECT ON public.v_pm_scope_items_truth TO anon, authenticated;

COMMENT ON VIEW public.v_pm_scope_items_truth IS
  'Canonical pm_scope_items view: every column + bridge to pm_assets + frequency_days mapping + LATERAL last_completed_at/by + next_due_date / days_until_due / is_overdue / is_due_soon derived columns. Registered in canonical_sources as pm_scope_items_truth.';

-- ─── Register pm_scope_items_truth in canonical_sources ───────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('pm_scope_items_truth', 'view', 'v_pm_scope_items_truth', 'maintenance-expert', 'realtime',
   'Canonical pm_scope_items reader. Per-scope-item granularity (complementary to v_pm_compliance_truth which is per-asset). Bridges to pm_assets and computes next_due_date / days_until_due / is_overdue / is_due_soon via the standard frequency map (Monthly=30d, Quarterly=90d, Semi-Annual=180d, Yearly=365d).',
   jsonb_build_object(
     'key',          jsonb_build_array('scope_item_id'),
     'hive_scoped',  true,
     'soft_delete',  false,
     'bridge_columns',  jsonb_build_array('asset_name','asset_tag','asset_category','asset_criticality','asset_location'),
     'derived_columns', jsonb_build_array('frequency_days','last_completed_at','last_completed_by','next_due_date','days_until_due','is_overdue','is_due_soon'),
     'frequency_map',   jsonb_build_object('Monthly',30,'Quarterly',90,'Semi-Annual',180,'Yearly',365),
     'standards',    jsonb_build_array('SAE JA1011','ISO 14224')
   ),
   'frequency_days mapping is duplicated in pm-scheduler.html (FREQ_DAYS) and hive.html (HIVE_FREQ_DAYS). Future cleanup: those constants can be retired once their callers read the view.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes;
