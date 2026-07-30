---
name: view-v_service_provider_truth
type: view
source: db:pg_get_viewdef:v_service_provider_truth
source_sha: 33c4d44e5b7d910e
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_provider_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `service_requests`
**Trust/identity cols exposed:** `rating_avg`, `rating_count`, `tier`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT sp.id, sp.provider_type, sp.worker_name, sp.hive_id, sp.display_name, sp.contact, sp.categories, sp.service_areas, sp.base_lat, sp.base_lng, sp.availability, sp.verified, sp.verified_at, sp.created_at, COALESCE(j.completed_jobs, (0)::bigint) AS completed_jobs, rv.rating_avg, COALESCE(rv.rating_count, (0)::bigint) AS rating_count, CASE WHEN ((COALESCE(j.completed_jobs, (0)::bigint) >= 25) AND (COALESCE(rv.rating_avg, (0)::numeric) >= 4.5)) THEN 'gold'::text WHEN (COALESCE(j.completed_jobs, (0)::bigint) >= 10) THEN 'silver'::text ELSE 'bronze'::text END AS tier, 1 AS _source_count, sp.up …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
