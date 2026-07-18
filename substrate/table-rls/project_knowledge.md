---
name: table-rls-project_knowledge
type: table-rls
source: db:pg_policies+pg_trigger:project_knowledge
source_sha: d2868c69ce55848e
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `project_knowledge` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, project_id, source_type*, source_id, project_code, project_type, discipline, text_chunk*, embedding, created_at*

Policies:
- `project_knowledge_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
