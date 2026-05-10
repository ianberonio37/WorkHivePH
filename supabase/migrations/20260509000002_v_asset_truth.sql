-- Canonical Sources Phase A.2: v_asset_truth view.
--
-- This is THE single read path for asset metadata across the platform.
-- Supersedes asset_brain_overview (May 8) which stays as a thin wrapper
-- for backward compatibility during the cutover. New code reads from
-- v_asset_truth; old code stays correct because asset_brain_overview now
-- selects from the same underlying source (asset_nodes).
--
-- The view unifies the 3 asset PK schemes (assets.id text, pm_assets.id uuid,
-- asset_nodes.id uuid) by exposing asset_nodes.id as the canonical uuid AND
-- carrying legacy_asset_id (text) and pm_asset_id (uuid) as bridge columns
-- so consumers can resolve any of the legacy IDs without a separate query.
--
-- RLS: views inherit RLS from underlying tables. asset_nodes already has
-- a hive-membership-join read policy (Phase 0), so v_asset_truth inherits
-- the same protection. No additional policy needed.
--
-- Skills consulted: architect (canonical sources pattern, view as contract),
-- multitenant-engineer (RLS inheritance from base table), data-engineer
-- (narrow indexed lookups via underlying asset_nodes columns).

BEGIN;

CREATE OR REPLACE VIEW public.v_asset_truth AS
SELECT
  n.id              AS asset_id,                  -- canonical uuid
  n.hive_id,
  n.auth_uid,
  n.parent_id,
  n.level,
  n.tag,
  n.name,
  n.iso_class,
  n.criticality,
  n.location,
  n.manufacturer,
  n.model,
  n.serial_no,
  n.install_date,
  n.external_ids,
  n.legacy_asset_id,                              -- bridge for inventory + logbook FK
  n.pm_asset_id,                                  -- bridge for pm_completions / pm_scope_items
  n.status,
  n.submitted_by,
  n.approved_by,
  n.approved_at,
  n.created_at,
  n.updated_at,
  -- Aggregate footprint (was asset_brain_overview)
  (SELECT count(*) FROM public.logbook l
     WHERE l.hive_id = n.hive_id
       AND l.asset_ref_id = n.legacy_asset_id) AS lifetime_logbook_entries,
  (SELECT max(l.created_at) FROM public.logbook l
     WHERE l.hive_id = n.hive_id
       AND l.asset_ref_id = n.legacy_asset_id
       AND l.maintenance_type = 'Breakdown / Corrective') AS last_failure_at,
  (SELECT count(*) FROM public.pm_completions pc
     WHERE pc.hive_id = n.hive_id
       AND pc.asset_id = n.pm_asset_id) AS pm_completed_count,
  (SELECT count(*) FROM public.asset_edges e
     WHERE e.hive_id = n.hive_id
       AND (e.from_node_id = n.id OR e.to_node_id = n.id)) AS edge_count
FROM public.asset_nodes n
WHERE n.status = 'approved';

COMMENT ON VIEW public.v_asset_truth IS
  'Canonical asset 360 view. Single read path for asset metadata across the platform. Bridges 3 legacy PK schemes via legacy_asset_id + pm_asset_id columns. Registered in canonical_sources as domain=asset_truth.';

GRANT SELECT ON public.v_asset_truth TO anon, authenticated;

-- Register in the canonical_sources registry. ON CONFLICT DO UPDATE so the
-- contract can evolve without dropping and re-inserting.
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'asset_truth',
  'view',
  'v_asset_truth',
  'architect',
  'realtime',
  'Canonical asset 360. Bridges asset_nodes + legacy assets.id (text) + pm_assets.id (uuid) via legacy_asset_id and pm_asset_id columns. Hive-scoped via inherited RLS on asset_nodes. status=approved only.',
  jsonb_build_object(
    'key', jsonb_build_array('asset_id'),
    'hive_scoped', true,
    'approved_only', true,
    'bridge_columns', jsonb_build_array('legacy_asset_id', 'pm_asset_id'),
    'aggregate_columns', jsonb_build_array(
      'lifetime_logbook_entries', 'last_failure_at',
      'pm_completed_count', 'edge_count'
    )
  ),
  'Supersedes asset_brain_overview (kept as wrapper for backward compat). New code reads v_asset_truth.'
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
