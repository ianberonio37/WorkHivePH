---
name: view-v_anomaly_truth
type: view
source: db:pg_get_viewdef:v_anomaly_truth
source_sha: d837cbf05399c445
last_verified: 2026-07-13
supersedes: null
---
## view · `v_anomaly_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `anomaly_signals`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT DISTINCT ON (hive_id, machine) id, hive_id, snapshot_date, machine, asset_node_id, composite_score, logbook_cluster_score, sensor_zscore_score, pm_drift_score, parts_spend_score, failure_signature_score, source_count, severity, top_reasons, evidence, status, acknowledged_by, acknowledged_at, resolved_by, resolved_at, computed_at, model_version FROM anomaly_signals WHERE (status = ANY (ARRAY['active'::text, 'acknowledged'::text])) ORDER BY hive_id, machine, snapshot_date DESC;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
