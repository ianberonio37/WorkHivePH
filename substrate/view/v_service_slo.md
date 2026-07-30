---
name: view-v_service_slo
type: view
source: db:pg_get_viewdef:v_service_slo
source_sha: 952b1de6d2f86da3
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_slo`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `r`, `service_requests`, `service_slo_targets`, `t`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  WITH t AS ( SELECT service_slo_targets.sli, service_slo_targets.target, service_slo_targets.comparator, service_slo_targets.unit, service_slo_targets.window_days, service_slo_targets.note, service_slo_targets.updated_at FROM service_slo_targets ), win AS ( SELECT COALESCE(max(t.window_days), 30) AS d FROM t ), r AS ( SELECT service_requests.id, service_requests.client_auth_uid, service_requests.client_worker_name, service_requests.hive_id, service_requests.segment, service_requests.mode, service_requests.catalog_item_id, service_requests.custom_scope, service_requests.address, service_request …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
