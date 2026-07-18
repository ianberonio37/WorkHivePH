---
name: view-v_fmea_truth
type: view
source: db:pg_get_viewdef:v_fmea_truth
source_sha: d76ef3f4e50a96e3
last_verified: 2026-07-13
supersedes: null
---
## view · `v_fmea_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `asset_nodes`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT m.id AS fmea_mode_id, m.hive_id, m.asset_id, n.tag AS asset_tag, n.name AS asset_name, n.iso_class, n.criticality AS asset_criticality, m.function_text, m.failure_mode, m.effect_text, m.cause_text, m.severity, m.occurrence, m.detection, m.rpn, m.consequence_class, m.source, m.ai_confidence, m.created_at, m.updated_at, m.approved_at, m.approved_by FROM (rcm_fmea_modes m LEFT JOIN asset_nodes n ON ((n.id = m.asset_id))) WHERE (m.approved_at IS NOT NULL);

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
