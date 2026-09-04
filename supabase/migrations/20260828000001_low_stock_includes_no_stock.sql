-- T19: an item that has RUN OUT was not counted as low stock (2026-08-28)
--
-- v_inventory_items_truth defined:
--     is_low_stock = min_qty > 0 AND qty_on_hand <= min_qty
--
-- The `min_qty > 0` guard is there for a good reason: without a reorder point there is no
-- threshold to be under, and flagging every such item would make the signal useless. But it also
-- excludes the worst case it should include — an item at qty_on_hand = 0 whose min_qty was never
-- set. That item is out of stock by the view's own is_out_of_stock, and simultaneously NOT low.
--
-- MEASURED on the Baguio fixture, one item moved to qty 0 with no reorder point, inside a
-- transaction that rolled back:
--     before : is_low_stock 3 · is_out_of_stock 0 · out|low|critical 3
--     after  : is_low_stock 3 · is_out_of_stock 1 · out|low|critical 4
-- The supervisor's ops-home tile reads is_low_stock, so it stayed at 3 while inventory's "below"
-- band read 4. A part that had actually run out was invisible on the triage surface whose entire
-- job is showing what needs attention.
--
-- ★AND IT COMPOUNDED, because get_hive_dashboard derives the tile's OUT-OF-STOCK breakdown by
-- filtering its low_stock_items array (qty_on_hand <= 0 over rows already filtered to
-- is_low_stock). An item excluded from low_stock_items is therefore missing from the out-of-stock
-- count as well — so the one number that should have caught it could not, by construction.
--
-- Fixed at the DEFINITION rather than at the tile: index reads it two ways (the RPC in hive mode,
-- the view directly in solo/fallback) and inventory, hive, alert-hub, logbook, the ai-gateway and
-- two psql probes read it too. Fixing one caller would have left every other caller wrong, which
-- is the sibling-fix trap this codebase keeps meeting.
--
-- The guard is KEPT for every item that has stock: no reorder point still means not-low at any
-- positive quantity. Only zero is unconditional, because zero needs no threshold to be bad.
--
-- ★THE COLUMN LIST IS REPRODUCED EXACTLY, and that is not ceremony. The first draft of this
-- migration wrote `SELECT i.*` plus the three flags, which would have dropped `min_qty AS
-- reorder_point` — an alias index.html selects BY NAME — and reordered the rest. Reading the whole
-- view before replacing it is the difference between a one-expression change and a broken page.
--
-- security_invoker is re-declared because CREATE OR REPLACE VIEW DROPS it, and a truth view that
-- silently reverts to owner-rights stops enforcing RLS on every reader.

CREATE OR REPLACE VIEW v_inventory_items_truth
WITH (security_invoker = true)
AS
  SELECT id,
    hive_id,
    worker_name,
    part_number,
    part_name,
    category,
    unit,
    qty_on_hand,
    min_qty,
    min_qty AS reorder_point,
    bin_location,
    linked_asset_node_ids,
    notes,
    photo,
    status,
    submitted_by,
    approved_by,
    approved_at,
    created_at,
    updated_at,
    qty_on_hand <= 0::numeric AS is_out_of_stock,
    -- CHANGED (and the only change): zero stock is low stock, reorder point or not.
    qty_on_hand <= 0::numeric
      OR (min_qty > 0::numeric AND qty_on_hand <= min_qty) AS is_low_stock,
    min_qty > 0::numeric AND qty_on_hand <= (min_qty / 2.0) AS is_critical_low,
    lead_time_days,
    rejection_reason
   FROM inventory_items i;
