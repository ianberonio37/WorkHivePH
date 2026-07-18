---
name: view-v_hive_readiness_truth
type: view
source: db:pg_get_viewdef:v_hive_readiness_truth
source_sha: 4c9b208352a6361d
last_verified: 2026-07-13
supersedes: null
---
## view · `v_hive_readiness_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `hive_readiness`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT DISTINCT ON (hive_id) hive_id, snapshot_date, process_maturity_score, data_quality_score, infrastructure_resilience_score, leadership_engagement_score, cultural_adoption_score, composite_score, current_stair, evidence, blocker_summary, computed_at, model_version FROM hive_readiness ORDER BY hive_id, snapshot_date DESC, computed_at DESC;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
