---
name: table-rls-fault_knowledge
type: table-rls
source: db:pg_policies+pg_trigger:fault_knowledge
source_sha: 06cf1fc72e696d9e
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `fault_knowledge` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, logbook_id, machine, category, problem, root_cause, action, knowledge, worker_name, embedding, created_at, embedding_model, maintenance_type, source*, ai_model, ai_confidence, auth_uid, ai_assisted_fields*

Policies:
- `fault_knowledge_delete_locked` [DELETE · roles=public] USING=`false` CHECK=`∅`
- `fault_knowledge_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `fault_knowledge_read` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (((hive_id IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_mem` CHECK=`∅`
- `fault_knowledge_update_locked` [UPDATE · roles=public] USING=`false` CHECK=`false`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
