---
name: table-rls-companion_handoff
type: table-rls
source: db:pg_policies+pg_trigger:companion_handoff
source_sha: fb522aa595222145
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `companion_handoff` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, from_worker, to_worker, message, status, source, created_at

Policies:
- `companion_handoff_hive_all` [ALL · roles=authenticated] USING=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))` CHECK=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
