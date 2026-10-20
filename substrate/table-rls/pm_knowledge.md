---
name: table-rls-pm_knowledge
type: table-rls
source: db:pg_policies+pg_trigger:pm_knowledge
source_sha: 84bb672b212222fc
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `pm_knowledge` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, asset_id, asset_name, category, overdue_count, last_completed, health_summary, embedding, updated_at, worker_name, embedding_model, created_at*

Policies:
- `pm_knowledge_delete_locked` [DELETE · roles=public] USING=`false` CHECK=`∅`
- `pm_knowledge_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `pm_knowledge_read` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid ` CHECK=`∅`
- `pm_knowledge_update_locked` [UPDATE · roles=public] USING=`false` CHECK=`false`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
