---
name: view-v_service_catalog_truth
type: view
source: db:pg_get_viewdef:v_service_catalog_truth
source_sha: 076d270a76519972
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_catalog_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `service_catalog`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, segment, category, name, description, unit, base_rate, active, created_at, updated_at, 1 AS _source_count, updated_at AS _freshness_ts, 'service_catalog_truth:v1'::text AS _canonical_version, requires_cert_level FROM service_catalog c WHERE (active = true);

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
