---
name: table-rls-ai_knowledge_gap
type: table-rls
source: db:pg_policies+pg_trigger:ai_knowledge_gap
source_sha: 6dbd3f09b7370a57
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_knowledge_gap` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, worker_name, question*, reason, topic, created_at

Policies:
- `ai_knowledge_gap_hive_all` [ALL · roles=authenticated] USING=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))` CHECK=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
