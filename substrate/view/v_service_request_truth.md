---
name: view-v_service_request_truth
type: view
source: db:pg_get_viewdef:v_service_request_truth
source_sha: 8a7993582404db3b
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_request_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `hive_members`, `service_catalog`, `service_offers`, `service_providers`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT r.id, r.client_auth_uid, r.client_worker_name, r.hive_id, r.segment, r.mode, r.catalog_item_id, c.name AS catalog_name, c.category AS catalog_category, c.unit AS catalog_unit, c.base_rate AS catalog_rate, r.custom_scope, r.address, r.urgency, r.budget, r.status, r.matched_provider_id, sp.display_name AS provider_name, sp.contact AS provider_contact, sp.availability AS provider_availability, r.broadcast_radius_m, r.offer_ttl_expires_at, r.accepted_at, r.en_route_at, r.on_site_at, r.in_progress_at, r.completed_at, r.settled_at, r.cancelled_at, r.created_at, r.updated_at, ( SELECT count(* …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
