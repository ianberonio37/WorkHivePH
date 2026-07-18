---
name: table-rls-integration_configs
type: table-rls
source: db:pg_policies+pg_trigger:integration_configs
source_sha: c85279314ca88dc3
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `integration_configs` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id, system_type*, label, endpoint_url, auth_method, field_map, sync_freq, enabled, last_sync_at, last_sync_count, created_at, auth_token, last_sync_status, last_sync_error, delta_cursor, updated_at*

Policies:
- `integration_configs_supervisor_all` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = integration_configs.hive_id) ` CHECK=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = integration_configs.hive_id) `

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
