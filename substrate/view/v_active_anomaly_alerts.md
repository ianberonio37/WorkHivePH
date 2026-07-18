---
name: view-v_active_anomaly_alerts
type: view
source: db:pg_get_viewdef:v_active_anomaly_alerts
source_sha: 0fdfd0c917d1bc46
last_verified: 2026-07-13
supersedes: null
---
## view · `v_active_anomaly_alerts`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `anomaly_alerts`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, hive_id, asset_id, alert_type, severity, metric_name, metric_value, metric_threshold, deviation_percent, description, action_suggested, detected_at FROM anomaly_alerts WHERE (((suppressed_until IS NULL) OR (suppressed_until < now())) AND (acknowledged_at IS NULL)) ORDER BY CASE WHEN (severity = 'critical'::text) THEN 1 WHEN (severity = 'high'::text) THEN 2 WHEN (severity = 'medium'::text) THEN 3 ELSE 4 END, detected_at DESC;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
