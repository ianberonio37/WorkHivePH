---
name: table-rls-wh_health_status
type: table-rls
source: db:pg_policies+pg_trigger:wh_health_status
source_sha: dcee4acf548ff24d
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `wh_health_status` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): surface*, status*, latency_ms, detail, updated_at*

Policies:
- `wh_health_service_all` [ALL · roles=service_role] USING=`true` CHECK=`true`
- `wh_health_public_read` [SELECT · roles=anon,authenticated] USING=`true` CHECK=`∅`

**Verdict:** FLAGS: wh_health_public_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
