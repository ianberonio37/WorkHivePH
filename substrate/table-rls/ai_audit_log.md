---
name: table-rls-ai_audit_log
type: table-rls
source: db:pg_policies+pg_trigger:ai_audit_log
source_sha: bb700766835039a2
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_audit_log` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, worker_name, event*, payload*, source, created_at

Policies:
- `ai_audit_log_hive_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))`
- `ai_audit_log_hive_select` [SELECT · roles=authenticated] USING=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
