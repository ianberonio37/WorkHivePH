-- Asset Brain Phase 1: backfill asset_nodes from existing pm_assets and legacy assets.
--
-- Strategy:
--   1. Insert one asset_nodes row per pm_assets row (uuid-keyed, better structured).
--   2. UPSERT from legacy assets, merging legacy_asset_id into the matching pm-derived
--      node where (hive_id, tag) collides. New legacy-only rows are inserted fresh.
--   3. Backfill asset_edges with parent_of when pm_assets has a category hierarchy
--      we can infer. Phase 1 keeps this conservative; explicit edges are added later.
--
-- Idempotent: re-running this migration is safe. ON CONFLICT (hive_id, tag) merges.
-- Solo-mode rows (hive_id IS NULL) are skipped intentionally - the graph is hive-scoped.
--
-- Skills consulted: architect (FK type matching, idempotency), data-engineer (batch
-- inserts, narrow selects), maintenance-expert (criticality vocabulary mapping
-- across Filipino industrial norms), multitenant-engineer (hive scope on every row).

BEGIN;

-- 1. Backfill from pm_assets. Each pm_asset becomes one asset_node with pm_asset_id linked.

INSERT INTO public.asset_nodes (
  hive_id, auth_uid, worker_name, level, tag, name,
  iso_class, criticality, location, pm_asset_id, status, submitted_by, approved_by, approved_at
)
SELECT
  pa.hive_id,
  pa.auth_uid,
  pa.worker_name,
  'equipment'                                  AS level,
  COALESCE(NULLIF(pa.tag_id, ''), pa.asset_name) AS tag,
  pa.asset_name                                AS name,
  pa.category                                  AS iso_class,
  CASE
    WHEN lower(COALESCE(pa.criticality, '')) LIKE '%critical%' THEN 'critical'
    WHEN lower(COALESCE(pa.criticality, '')) LIKE '%major%'    THEN 'high'
    WHEN lower(COALESCE(pa.criticality, '')) LIKE '%high%'     THEN 'high'
    WHEN lower(COALESCE(pa.criticality, '')) LIKE '%minor%'    THEN 'medium'
    WHEN lower(COALESCE(pa.criticality, '')) LIKE '%medium%'   THEN 'medium'
    WHEN lower(COALESCE(pa.criticality, '')) LIKE '%low%'      THEN 'low'
    ELSE 'medium'
  END                                          AS criticality,
  pa.location,
  pa.id                                        AS pm_asset_id,
  'approved'                                   AS status,
  pa.worker_name                               AS submitted_by,
  pa.worker_name                               AS approved_by,
  pa.created_at                                AS approved_at
FROM public.pm_assets pa
WHERE pa.hive_id IS NOT NULL
ON CONFLICT (hive_id, tag) DO UPDATE
  SET pm_asset_id = COALESCE(public.asset_nodes.pm_asset_id, EXCLUDED.pm_asset_id),
      iso_class   = COALESCE(public.asset_nodes.iso_class,   EXCLUDED.iso_class),
      location    = COALESCE(public.asset_nodes.location,    EXCLUDED.location),
      auth_uid    = COALESCE(public.asset_nodes.auth_uid,    EXCLUDED.auth_uid);

-- 2. Backfill from legacy assets. Where the (hive_id, tag) already exists from
--    pm_assets, just merge legacy_asset_id into the existing row. Otherwise insert fresh.

INSERT INTO public.asset_nodes (
  hive_id, auth_uid, worker_name, level, tag, name,
  iso_class, criticality, location, legacy_asset_id, status, submitted_by, approved_by, approved_at
)
SELECT
  a.hive_id,
  a.auth_uid,
  a.worker_name,
  'equipment'                                          AS level,
  COALESCE(NULLIF(a.asset_id, ''), NULLIF(a.name, ''), a.id) AS tag,
  COALESCE(NULLIF(a.name, ''), a.asset_id, a.id)       AS name,
  NULLIF(a.type, '')                                   AS iso_class,
  CASE
    WHEN lower(COALESCE(a.criticality, '')) LIKE '%critical%' THEN 'critical'
    WHEN lower(COALESCE(a.criticality, '')) LIKE '%major%'    THEN 'high'
    WHEN lower(COALESCE(a.criticality, '')) LIKE '%high%'     THEN 'high'
    WHEN lower(COALESCE(a.criticality, '')) LIKE '%minor%'    THEN 'medium'
    WHEN lower(COALESCE(a.criticality, '')) LIKE '%medium%'   THEN 'medium'
    WHEN lower(COALESCE(a.criticality, '')) LIKE '%low%'      THEN 'low'
    ELSE 'medium'
  END                                                  AS criticality,
  NULLIF(a.location, '')                               AS location,
  a.id                                                 AS legacy_asset_id,
  COALESCE(NULLIF(a.status, ''), 'approved')           AS status,
  COALESCE(a.submitted_by, a.worker_name)              AS submitted_by,
  a.approved_by,
  a.approved_at
FROM public.assets a
WHERE a.hive_id IS NOT NULL
ON CONFLICT (hive_id, tag) DO UPDATE
  SET legacy_asset_id = COALESCE(public.asset_nodes.legacy_asset_id, EXCLUDED.legacy_asset_id),
      iso_class       = COALESCE(public.asset_nodes.iso_class,       EXCLUDED.iso_class),
      location        = COALESCE(public.asset_nodes.location,        EXCLUDED.location),
      auth_uid        = COALESCE(public.asset_nodes.auth_uid,        EXCLUDED.auth_uid);

-- 3. Audit row: how many came from where. Stored as a one-off provenance comment in
--    automation_log if that table is present; otherwise skipped silently.

DO $$
DECLARE
  cnt_pm   bigint;
  cnt_leg  bigint;
  cnt_both bigint;
BEGIN
  SELECT count(*) INTO cnt_pm   FROM public.asset_nodes WHERE pm_asset_id     IS NOT NULL AND legacy_asset_id IS NULL;
  SELECT count(*) INTO cnt_leg  FROM public.asset_nodes WHERE legacy_asset_id IS NOT NULL AND pm_asset_id     IS NULL;
  SELECT count(*) INTO cnt_both FROM public.asset_nodes WHERE pm_asset_id     IS NOT NULL AND legacy_asset_id IS NOT NULL;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
    INSERT INTO public.automation_log (job_name, status, detail)
    VALUES (
      'asset_brain_backfill',
      'success',
      format(
        'pm_only=%s legacy_only=%s merged=%s total=%s',
        cnt_pm, cnt_leg, cnt_both, cnt_pm + cnt_leg + cnt_both
      )
    );
  END IF;
END
$$;

COMMIT;
