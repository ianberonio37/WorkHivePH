---
name: view-v_sensor_recent
type: view
source: db:pg_get_viewdef:v_sensor_recent
source_sha: af93901ec5d0e79a
last_verified: 2026-07-13
supersedes: null
---
## view · `v_sensor_recent`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `asset_nodes`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT sr.id, sr.hive_id, sr.asset_id, sr.parameter, sr.value, sr.recorded_at, sr.source, sr.meta, n.tag AS asset_tag, n.name AS asset_name, n.iso_class FROM (sensor_readings sr LEFT JOIN asset_nodes n ON ((n.id = sr.asset_id))) WHERE (sr.recorded_at >= (now() - '30 days'::interval));

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
