-- Phase 5b.1: Drop logbook.asset_ref_id (text) and the legacy FK to assets.
--
-- Phase 5a (20260512000006) added logbook.asset_node_id (uuid) alongside the
-- legacy text bridge and back-filled it via the asset_nodes.legacy_asset_id
-- mapping. This migration is the irreversible second half:
--
--   1. CREATE OR REPLACE the v_logbook_truth view so its JOIN uses the new
--      uuid FK column directly instead of the legacy_asset_id text bridge.
--      External shape stays compatible -- consumers of asset_node_id (the
--      column the view already exposes) see the same column from a cleaner
--      source. The l.asset_ref_id passthrough is dropped from the SELECT
--      list; the few readers that pulled this raw text bridge have been
--      migrated this session to read asset_node_id instead.
--
--   2. CREATE OR REPLACE v_asset_truth so its aggregate subqueries (lifetime
--      logbook entries + last_failure_at) join via l.asset_node_id = n.id
--      instead of l.asset_ref_id = n.legacy_asset_id. Same numbers; one less
--      moving part.
--
--   3. Drop the BEFORE INSERT/UPDATE trigger that auto-resolved
--      asset_node_id from asset_ref_id. Writers have been migrated to write
--      asset_node_id directly via the resolveAssetNodeId helper in utils.js.
--      Once asset_ref_id is gone, the trigger has nothing to resolve from.
--
--   4. Drop the legacy FK constraint logbook_asset_ref_id_fkey (to the old
--      assets table) and then drop the column itself.
--
--   5. Drop the supporting index logbook_asset_ref_id_idx.
--
--   6. Update the canonical_sources notes for logbook_truth so the contract
--      reflects asset_node_id (uuid) as the canonical asset reference.
--
-- What this does NOT do:
--   - Drop inventory_items.linked_asset_ids (Phase 5b.2; deferred until the
--     inventory.html asset picker is migrated from `assets` to `asset_nodes`).
--   - Drop the `assets` table itself (still used by the asset wizard +
--     logbook.html / parts-tracker.html asset CRUD).
--   - Drop the Phase 5a trigger on inventory_items (still wanted for
--     auto-maintaining linked_asset_node_ids until 5b.2).
--   - Touch parts_records.asset_ref_id (a different table with its own FK
--     to assets; out of scope for Phase 5b.1).
--
-- Skills consulted: architect (two-phase column drop pattern, view contract
-- stability), data-engineer (single REFRESH-style replacement, BRIN/btree
-- index hygiene), security (FK drop is hive-scoped via inherited RLS;
-- writer pathway preserves cross-tenant isolation via asset_nodes hive_id),
-- maintenance-expert (audit trail of asset identity continuity).

BEGIN;

-- ── 1. v_logbook_truth: join via asset_node_id ─────────────────────────────
-- The new shape drops asset_ref_id from the SELECT list. Postgres rejects
-- a CREATE OR REPLACE VIEW that removes columns, so we DROP first.
--
-- We also retire asset_brain_overview here. It was the May-8 precursor of
-- v_asset_truth and is the only other view that referenced
-- logbook.asset_ref_id. No live code reads it (CANONICAL_SOURCES_AUDIT.md
-- marks it as deprecated wrapper); dropping it now is what allows the
-- ALTER TABLE ... DROP COLUMN below to succeed.
DROP VIEW IF EXISTS public.asset_brain_overview CASCADE;
DROP VIEW IF EXISTS public.v_logbook_truth CASCADE;

