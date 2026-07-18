---
name: view-v_knowledge_truth
type: view
source: db:pg_get_viewdef:v_knowledge_truth
source_sha: 97a0996f5e61248c
last_verified: 2026-07-13
supersedes: null
---
## view · `v_knowledge_truth`

**security_invoker:** on  (OFF = runs as owner, BYPASSES base-table RLS — cross-hive read-leak risk, mig 001)
**Source tables:** `bom_knowledge`, `calc_knowledge`, `fault_knowledge`, `pm_knowledge`, `project_knowledge`, `skill_knowledge`
**Trust/identity cols exposed:** (none)  (each must be sourced from a CANONICAL/guarded base col, not a forgeable one — mig 009)

**Definition (collapsed):**  SELECT 'fault'::text AS source, fault_knowledge.id, fault_knowledge.hive_id, COALESCE(fault_knowledge.knowledge, fault_knowledge.problem, fault_knowledge.action, ''::text) AS content, fault_knowledge.embedding, fault_knowledge.created_at FROM fault_knowledge UNION ALL SELECT 'skill'::text AS source, skill_knowledge.id, skill_knowledge.hive_id, COALESCE(skill_knowledge.primary_skill, skill_knowledge.discipline, ''::text) AS content, skill_knowledge.embedding, COALESCE(skill_knowledge.updated_at, now()) AS created_at FROM skill_knowledge UNION ALL SELECT 'pm'::text AS source, pm_knowledge.id, p …

Links: [[reference_xhive_view_read_leak_security_invoker]] [[reference_marketplace_listing_trust_forge]]
