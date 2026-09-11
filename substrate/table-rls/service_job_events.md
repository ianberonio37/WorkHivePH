---
name: table-rls-service_job_events
type: table-rls
source: db:pg_policies+pg_trigger:service_job_events
source_sha: 59d164896b9faaae
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_job_events` — RLS posture (platform table — no hive_id or auth_uid)

RLS enabled: **True** · has hive_id: False · has auth_uid: False

Columns (*=NOT NULL): id*, request_id*, actor_uid, actor_role, from_state, to_state*, note, created_at*

Policies:
- `service_job_events_party_read` [SELECT · roles=authenticated] USING=`(request_id IN ( SELECT r.id FROM service_requests r))` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
