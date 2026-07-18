---
name: table-rls-auth_session_events
type: table-rls
source: db:pg_policies+pg_trigger:auth_session_events
source_sha: c25f211ccfbf1055
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `auth_session_events` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, auth_uid, hive_id, worker_name, event_type*, ip, meta

Policies:
- `auth_session_events_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `auth_session_events_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND ((auth.uid() = auth_uid) OR (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = a` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
