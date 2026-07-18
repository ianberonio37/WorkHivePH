-- PROJECT_MANAGER_DEEP_ARC Extension 1 — the MAINTENANCE-NATURE facet as a DERIVED lens.
-- Ian's taxonomy (reactive/breakdown - preventive - project) is orthogonal to project_type
-- (workorder/shutdown/capex/contractor = structure). It is derived project_type-primary,
-- refined by the source-link composition the X-keystone bundles: a workorder that bundles
-- logbook entries is reactive; one that bundles PM completions is a preventive rollup.
-- Validated against seeded data (shutdown -> preventive, capex/contractor -> project,
-- workorder+logbook -> reactive). New migration (CREATE OR REPLACE) so 20260512000013 stays immutable.
CREATE OR REPLACE VIEW public.v_project_truth AS
SELECT
  p.id                          AS project_id,
  p.hive_id,
  p.project_code,
  p.name,
  p.project_type,
  p.status,
  p.priority,
  p.owner_name,
  p.budget_php,
  p.start_date,
  p.end_date                    AS target_end_date,
  p.closed_at                   AS actual_end_at,
  p.created_at,
  p.updated_at,
  (SELECT count(*) FROM public.project_items pi
     WHERE pi.project_id = p.id) AS item_count,
  (SELECT count(*) FROM public.project_items pi
     WHERE pi.project_id = p.id AND pi.status = 'done') AS items_done,
  (SELECT coalesce(sum(pi.estimated_hours), 0)::numeric FROM public.project_items pi
     WHERE pi.project_id = p.id) AS estimated_total_hours,
  (SELECT coalesce(sum(pi.actual_hours), 0)::numeric FROM public.project_items pi
     WHERE pi.project_id = p.id) AS actual_total_hours,
  (SELECT max(ppl.created_at) FROM public.project_progress_logs ppl
     WHERE ppl.project_id = p.id) AS last_progress_at,
  (SELECT count(*) FROM public.project_change_orders pco
     WHERE pco.project_id = p.id AND pco.status = 'approved') AS approved_change_orders,
  (SELECT coalesce(sum(pco.cost_impact_php), 0)::numeric FROM public.project_change_orders pco
     WHERE pco.project_id = p.id AND pco.status = 'approved') AS approved_co_cost_php,
  (SELECT count(*) FROM public.project_links pl
     WHERE pl.project_id = p.id) AS link_count,
  -- Extension 1: maintenance-nature facet (APPENDED at end — CREATE OR REPLACE VIEW
  -- cannot insert a column mid-list). Derived project_type-primary, link-refined.
  CASE
    WHEN p.project_type IN ('capex', 'contractor') THEN 'project'
    WHEN p.project_type = 'shutdown' THEN 'preventive'
    WHEN p.project_type = 'workorder'
         AND EXISTS (SELECT 1 FROM public.project_links pl
                     WHERE pl.project_id = p.id AND pl.link_type = 'logbook') THEN 'reactive'
    WHEN p.project_type = 'workorder'
         AND EXISTS (SELECT 1 FROM public.project_links pl
                     WHERE pl.project_id = p.id AND pl.link_type = 'pm_completion') THEN 'preventive'
    ELSE 'reactive'
  END                           AS maintenance_nature
FROM public.projects p
WHERE p.deleted_at IS NULL AND p.status != 'archived';

GRANT SELECT ON public.v_project_truth TO anon, authenticated;
