---
name: view-v_alert_truth
type: view
source: db:pg_get_viewdef:v_alert_truth
source_sha: b24423068f6b7a2f
last_verified: 2026-07-13
supersedes: null
---
## view · `v_alert_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `anomaly_signals`, `failure_signature_alerts`, `jsonb_array_elements_text`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT fsa.id AS alert_id, fsa.hive_id, NULL::uuid AS asset_id, fsa.machine, 'signature'::text AS alert_kind, CASE WHEN (fsa.severity = 'critical'::text) THEN 'critical'::text WHEN (fsa.severity = 'warning'::text) THEN 'high'::text WHEN (fsa.severity = 'info'::text) THEN 'low'::text ELSE COALESCE(fsa.severity, 'info'::text) END AS severity, fsa.alert_title AS title, fsa.alert_detail AS detail, fsa.rule_id, fsa.category, fsa.detected_at, fsa.status, fsa.evidence FROM failure_signature_alerts fsa WHERE (fsa.status = ANY (ARRAY['active'::text, 'acknowledged'::text])) UNION ALL SELECT ans.id AS a …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
