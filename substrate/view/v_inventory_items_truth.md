---
name: view-v_inventory_items_truth
type: view
source: db:pg_get_viewdef:v_inventory_items_truth
source_sha: 5300f0c7510c1d63
last_verified: 2026-07-13
supersedes: null
---
## view · `v_inventory_items_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `inventory_items`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, hive_id, worker_name, part_number, part_name, category, unit, qty_on_hand, min_qty, min_qty AS reorder_point, bin_location, linked_asset_node_ids, notes, photo, status, submitted_by, approved_by, approved_at, created_at, updated_at, (qty_on_hand <= (0)::numeric) AS is_out_of_stock, ((min_qty > (0)::numeric) AND (qty_on_hand <= min_qty)) AS is_low_stock, ((min_qty > (0)::numeric) AND (qty_on_hand <= (min_qty / 2.0))) AS is_critical_low FROM inventory_items i;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
