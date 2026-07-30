---
name: view-v_service_open_broadcasts
type: view
source: db:pg_get_viewdef:v_service_open_broadcasts
source_sha: f1cab4daca1cd04a
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_open_broadcasts`

**security_invoker:** OFF ⚠  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `auth`, `service_catalog`, `service_offers`, `service_providers`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT r.id AS request_id, r.segment, r.mode, r.urgency, r.budget, r.catalog_item_id, c.name AS catalog_name, c.category AS catalog_category, c.unit AS catalog_unit, c.base_rate AS catalog_rate, r.custom_scope, split_part(COALESCE(r.address, ''::text), ','::text, 1) AS area_hint, r.broadcast_radius_m, r.offer_ttl_expires_at, r.created_at, sp.id AS my_provider_id, round(((st_distance(r.location, sp.base_location) / (1000.0)::double precision))::numeric, 1) AS distance_km, (EXISTS ( SELECT 1 FROM service_offers o WHERE ((o.request_id = r.id) AND (o.provider_id = sp.id)))) AS already_responded F …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
