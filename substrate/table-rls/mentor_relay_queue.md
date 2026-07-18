---
name: table-rls-mentor_relay_queue
type: table-rls
source: db:pg_policies+pg_trigger:mentor_relay_queue
source_sha: 745a118b0e1273a4
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `mentor_relay_queue` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, from_worker, question*, status, answer, answered_by, answered_at, source, created_at

Policies:
- `mentor_relay_queue_hive_all` [ALL · roles=authenticated] USING=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))` CHECK=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
