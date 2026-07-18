---
name: view-v_inventory_transactions_truth
type: view
source: db:pg_get_viewdef:v_inventory_transactions_truth
source_sha: 0b5d722a1df0bfe2
last_verified: 2026-07-13
supersedes: null
---
## view · `v_inventory_transactions_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `inventory_items`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT t.id, t.hive_id, t.worker_name, t.auth_uid, t.item_id, t.type, t.qty_change, t.qty_after, t.note, t.job_ref, t.created_at, i.part_name AS item_part_name, i.part_number AS item_part_number, i.category AS item_category, i.unit AS item_unit, (t.type = 'consume'::text) AS is_consume, (t.type = 'restock'::text) AS is_restock, (t.type = 'adjust'::text) AS is_adjust, CASE WHEN (t.type = 'consume'::text) THEN (- abs(t.qty_change)) ELSE abs(t.qty_change) END AS qty_delta FROM (inventory_transactions t LEFT JOIN inventory_items i ON ((i.id = t.item_id)));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
