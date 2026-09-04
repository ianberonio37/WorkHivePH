-- T20 (2026-08-25): the approval queue's Reject wrote status='rejected' with no WHY on parts.
-- asset_nodes already carries rejection_reason (asset-hub captures + renders it to the submitter);
-- inventory_items had nowhere to put one, so the refused party learned nothing. Additive, re-runnable.
alter table inventory_items add column if not exists rejection_reason text;

-- The page reads v_inventory_items_truth (select *), so the reason must ride the truth view too.
create or replace view v_inventory_items_truth as
 SELECT id, hive_id, worker_name, part_number, part_name, category, unit,
    qty_on_hand, min_qty, min_qty AS reorder_point, bin_location,
    linked_asset_node_ids, notes, photo, status, submitted_by, approved_by,
    approved_at, created_at, updated_at,
    qty_on_hand <= 0::numeric AS is_out_of_stock,
    min_qty > 0::numeric AND qty_on_hand <= min_qty AS is_low_stock,
    min_qty > 0::numeric AND qty_on_hand <= (min_qty / 2.0) AS is_critical_low,
    lead_time_days,
    rejection_reason
   FROM inventory_items i;

-- CREATE OR REPLACE VIEW resets reloptions: the recreation above silently DROPPED security_invoker,
-- turning the truth view owner-rights (an RLS bypass) - caught by the db-adoption D4 floor (58->57).
alter view v_inventory_items_truth set (security_invoker = true);
