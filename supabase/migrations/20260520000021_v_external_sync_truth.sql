-- ─── v_external_sync_truth canonical view ──────────────────────────────────
-- TIER C gap-table promotion #5: external_sync had 5 raw reads across 3
-- cross-domain consumers (asset-hub, logbook, integrations) plus the
-- integrations.html owner writes.
--
-- Superset of every reader + derived freshness flags so consumers can drop
-- their per-page "is this row recent?" client math. integrations.html
-- stays as the canonical CRUD owner via PAGE_RAW_OWNERS; cross-domain
-- consumers read through the view.

DROP VIEW IF EXISTS public.v_external_sync_truth;

CREATE VIEW public.v_external_sync_truth AS
SELECT
  e.id,
  e.hive_id,
  e.system_type,
  e.external_id,
  e.entity_type,
  e.workhive_table,
  e.status,
  e.sync_payload,
  e.last_synced_at,
  e.sync_status,
  -- Derived freshness flags drop per-page age calculations
  (e.sync_status = 'active')                                   AS is_active,
  (e.sync_status = 'deleted')                                  AS is_deleted,
  (e.sync_status = 'error')                                    AS is_error,
  (e.last_synced_at >= now() - interval '24 hours')            AS synced_within_24h,
  (e.last_synced_at >= now() - interval '7 days')              AS synced_within_7d,
  ((now()::date - e.last_synced_at::date))                     AS days_since_sync
FROM public.external_sync e;

GRANT SELECT ON public.v_external_sync_truth TO anon, authenticated;

COMMENT ON VIEW public.v_external_sync_truth IS
  'Canonical external_sync reader. Per-sync-row granularity + derived is_active/is_deleted/is_error + synced_within_24h/7d freshness flags. integrations.html remains the CRUD owner; cross-domain consumers (asset-hub, logbook) read here.';

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('external_sync_truth', 'view', 'v_external_sync_truth', 'integration-engineer', 'realtime',
   'Canonical external_sync reader. Per-row granularity + derived freshness flags (is_active/is_deleted/is_error/synced_within_24h/7d) + days_since_sync.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'derived_columns', jsonb_build_array('is_active','is_deleted','is_error','synced_within_24h','synced_within_7d','days_since_sync')
   ),
   'Phase 3 of the TIER C gap-table sweep (2026-05-20). 5 raw reads at baseline. integrations.html remains the CRUD owner for upsert/delete operations; selects on cross-domain consumers (asset-hub, logbook) migrate here.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind,
      source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill,
      freshness   = EXCLUDED.freshness,
      description = EXCLUDED.description,
      contract    = EXCLUDED.contract,
      notes       = EXCLUDED.notes;
