---
name: table-rls-ai_quality_escalation
type: table-rls
source: db:pg_policies+pg_trigger:ai_quality_escalation
source_sha: 8a6cbaa8390981a5
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `ai_quality_escalation` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, worker_name, thumbs_down_7d, last_negative_at, reviewed_at, reviewed_by, created_at

Policies:
- `ai_quality_escalation_hive_all` [ALL · roles=authenticated] USING=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))` CHECK=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
