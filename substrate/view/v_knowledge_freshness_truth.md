---
name: view-v_knowledge_freshness_truth
type: view
source: db:pg_get_viewdef:v_knowledge_freshness_truth
source_sha: 34f87cca4914bb37
last_verified: 2026-07-13
supersedes: null
---
## view · `v_knowledge_freshness_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `fault_knowledge`, `pm_knowledge`, `skill_knowledge`, `src`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  WITH src AS ( SELECT 'fault'::text AS kind, fault_knowledge.hive_id, (fault_knowledge.embedding IS NOT NULL) AS embedded, fault_knowledge.created_at FROM fault_knowledge UNION ALL SELECT 'skill'::text AS kind, skill_knowledge.hive_id, (skill_knowledge.embedding IS NOT NULL) AS embedded, skill_knowledge.created_at FROM skill_knowledge UNION ALL SELECT 'pm'::text AS kind, pm_knowledge.hive_id, (pm_knowledge.embedding IS NOT NULL) AS embedded, pm_knowledge.created_at FROM pm_knowledge ) SELECT hive_id, kind, (count(*))::integer AS total_rows, (count(*) FILTER (WHERE embedded))::integer AS embedd …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
