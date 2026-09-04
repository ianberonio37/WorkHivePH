---
name: view-v_pm_scope_items_truth
type: view
source: db:pg_get_viewdef:v_pm_scope_items_truth
source_sha: 883e65877196fc10
last_verified: 2026-07-13
supersedes: null
---
## view · `v_pm_scope_items_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `LATERAL`, `asset_nodes`, `pm_assets`, `pm_completions`, `s`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT scope_item_id, scope_item_id AS id, hive_id, pm_asset_id, pm_asset_id AS asset_id, item_text, frequency, anchor_date, is_custom, created_at, asset_name, asset_tag, asset_category, asset_criticality, asset_location, frequency_days, last_completed_at, last_completed_by, next_due_date, (next_due_date - CURRENT_DATE) AS days_until_due, ( CASE WHEN (interval_kind <> 'meter'::text) THEN (next_due_date < CURRENT_DATE) ELSE false END OR ((interval_km IS NOT NULL) AND (current_km IS NOT NULL) AND (current_km >= next_due_km))) AS is_overdue, ( CASE WHEN (interval_kind <> 'meter'::text) THEN ((ne …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
