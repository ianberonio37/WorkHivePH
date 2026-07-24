---
name: table-rls-client_errors
type: table-rls
source: db:pg_policies+pg_trigger:client_errors
source_sha: 3a4b8532d050ab95
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `client_errors` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id, worker_name, auth_uid, context*, message*, stack, page, user_agent, created_at*

Policies:
- `client_errors_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`((auth.uid() IS NOT NULL) AND ((hive_id IS NULL) OR (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = client_`
- `client_errors_read` [SELECT · roles=authenticated] USING=`(EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = client_errors.hive_id) AND (hm.auth_uid = auth.uid()) AND (` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
