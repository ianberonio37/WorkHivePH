---
name: table-rls-consulting_engagements
type: table-rls
source: db:pg_policies+pg_trigger:consulting_engagements
source_sha: c4dda1c7a37aef91
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `consulting_engagements` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, status*, started_at, completed_at, evidence*, created_at*, created_by

Policies:
- `consult_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `consult_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = consulting_engagements.hive_i` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
