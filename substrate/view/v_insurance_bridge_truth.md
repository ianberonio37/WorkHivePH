---
name: view-v_insurance_bridge_truth
type: view
source: db:pg_get_viewdef:v_insurance_bridge_truth
source_sha: 89bb97c11f4d09f7
last_verified: 2026-07-13
supersedes: null
---
## view · `v_insurance_bridge_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `LATERAL`, `anomaly_signals`, `hive_adoption_score`, `hive_readiness`
**Trust/identity cols exposed:** `adoption_risk_tier`  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT h.id AS hive_id, h.name AS hive_name, hr.composite_score AS readiness_score, hr.current_stair AS maturity_stair, has.risk_score AS adoption_risk_score, has.risk_tier AS adoption_risk_tier, ( SELECT count(*) AS count FROM anomaly_signals an WHERE ((an.hive_id = h.id) AND (an.status = 'active'::text) AND (an.severity = ANY (ARRAY['warning'::text, 'critical'::text])))) AS active_warning_count, ( SELECT count(*) AS count FROM anomaly_signals an WHERE ((an.hive_id = h.id) AND (an.status = 'active'::text) AND (an.severity = 'critical'::text))) AS active_critical_count, (GREATEST((0)::bigint, …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
