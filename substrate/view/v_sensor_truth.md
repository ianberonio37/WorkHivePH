---
name: view-v_sensor_truth
type: view
source: db:pg_get_viewdef:v_sensor_truth
source_sha: b39d7ba26daa1b92
last_verified: 2026-07-13
supersedes: null
---
## view · `v_sensor_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `sensor_readings`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT DISTINCT ON (hive_id, asset_id, parameter) id AS reading_id, hive_id, asset_id, parameter, value, unit, quality_flag, recorded_at, source, (quality_flag = 'ANOMALY'::text) AS is_anomaly FROM sensor_readings s ORDER BY hive_id, asset_id, parameter, recorded_at DESC;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