CREATE VIEW public.v_logbook_truth AS
SELECT
  -- Core columns (every existing reader's superset).
  l.id, l.hive_id, l.worker_name,
  l.created_at, l.closed_at, l.date, l.status,
  l.maintenance_type, l.category,
  l.machine,
  l.problem, l.action, l.root_cause, l.failure_consequence,
  l.downtime_hours, l.production_output,
  l.parts_used, l.readings_json,
  l.knowledge, l.tasklist_acknowledged, l.tasklist_note,
  l.photo, l.pm_completion_id,
  l.wo_state, l.wo_assigned_to,
  -- Canonical asset reference (uuid). Was previously derived via the legacy
  -- text bridge; now read directly off the logbook row.
  l.asset_node_id,
  n.tag           AS asset_tag,
  n.name          AS asset_node_name,
  n.iso_class     AS asset_iso_class,
  n.criticality   AS asset_criticality,
  n.location      AS asset_location,
  -- Derived: is this a corrective / breakdown event?
  (l.maintenance_type ~* '(corrective|breakdown)') AS is_corrective
FROM public.logbook l
LEFT JOIN public.asset_nodes n
  ON n.id = l.asset_node_id;

COMMENT ON VIEW public.v_logbook_truth IS
  'Canonical logbook reader. Joins asset_nodes via the canonical uuid FK (Phase 5b.1) instead of the legacy text bridge. Asset metadata columns (asset_tag, asset_iso_class, etc.) come from the join. Registered as logbook_truth.';

-- Update the registry notes so the next reviewer knows this is post-Phase-5b.1.
UPDATE public.canonical_sources
SET notes = 'Phase 5b.1 contract: join uses logbook.asset_node_id (uuid) directly. The legacy_asset_id text bridge in asset_nodes is still populated for inventory_items.linked_asset_ids (Phase 5b.2) but not used by this view.',
    contract = jsonb_set(
      contract,
      '{bridge_columns}',
      '["asset_node_id","asset_tag","asset_iso_class","asset_criticality","asset_location"]'::jsonb
    ),
    registered_at = now()
WHERE domain = 'logbook_truth';

-- ── 2. v_asset_truth: aggregate subqueries via asset_node_id ───────────────
-- v_asset_truth keeps the same SELECT shape across phases (no columns
-- removed) so REPLACE is safe here.

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
  n.legacy_asset_id,                              -- bridge kept for 5b.2 readers
  n.pm_asset_id,                                  -- bridge for pm_completions
  n.status,
  n.submitted_by,
  n.approved_by,
  n.approved_at,
  n.created_at,
  n.updated_at,
  -- Aggregate footprint. Phase 5b.1: join via canonical uuid, not legacy text.
  (SELECT count(*) FROM public.logbook l
     WHERE l.hive_id = n.hive_id
       AND l.asset_node_id = n.id) AS lifetime_logbook_entries,
  (SELECT max(l.created_at) FROM public.logbook l
     WHERE l.hive_id = n.hive_id
       AND l.asset_node_id = n.id
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
  'Canonical asset 360. Phase 5b.1: aggregate subqueries join via logbook.asset_node_id (uuid) instead of the legacy text bridge.';

-- ── 3. Drop the Phase 5a trigger (no longer needed) ────────────────────────

DROP TRIGGER IF EXISTS trg_resolve_logbook_asset_node_id ON public.logbook;
DROP FUNCTION IF EXISTS public.resolve_logbook_asset_node_id();

-- ── 4. Drop the legacy FK and column ───────────────────────────────────────

ALTER TABLE public.logbook
  DROP CONSTRAINT IF EXISTS logbook_asset_ref_id_fkey;

-- Drop the supporting index too; nothing reads asset_ref_id any more.
DROP INDEX IF EXISTS public.logbook_asset_ref_id_idx;

ALTER TABLE public.logbook
  DROP COLUMN IF EXISTS asset_ref_id;

-- ── 5. Provenance row so we can see the drop succeeded ─────────────────────

DO $$
DECLARE
  cnt_logbook  bigint;
  cnt_with_node bigint;
BEGIN
  SELECT count(*) INTO cnt_logbook FROM public.logbook;
  SELECT count(*) INTO cnt_with_node FROM public.logbook WHERE asset_node_id IS NOT NULL;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
    INSERT INTO public.automation_log (job_name, status, detail)
    VALUES (
      'phase_5b1_drop_logbook_asset_ref',
      'success',
      format(
        'logbook rows: %s total, %s with asset_node_id populated. asset_ref_id column + FK + index + trigger dropped.',
        cnt_logbook, cnt_with_node
      )
    );
  END IF;
END
$$;

COMMIT;
