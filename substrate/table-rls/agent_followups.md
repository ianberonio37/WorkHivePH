---
name: table-rls-agent_followups
type: table-rls
source: db:pg_policies+pg_trigger:agent_followups
source_sha: 259e31011f9e96a4
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `agent_followups` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, worker_name, topic*, detail, due_at*, status*, importance*, source_trace_id, created_by, created_at*, surfaced_at, resolved_at

Policies:
- `followups_insert` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `followups_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = age` CHECK=`∅`
- `followups_update` [UPDATE · roles=public] USING=`false` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
