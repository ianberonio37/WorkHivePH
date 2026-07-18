---
name: view-v_audit_unified
type: view
source: db:pg_get_viewdef:v_audit_unified
source_sha: 2869bad83dd16f8c
last_verified: 2026-07-13
supersedes: null
---
## view · `v_audit_unified`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `automation_log`, `cmms_audit_log`, `gateway_audit_log`, `hive_audit_log`
**Trust/identity cols exposed:** `worker_name`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT 'hive'::text AS audit_source, (hive_audit_log.id)::text AS audit_id, hive_audit_log.hive_id, hive_audit_log.actor AS worker_name, hive_audit_log.action, hive_audit_log.target_type, hive_audit_log.target_id, COALESCE(hive_audit_log.meta, '{}'::jsonb) AS payload, hive_audit_log.created_at FROM hive_audit_log UNION ALL SELECT 'cmms'::text AS audit_source, (cmms_audit_log.id)::text AS audit_id, cmms_audit_log.hive_id, cmms_audit_log.triggered_by AS worker_name, cmms_audit_log.operation AS action, cmms_audit_log.entity_type AS target_type, cmms_audit_log.batch_id AS target_id, jsonb_build_o …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
