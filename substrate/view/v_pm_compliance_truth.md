---
name: view-v_pm_compliance_truth
type: view
source: db:pg_get_viewdef:v_pm_compliance_truth
source_sha: d499027669cac501
last_verified: 2026-07-13
supersedes: null
---
## view · `v_pm_compliance_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `pm_completions`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT pa.hive_id, pa.id AS pm_asset_id, pa.asset_name, pa.tag_id, pa.category, pa.criticality, pa.location, pa.last_anchor_date, CASE WHEN (max(pc.completed_at) IS NULL) THEN NULL::integer ELSE ((now())::date - (max(pc.completed_at))::date) END AS days_since_last_completion, count(pc.id) AS lifetime_completions, count(pc.id) FILTER (WHERE (pc.completed_at >= (now() - '30 days'::interval))) AS completions_30d, count(pc.id) FILTER (WHERE (pc.completed_at >= (now() - '90 days'::interval))) AS completions_90d, count(pc.id) FILTER (WHERE (pc.completed_at >= (now() - '365 days'::interval))) AS com …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
