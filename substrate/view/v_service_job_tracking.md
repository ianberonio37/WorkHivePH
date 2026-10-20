---
name: view-v_service_job_tracking
type: view
source: db:pg_get_viewdef:v_service_job_tracking
source_sha: 155fe027f427ff1d
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_job_tracking`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `service_job_tracking_rows`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT request_id, status, provider_id, provider_name, live_lat, live_lng, request_lat, request_lng, location_updated_at FROM service_job_tracking_rows() r(request_id, status, provider_id, provider_name, live_lat, live_lng, request_lat, request_lng, location_updated_at);

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
