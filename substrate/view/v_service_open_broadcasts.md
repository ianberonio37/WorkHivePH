---
name: view-v_service_open_broadcasts
type: view
source: db:pg_get_viewdef:v_service_open_broadcasts
source_sha: 5c0ba522d4d5d4c7
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_open_broadcasts`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `service_open_broadcasts_rows`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT request_id, segment, mode, urgency, (budget)::numeric(12,2) AS budget, catalog_item_id, catalog_name, catalog_category, catalog_unit, (catalog_rate)::numeric(12,2) AS catalog_rate, custom_scope, area_hint, broadcast_radius_m, offer_ttl_expires_at, created_at, my_provider_id, distance_km, already_responded FROM service_open_broadcasts_rows() r(request_id, segment, mode, urgency, budget, catalog_item_id, catalog_name, catalog_category, catalog_unit, catalog_rate, custom_scope, area_hint, broadcast_radius_m, offer_ttl_expires_at, created_at, my_provider_id, distance_km, already_responded) …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
