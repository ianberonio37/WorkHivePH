-- ─── v_logbook_truth canonical view ──────────────────────────────────────────
-- Truth-scattering fix for the logbook hotspot. Identified by
-- validate_silo_monitor.py as the largest unregistered hotspot (27 distinct
-- consumer files). The view bakes in the asset_nodes bridge (legacy_asset_id)
-- so every reader gets asset_node_id / asset_tag / asset_iso_class for free
-- and a derived is_corrective flag for analytics consumers.
--
-- logbook does NOT have a deleted_at column today — soft-delete is community
-- and marketplace only. If logbook ever adds soft-delete, the WHERE clause
-- here is the single point that needs to learn .is(deleted_at, null).

CREATE OR REPLACE VIEW public.v_logbook_truth AS
SELECT
  -- Core columns (every existing reader's superset)
  l.id, l.hive_id, l.worker_name,
  l.created_at, l.closed_at, l.date, l.status,
  l.maintenance_type, l.category,
  l.machine, l.asset_ref_id,
  l.problem, l.action, l.root_cause, l.failure_consequence,
  l.downtime_hours, l.production_output,
  l.parts_used, l.readings_json,
  l.knowledge, l.tasklist_acknowledged, l.tasklist_note,
  l.photo, l.pm_completion_id,
  l.wo_state, l.wo_assigned_to,
  -- Bridge to asset_nodes via legacy_asset_id (hive-scoped to avoid
  -- cross-hive name collisions). Consumers no longer need to JOIN themselves
  -- when they want the canonical asset id / iso class / criticality.
  n.id            AS asset_node_id,
  n.tag           AS asset_tag,
  n.name          AS asset_node_name,
  n.iso_class     AS asset_iso_class,
  n.criticality   AS asset_criticality,
  n.location      AS asset_location,
  -- Derived: is this a corrective / breakdown event? Multiple consumers
  -- duplicate this regex; bake it in once.
  (l.maintenance_type ~* '(corrective|breakdown)') AS is_corrective
FROM public.logbook l
LEFT JOIN public.asset_nodes n
  ON n.legacy_asset_id = l.asset_ref_id
 AND n.hive_id        = l.hive_id;

GRANT SELECT ON public.v_logbook_truth TO anon, authenticated;

COMMENT ON VIEW public.v_logbook_truth IS
  'Canonical logbook view: every column + asset_nodes bridge + is_corrective derived flag. Registered in canonical_sources as logbook_truth.';

-- ─── Register logbook_truth in canonical_sources ──────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('logbook_truth', 'view', 'v_logbook_truth', 'data-engineer', 'realtime',
   'Canonical logbook reader. Carries every logbook column plus a hive-scoped LEFT JOIN to asset_nodes (asset_node_id / asset_tag / asset_iso_class / asset_criticality / asset_location) so consumers no longer have to bridge legacy_asset_id themselves. Includes is_corrective derived flag (matches /(corrective|breakdown)/i) so analytics consumers stop reimplementing the same regex.',
   jsonb_build_object(
     'key',          jsonb_build_array('id'),
     'hive_scoped',  true,
     'soft_delete',  false,
     'bridge_columns', jsonb_build_array('asset_node_id','asset_tag','asset_iso_class','asset_criticality','asset_location'),
     'derived_columns', jsonb_build_array('is_corrective'),
     'standards',    jsonb_build_array('ISO 14224')
   ),
   'logbook has no deleted_at column today; if soft-delete is ever added, this view becomes the single point that needs to learn the filter.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes;
