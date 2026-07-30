---
name: view-v_service_job_tracking
type: view
source: db:pg_get_viewdef:v_service_job_tracking
source_sha: 64249a7d1d3b54ec
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_job_tracking`

**security_invoker:** OFF ⚠  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `hive_members`, `service_providers`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT r.id AS request_id, r.status, sp.id AS provider_id, sp.display_name AS provider_name, st_y((sp.live_location)::geometry) AS live_lat, st_x((sp.live_location)::geometry) AS live_lng, st_y((r.location)::geometry) AS request_lat, st_x((r.location)::geometry) AS request_lng, sp.updated_at AS location_updated_at FROM (service_requests r JOIN service_providers sp ON ((sp.id = r.matched_provider_id))) WHERE ((r.status = ANY (ARRAY['en_route'::text, 'on_site'::text, 'in_progress'::text])) AND ((r.client_auth_uid = auth.uid()) OR ((r.hive_id IS NOT NULL) AND (r.hive_id IN ( SELECT hm.hive_id FR …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
