---
name: table-rls-automation_log
type: table-rls
source: db:pg_policies+pg_trigger:automation_log
source_sha: e1bdb9fe599c8303
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `automation_log` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, job_name*, hive_id, triggered_at, status, detail

Policies:
- `automation_log_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE ((hive_members.auth_uid ` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
