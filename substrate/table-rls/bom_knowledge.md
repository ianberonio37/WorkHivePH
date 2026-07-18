---
name: table-rls-bom_knowledge
type: table-rls
source: db:pg_policies+pg_trigger:bom_knowledge
source_sha: 82789e09a93d173d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `bom_knowledge` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, project_name, calc_type, key_spec, item_count, notes, embedding, created_at

Policies:
- `bom_knowledge_hive_rw` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT user_hive_ids() AS user_hive_ids)))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
