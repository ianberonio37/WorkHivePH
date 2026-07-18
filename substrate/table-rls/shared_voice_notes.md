---
name: table-rls-shared_voice_notes
type: table-rls
source: db:pg_policies+pg_trigger:shared_voice_notes
source_sha: 312344f1c86b71de
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `shared_voice_notes` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, thread_key*, worker_name, content*, source, created_at

Policies:
- `shared_voice_notes_hive_all` [ALL · roles=authenticated] USING=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))` CHECK=`(hive_id IN ( SELECT hive_members.hive_id FROM hive_members WHERE (hive_members.auth_uid = auth.uid())))`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
