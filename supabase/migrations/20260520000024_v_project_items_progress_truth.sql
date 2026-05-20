-- ─── v_project_items_truth + v_project_progress_truth canonical views ──────
-- Turn 4 of the canonical-drift flywheel. project_items had 5 raw reads,
-- project_progress_logs had 6. Both PM-domain tables that drive the
-- project-manager surface + the project-report rollups.

DROP VIEW IF EXISTS public.v_project_items_truth;
DROP VIEW IF EXISTS public.v_project_progress_truth;

-- 2026-05-20: 20260520000009_drop_phantom_columns_seeder_only.sql earlier
-- dropped actual_start/actual_end/predecessors/sort_order from project_items
-- (declared unused by the phantom auditor). The view below restores them
-- because the schedule-flag derivations need actual_start, and the audit
-- only considered code consumers — the view IS the consumer that justifies
-- keeping them. Additive ALTER restores any missing column.
ALTER TABLE IF EXISTS public.project_items
  ADD COLUMN IF NOT EXISTS actual_start    date,
  ADD COLUMN IF NOT EXISTS actual_end      date,
  ADD COLUMN IF NOT EXISTS predecessors    jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS estimated_hours numeric(8,2),
  ADD COLUMN IF NOT EXISTS actual_hours    numeric(8,2),
  ADD COLUMN IF NOT EXISTS sort_order      integer NOT NULL DEFAULT 0;

-- ── project_items_truth ─────────────────────────────────────────────────────
CREATE VIEW public.v_project_items_truth AS
SELECT
  i.id,
  i.project_id,
  i.hive_id,
  i.wbs_code,
  i.title,
  i.owner_name,
  i.status,
  i.pct_complete,
  i.planned_start,
  i.planned_end,
  i.actual_start,
  i.actual_end,
  i.predecessors,
  i.estimated_hours,
  i.actual_hours,
  i.notes,
  i.sort_order,
  i.created_at,
  i.updated_at,
  -- Bridge to projects (project name and overall status)
  p.name           AS project_name,
  p.project_code   AS project_code,
  p.status         AS project_status,
  -- Derived status flags
  (i.status = 'pending')     AS is_pending,
  (i.status = 'in_progress') AS is_in_progress,
  (i.status = 'done')        AS is_done,
  (i.status = 'blocked')     AS is_blocked,
  (i.status = 'skipped')     AS is_skipped,
  -- Derived schedule flags
  (i.planned_end IS NOT NULL AND i.planned_end < CURRENT_DATE
     AND i.status NOT IN ('done','skipped'))           AS is_overdue,
  (i.planned_start IS NOT NULL AND i.planned_start <= CURRENT_DATE
     AND i.actual_start IS NULL
     AND i.status = 'pending')                          AS is_late_start
FROM public.project_items i
LEFT JOIN public.projects p ON p.id = i.project_id;

GRANT SELECT ON public.v_project_items_truth TO anon, authenticated;

COMMENT ON VIEW public.v_project_items_truth IS
  'Canonical project_items reader. Per-item granularity + project bridge (name/code/status) + 5 status flags + 2 schedule flags (is_overdue, is_late_start).';

-- ── project_progress_truth ──────────────────────────────────────────────────
CREATE VIEW public.v_project_progress_truth AS
SELECT
  pl.id,
  pl.project_id,
  pl.hive_id,
  pl.log_date,
  pl.reported_by,
  pl.pct_complete,
  pl.hours_worked,
  pl.notes,
  pl.blockers,
  pl.acknowledged_by,
  pl.acknowledged_at,
  pl.created_at,
  -- Bridge to projects
  p.name           AS project_name,
  p.project_code   AS project_code,
  p.status         AS project_status,
  -- Derived flags
  (pl.acknowledged_at IS NOT NULL) AS is_acknowledged,
  (pl.blockers IS NOT NULL AND length(trim(pl.blockers)) > 0) AS has_blocker,
  (now()::date - pl.log_date)      AS days_since_log
FROM public.project_progress_logs pl
LEFT JOIN public.projects p ON p.id = pl.project_id;

GRANT SELECT ON public.v_project_progress_truth TO anon, authenticated;

COMMENT ON VIEW public.v_project_progress_truth IS
  'Canonical project_progress_logs reader. Per-log granularity + project bridge + is_acknowledged/has_blocker/days_since_log derived flags.';

-- Register both in canonical_sources
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('project_items_truth', 'view', 'v_project_items_truth', 'data-engineer', 'realtime',
   'Canonical project_items reader. Per-item with project bridge + 5 status flags + 2 schedule flags.',
   jsonb_build_object(
     'key', jsonb_build_array('id'), 'hive_scoped', true, 'soft_delete', false,
     'bridge_columns',  jsonb_build_array('project_name','project_code','project_status'),
     'derived_columns', jsonb_build_array('is_pending','is_in_progress','is_done','is_blocked','is_skipped','is_overdue','is_late_start')
   ),
   'Turn 4 of TIER C gap-table sweep (2026-05-20).'),
  ('project_progress_truth', 'view', 'v_project_progress_truth', 'data-engineer', 'realtime',
   'Canonical project_progress_logs reader. Per-log with project bridge + 3 derived flags.',
   jsonb_build_object(
     'key', jsonb_build_array('id'), 'hive_scoped', true, 'soft_delete', false,
     'bridge_columns',  jsonb_build_array('project_name','project_code','project_status'),
     'derived_columns', jsonb_build_array('is_acknowledged','has_blocker','days_since_log')
   ),
   'Turn 4 of TIER C gap-table sweep (2026-05-20).')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind, source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill, freshness = EXCLUDED.freshness,
      description = EXCLUDED.description, contract = EXCLUDED.contract,
      notes       = EXCLUDED.notes;
