---
name: view-v_hive_value_summary
type: view
source: db:pg_get_viewdef:v_hive_value_summary
source_sha: 94603f46bc68cf85
last_verified: 2026-07-13
supersedes: null
---
## view · `v_hive_value_summary`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `fault_knowledge`, `hives`, `logbook`, `pm_completions`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT id AS hive_id, name AS hive_name, ( SELECT count(*) AS count FROM pm_completions pc WHERE ((pc.hive_id = h.id) AND (pc.status = 'done'::text))) AS pms_kept, ( SELECT count(*) AS count FROM logbook lb WHERE ((lb.hive_id = h.id) AND (lb.status = 'Closed'::text))) AS faults_resolved, ( SELECT count(*) AS count FROM fault_knowledge fk WHERE (fk.hive_id = h.id)) AS knowledge_written FROM hives h;

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
