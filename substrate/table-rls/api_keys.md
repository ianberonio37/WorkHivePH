---
name: table-rls-api_keys
type: table-rls
source: db:pg_policies+pg_trigger:api_keys
source_sha: bbb19b5b33142ca6
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `api_keys` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, key_prefix*, key_hash*, label, enabled, call_count, last_used_at, created_at

Policies:
- `api_keys_supervisor_all` [ALL · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = api_keys.hiv` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = api_keys.hiv`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
