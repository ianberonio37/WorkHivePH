---
name: table-rls-hive_retention_config
type: table-rls
source: db:pg_policies+pg_trigger:hive_retention_config
source_sha: 5b9dc959f47059c3
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_retention_config` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, soft_delete_retention_days, audit_retention_days*, ai_telemetry_retention_days*, updated_at*, updated_by

Policies:
- `hive_retention_config_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `hive_retention_config_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = hive_retention_config.hive_id` CHECK=`∅`
- `hive_retention_config_write` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = hive_retention_config.hive_id` CHECK=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = hive_retention_config.hive_id`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
