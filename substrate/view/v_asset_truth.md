---
name: view-v_asset_truth
type: view
source: db:pg_get_viewdef:v_asset_truth
source_sha: d13ec41e46d0fb36
last_verified: 2026-07-13
supersedes: null
---
## view · `v_asset_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `asset_edges`, `asset_nodes`, `logbook`, `pm_completions`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id AS asset_id, hive_id, auth_uid, parent_id, level, tag, name, iso_class, criticality, location, manufacturer, model, serial_no, install_date, external_ids, legacy_asset_id, pm_asset_id, status, submitted_by, approved_by, approved_at, created_at, updated_at, ( SELECT count(*) AS count FROM logbook l WHERE ((l.hive_id = n.hive_id) AND (l.asset_node_id = n.id))) AS lifetime_logbook_entries, ( SELECT max(l.created_at) AS max FROM logbook l WHERE ((l.hive_id = n.hive_id) AND (l.asset_node_id = n.id) AND (l.maintenance_type = 'Breakdown / Corrective'::text))) AS last_failure_at, ( SELECT c …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
