---
name: table-rls-fault_knowledge
type: table-rls
source: db:pg_policies+pg_trigger:fault_knowledge
source_sha: 5654184a24e0847f
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `fault_knowledge` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, logbook_id, machine, category, problem, root_cause, action, knowledge, worker_name, embedding, created_at, embedding_model, maintenance_type

Policies:
- `fault_knowledge_delete_locked` [DELETE · roles=public] USING=`false` CHECK=`∅`
- `fault_knowledge_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `fault_knowledge_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`
- `fault_knowledge_update_locked` [UPDATE · roles=public] USING=`false` CHECK=`false`

Guard triggers: `trg_daily_cap_fault_knowledge`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
