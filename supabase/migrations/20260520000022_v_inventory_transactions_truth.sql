-- ─── v_inventory_transactions_truth canonical view ──────────────────────────
-- Turn 4 of the canonical-drift flywheel (2026-05-20). #1 gap table after
-- the L-1.5 miner's scope expanded to edge functions in turn 3:
-- inventory_transactions had 6 raw reads.
--
-- Bridges to inventory_items for part_name + qty bridges, and derives
-- is_consume / is_restock flags so consumers can drop the type-string
-- scatter. Also derives sign-aware qty_delta (negative for consume) so
-- the type column doesn't have to be re-interpreted client-side.

DROP VIEW IF EXISTS public.v_inventory_transactions_truth;

CREATE VIEW public.v_inventory_transactions_truth AS
SELECT
  t.id,
  t.hive_id,
  t.worker_name,
  t.auth_uid,
  t.item_id,
  t.type,
  t.qty_change,
  t.qty_after,
  t.note,
  t.job_ref,
  t.created_at,
  -- Bridge to inventory_items for displayable name + category
  i.part_name      AS item_part_name,
  i.part_number    AS item_part_number,
  i.category       AS item_category,
  i.unit           AS item_unit,
  -- Derived flags
  (t.type = 'consume') AS is_consume,
  (t.type = 'restock') AS is_restock,
  (t.type = 'adjust')  AS is_adjust,
  CASE WHEN t.type = 'consume' THEN -ABS(t.qty_change)
       ELSE                            ABS(t.qty_change)
  END AS qty_delta
FROM public.inventory_transactions t
LEFT JOIN public.inventory_items i ON i.id = t.item_id;

GRANT SELECT ON public.v_inventory_transactions_truth TO anon, authenticated;

COMMENT ON VIEW public.v_inventory_transactions_truth IS
  'Canonical inventory_transactions reader. Bridges item_part_name/number/category/unit from inventory_items + derived is_consume/is_restock/is_adjust + sign-aware qty_delta.';

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('inventory_transactions_truth', 'view', 'v_inventory_transactions_truth', 'data-engineer', 'realtime',
   'Canonical inventory_transactions reader. Per-row granularity with item bridge (part_name/number/category/unit) and derived type flags + signed qty_delta.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('item_part_name','item_part_number','item_category','item_unit'),
     'derived_columns', jsonb_build_array('is_consume','is_restock','is_adjust','qty_delta')
   ),
   'Turn 4 of TIER C gap-table sweep (2026-05-20). 6 raw reads at baseline.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind, source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill, freshness = EXCLUDED.freshness,
      description = EXCLUDED.description, contract = EXCLUDED.contract,
      notes       = EXCLUDED.notes;
