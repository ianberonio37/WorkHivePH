---
name: view-v_service_provider_leaderboard
type: view
source: db:pg_get_viewdef:v_service_provider_leaderboard
source_sha: 7fefdb21d8d3da18
last_verified: 2026-07-13
supersedes: null
---
## view · `v_service_provider_leaderboard`

**security_invoker:** OFF ⚠  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `v_service_provider_truth`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id, display_name, categories, service_areas, verified, completed_jobs, rating_avg, rating_count, tier, rank() OVER (ORDER BY completed_jobs DESC, COALESCE(rating_avg, (0)::numeric) DESC, display_name) AS rank, 1 AS _source_count, _freshness_ts, 'service_leaderboard:v1'::text AS _canonical_version FROM v_service_provider_truth t WHERE (completed_jobs > 0);

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
