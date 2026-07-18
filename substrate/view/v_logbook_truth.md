---
name: view-v_logbook_truth
type: view
source: db:pg_get_viewdef:v_logbook_truth
source_sha: 6357b9b4a1e30ee5
last_verified: 2026-07-13
supersedes: null
---
## view · `v_logbook_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `asset_nodes`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT l.id, l.hive_id, l.worker_name, l.created_at, l.closed_at, l.date, l.status, l.maintenance_type, l.category, l.machine, l.problem, l.action, l.root_cause, l.failure_consequence, l.downtime_hours, l.production_output, l.parts_used, l.readings_json, l.knowledge, l.tasklist_acknowledged, l.tasklist_note, l.photo, l.pm_completion_id, l.wo_state, l.wo_assigned_to, l.asset_node_id, n.tag AS asset_tag, n.name AS asset_node_name, n.iso_class AS asset_iso_class, n.criticality AS asset_criticality, n.location AS asset_location, (l.maintenance_type ~* '(corrective|breakdown)'::text) AS is_correct …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
