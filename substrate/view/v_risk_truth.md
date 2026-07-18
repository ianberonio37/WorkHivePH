---
name: view-v_risk_truth
type: view
source: db:pg_get_viewdef:v_risk_truth
source_sha: 3ae04845fd538ff0
last_verified: 2026-07-13
supersedes: null
---
## view · `v_risk_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `asset_nodes`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT DISTINCT ON (rs.hive_id, rs.asset_name) n.id AS asset_id, rs.hive_id, rs.asset_name, rs.risk_score, rs.risk_level, rs.health_score, rs.mtbf_days, rs.days_until_failure, rs.top_factors, rs.components, rs.model_version, rs.generated_at FROM (asset_risk_scores rs LEFT JOIN asset_nodes n ON (((n.hive_id = rs.hive_id) AND ((lower(n.tag) = lower(rs.asset_name)) OR (lower(n.name) = lower(rs.asset_name))) AND (n.status = 'approved'::text)))) ORDER BY rs.hive_id, rs.asset_name, rs.generated_at DESC;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
