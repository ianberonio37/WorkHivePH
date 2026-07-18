---
name: table-rls-sso_configs
type: table-rls
source: db:pg_policies+pg_trigger:sso_configs
source_sha: d9c668aa9c6db1b4
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `sso_configs` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, provider*, status*, idp_entity_id, enforced*, created_at*, created_by, activated_at, notes

Policies:
- `sso_configs_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `sso_configs_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = sso_configs.hive_id) AND (hm.` CHECK=`∅`
- `sso_configs_update_locked` [UPDATE · roles=public] USING=`false` CHECK=`false`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
