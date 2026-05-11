-- Phase 5b.2: Drop inventory_items.linked_asset_ids (text[]).
--
-- The last text-keyed asset bridge on the platform. Phase 5a added
-- linked_asset_node_ids (uuid[]) alongside and kept it populated via a
-- BEFORE INSERT/UPDATE trigger. This migration completes the cut-over:
--
--   1. CREATE OR REPLACE v_inventory_items_truth: select
--      linked_asset_node_ids instead of linked_asset_ids. The view's
--      external column linked_asset_ids is renamed to
--      linked_asset_node_ids; consumers were migrated this session.
--
--   2. DROP TRIGGER trg_resolve_inventory_linked_asset_node_ids + its
--      function. Writers now produce linked_asset_node_ids directly via
--      the asset_id <-> asset_node_id maps maintained in inventory.html
--      (built once per page load from asset_nodes.tag + .legacy_asset_id).
--
--   3. ALTER TABLE inventory_items DROP COLUMN linked_asset_ids.
--
--   4. Update canonical_sources notes for inventory_items_truth so the
--      contract reflects the new column name + the dropped alias.
--
-- What this does NOT do:
--   - Touch the `assets` table or asset_nodes (both still in use for the
--     wizard, picker, and trigger-maintained bridge columns).
--   - Drop parts_records.asset_ref_id (different table, separate FK).
--
-- Skills consulted: architect (column-rename via view-replace pattern,
-- two-phase drop completion), data-engineer (CREATE OR REPLACE VIEW
-- compatibility, derived-column preservation), multitenant-engineer
-- (writer-side resolution already hive-scoped via _buildAssetNodeMaps).

BEGIN;

-- ── 1. v_inventory_items_truth: linked_asset_node_ids replaces linked_asset_ids ──

CREATE OR REPLACE VIEW public.v_inventory_items_truth AS
SELECT
  i.id, i.hive_id, i.worker_name,
  i.part_number, i.part_name, i.category, i.unit,
  i.qty_on_hand,
  i.min_qty,
  i.min_qty                                             AS reorder_point,
  i.bin_location,
  i.linked_asset_node_ids,                              -- Phase 5b.2 canonical
  i.notes, i.photo,
  i.status, i.submitted_by, i.approved_by, i.approved_at,
  i.created_at, i.updated_at,
  -- Derived flags consolidate the three thresholds consumers reimplement.
  (i.qty_on_hand <= 0)                                  AS is_out_of_stock,
  (i.min_qty > 0 AND i.qty_on_hand <= i.min_qty)        AS is_low_stock,
  (i.min_qty > 0 AND i.qty_on_hand <= i.min_qty / 2.0)  AS is_critical_low
FROM public.inventory_items i;

COMMENT ON VIEW public.v_inventory_items_truth IS
  'Canonical inventory_items view: every column + reorder_point alias + canonical asset linkage via linked_asset_node_ids (uuid[]). Phase 5b.2 (2026-05-12) replaced the legacy text bridge linked_asset_ids with the uuid array; the view no longer exposes the legacy column.';

-- Update registry notes for the new contract.
UPDATE public.canonical_sources
SET notes = 'Phase 5b.2 contract: linked_asset_node_ids (uuid[]) replaces linked_asset_ids (text[]). reorder_point alias for min_qty stays. Future cleanup: rename min_qty -> reorder_point on the table and drop the alias.',
    contract = jsonb_set(
      jsonb_set(
        contract,
        '{aliased_columns}',
        '{"reorder_point": "min_qty", "linked_asset_node_ids": "canonical asset_node uuid[]"}'::jsonb
      ),
      '{derived_columns}',
      '["is_out_of_stock","is_low_stock","is_critical_low"]'::jsonb
    ),
    registered_at = now()
WHERE domain = 'inventory_items_truth';

-- ── 2. Drop the Phase 5a trigger (no longer needed) ────────────────────────

DROP TRIGGER IF EXISTS trg_resolve_inventory_linked_asset_node_ids ON public.inventory_items;
DROP FUNCTION IF EXISTS public.resolve_inventory_linked_asset_node_ids();

-- ── 3. Drop the legacy text column ─────────────────────────────────────────

ALTER TABLE public.inventory_items
  DROP COLUMN IF EXISTS linked_asset_ids;

-- ── 4. Provenance row ──────────────────────────────────────────────────────

DO $$
DECLARE
  cnt_inv_total       bigint;
  cnt_with_uuid_links bigint;
BEGIN
  SELECT count(*) INTO cnt_inv_total FROM public.inventory_items;
  SELECT count(*) INTO cnt_with_uuid_links
    FROM public.inventory_items
    WHERE array_length(linked_asset_node_ids, 1) > 0;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'automation_log') THEN
    INSERT INTO public.automation_log (job_name, status, detail)
    VALUES (
      'phase_5b2_drop_inventory_linked_asset_ids',
      'success',
      format(
        'inventory_items rows: %s total, %s with linked_asset_node_ids populated. linked_asset_ids column + trigger dropped.',
        cnt_inv_total, cnt_with_uuid_links
      )
    );
  END IF;
END
$$;

COMMIT;
