-- Phase 5c: Drop the legacy `assets` table entirely.
--
-- The end of the fuel-layer cleanup. The `assets` table has been a
-- text-keyed parallel-write target since the platform's baseline; every
-- canonical surface now reads/writes asset_nodes directly. This migration:
--
--   1. Relaxes asset_nodes.hive_id from NOT NULL to nullable so solo-mode
--      workers (no hive) can keep canonical asset records on the new path.
--   2. Drops the FK asset_nodes.legacy_asset_id -> assets(id) since the
--      target is going away. The column itself stays (still useful as a
--      historical trace if assets ever needs to be reconstructed from
--      backups).
--   3. Drops the FK parts_records.asset_ref_id -> assets(asset_id) for
--      the same reason. parts_records.asset_ref_id becomes a free-text
--      field; that table is a write-only history table on its own
--      identity (parts_records.id is the canonical row key).
--   4. Backfills every solo-mode `assets` row (hive_id NULL) into
--      asset_nodes so existing records survive the table drop. Mirrors
--      the original asset_brain_backfill (20260508000010) which only
--      handled hive rows.
--   5. Drops the populate_asset_node_bridges trigger + function -- the
--      bridge it maintained read from the legacy assets table; with that
--      table gone the trigger is both broken and unnecessary (writers
--      now produce asset_nodes records directly).
--   6. DROP TABLE assets.
--
-- After this, asset_nodes is the single source of truth for asset
-- records platform-wide. Writers (logbook wizard, inventory linker,
-- CMMS import, supervisor approval) all target asset_nodes.
--
-- Skills consulted: architect (table-drop sequencing, FK dependency
-- order, populate_asset_node_bridges trigger ownership), data-engineer
-- (one-statement backfill via SELECT INSERT, idempotent guard via
-- NOT EXISTS), multitenant-engineer (solo-mode NULL hive_id support;
-- the unique constraint asset_nodes_tag_unique_per_hive uses NULLS
-- DISTINCT semantics so multiple solo workers can share the same tag),
-- security (RLS on asset_nodes inherits; solo-mode rows are reachable
-- via worker_name match, not via hive membership).

BEGIN;

-- ── 1. Relax asset_nodes.hive_id ────────────────────────────────────────────
-- The UNIQUE (hive_id, tag) constraint stays in place. Postgres treats NULLs
-- as DISTINCT by default in UNIQUE indexes, so multiple solo workers with
-- the same tag don't conflict. Within a single hive, the constraint still
-- prevents duplicate tags.

ALTER TABLE public.asset_nodes
  ALTER COLUMN hive_id DROP NOT NULL;

COMMENT ON COLUMN public.asset_nodes.hive_id IS
  'Hive scope. NULL for solo-mode workers (no hive). Multi-tenant queries filter on this; solo-mode queries filter on worker_name. Phase 5c (2026-05-12) made it nullable so the legacy `assets` table could be dropped.';

-- ── 2. Drop FKs pointing at the about-to-be-dropped assets table ─────────

ALTER TABLE public.asset_nodes
  DROP CONSTRAINT IF EXISTS asset_nodes_legacy_asset_id_fkey;

ALTER TABLE public.parts_records
  DROP CONSTRAINT IF EXISTS parts_records_asset_ref_id_fkey;

-- ── 3. Backfill solo-mode assets into asset_nodes ───────────────────────────
-- Mirror of 20260508000010_asset_brain_backfill.sql for hive_id IS NULL
-- rows. Idempotent: ON CONFLICT (hive_id, tag) merges; for NULL hives the
-- unique index treats each NULL as distinct so a re-run is a no-op (rows
-- already inserted have matching legacy_asset_id, no new rows produced
-- because of the NOT EXISTS guard below).

INSERT INTO public.asset_nodes (
  hive_id, auth_uid, worker_name, level, tag, name,
  iso_class, criticality, location, legacy_asset_id, status,
  submitted_by, approved_by, approved_at
)
SELECT
  NULL                                                 AS hive_id,        -- solo
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
WHERE a.hive_id IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM public.asset_nodes n
    WHERE n.hive_id IS NULL
      AND n.legacy_asset_id = a.id
  );

-- ── 4. Drop the populate_asset_node_bridges trigger + function ───────────
-- Trigger function references public.assets in its body; once that table
-- is gone, the trigger would fail on every insert. Drop it now. Writers
-- produce asset_nodes records directly (logbook wizard, inventory linker,
-- CMMS import all migrated in the same commit).

DROP TRIGGER IF EXISTS trg_populate_asset_node_bridges ON public.asset_nodes;
DROP FUNCTION IF EXISTS public.populate_asset_node_bridges();

-- ── 5. Drop the assets table ────────────────────────────────────────────────

DROP TABLE IF EXISTS public.assets;

-- ── 6. Provenance row ───────────────────────────────────────────────────────

DO $$
DECLARE
  cnt_nodes_total bigint;
  cnt_nodes_solo  bigint;
BEGIN
  SELECT count(*) INTO cnt_nodes_total FROM public.asset_nodes;
  SELECT count(*) INTO cnt_nodes_solo  FROM public.asset_nodes WHERE hive_id IS NULL;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
    INSERT INTO public.automation_log (job_name, status, detail)
    VALUES (
      'phase_5c_drop_assets',
      'success',
      format(
        'asset_nodes total: %s (%s solo-mode). assets table + FKs + populate_asset_node_bridges trigger dropped.',
        cnt_nodes_total, cnt_nodes_solo
      )
    );
  END IF;
END
$$;

COMMIT;
