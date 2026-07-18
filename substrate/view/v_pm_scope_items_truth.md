---
name: view-v_pm_scope_items_truth
type: view
source: db:pg_get_viewdef:v_pm_scope_items_truth
source_sha: 31c462f6d8240a71
last_verified: 2026-07-13
supersedes: null
---
## view · `v_pm_scope_items_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `LATERAL`, `pm_assets`, `pm_completions`, `s`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT scope_item_id, scope_item_id AS id, hive_id, pm_asset_id, pm_asset_id AS asset_id, item_text, frequency, anchor_date, is_custom, created_at, asset_name, asset_tag, asset_category, asset_criticality, asset_location, frequency_days, last_completed_at, last_completed_by, next_due_date, (next_due_date - CURRENT_DATE) AS days_until_due, (next_due_date < CURRENT_DATE) AS is_overdue, ((next_due_date >= CURRENT_DATE) AND (next_due_date <= ((CURRENT_DATE + '14 days'::interval))::date)) AS is_due_soon FROM ( SELECT base.scope_item_id, base.hive_id, base.pm_asset_id, base.item_text, base.frequenc …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
