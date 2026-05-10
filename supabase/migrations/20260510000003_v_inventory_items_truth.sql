-- ─── v_inventory_items_truth canonical view ──────────────────────────────────
-- Truth-scattering fix for the inventory_items hotspot. validate_silo_monitor
-- flagged this as the largest unregistered hotspot (16 distinct consumer
-- files) after logbook was promoted. The view does three things:
--
-- 1. Aliases min_qty as reorder_point. Multiple consumers query for a
--    `reorder_point` column that does NOT exist on the underlying table —
--    they were silently getting null and treating low-stock as never. This
--    bug stays latent in the schema; the view papers over it cleanly so
--    every consumer gets a usable value.
-- 2. Bakes in is_out_of_stock / is_low_stock / is_critical_low derived flags
--    that ~10 pages reimplement client-side. The same threshold rules
--    everywhere, in one place.
-- 3. Provides a stable column set so future schema additions don't ripple.

CREATE OR REPLACE VIEW public.v_inventory_items_truth AS
SELECT
  i.id, i.hive_id, i.worker_name,
  i.part_number, i.part_name, i.category, i.unit,
  i.qty_on_hand,
  i.min_qty,
  i.min_qty                                             AS reorder_point,
  i.bin_location, i.linked_asset_ids, i.notes, i.photo,
  i.status, i.submitted_by, i.approved_by, i.approved_at,
  i.created_at, i.updated_at,
  -- Derived flags consolidate the three thresholds consumers reimplement.
  (i.qty_on_hand <= 0)                                  AS is_out_of_stock,
  (i.min_qty > 0 AND i.qty_on_hand <= i.min_qty)        AS is_low_stock,
  (i.min_qty > 0 AND i.qty_on_hand <= i.min_qty / 2.0)  AS is_critical_low
FROM public.inventory_items i;

GRANT SELECT ON public.v_inventory_items_truth TO anon, authenticated;

COMMENT ON VIEW public.v_inventory_items_truth IS
  'Canonical inventory_items view: every column + reorder_point alias for min_qty + is_out_of_stock / is_low_stock / is_critical_low derived flags. Registered in canonical_sources as inventory_items_truth.';

-- ─── Register inventory_items_truth in canonical_sources ──────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('inventory_items_truth', 'view', 'v_inventory_items_truth', 'data-engineer', 'realtime',
   'Canonical inventory items reader. Carries every inventory_items column plus reorder_point as an alias for min_qty (some consumers query a reorder_point column that does not exist on the underlying table). Bakes in is_out_of_stock / is_low_stock / is_critical_low derived boolean flags so the same threshold logic does not get reimplemented across 10+ pages.',
   jsonb_build_object(
     'key',          jsonb_build_array('id'),
     'hive_scoped',  true,
     'soft_delete',  false,
     'aliased_columns',  jsonb_build_object('reorder_point', 'min_qty'),
     'derived_columns',  jsonb_build_array('is_out_of_stock','is_low_stock','is_critical_low'),
     'standards',    jsonb_build_array('SMRP', 'ISO 14224')
   ),
   'reorder_point alias is a backward-compat band-aid; the underlying table has no such column. Future cleanup: rename min_qty -> reorder_point on the table and drop the alias here.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes;
