---
name: table-rls-hive_retention_config
type: table-rls
source: db:pg_policies+pg_trigger:hive_retention_config
source_sha: c83976224a8ae7b9
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_retention_config` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, soft_delete_retention_days, audit_retention_days*, ai_telemetry_retention_days*, updated_at*, updated_by

Policies:
- `hive_retention_config_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `hive_retention_config_read` [SELECT · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = hive_retenti` CHECK=`∅`
- `hive_retention_config_write` [UPDATE · roles=public] USING=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = hive_retenti` CHECK=`((( SELECT auth.uid() AS uid) IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = hive_retenti`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
