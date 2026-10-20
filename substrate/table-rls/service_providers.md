---
name: table-rls-service_providers
type: table-rls
source: db:pg_policies+pg_trigger:service_providers
source_sha: 1825f1f0f58db200
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `service_providers` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, provider_type*, auth_uid, worker_name, hive_id, display_name*, contact, categories*, service_areas*, base_location, live_location, base_lat, base_lng, availability*, verified*, verified_at, created_at*, updated_at*

Policies:
- `service_providers_self_insert` [INSERT · roles=authenticated] USING=`∅` CHECK=`(((provider_type = 'freelancer'::text) AND (auth_uid = ( SELECT auth.uid() AS uid))) OR ((provider_type = 'hive'::text) `
- `service_providers_read` [SELECT · roles=authenticated] USING=`true` CHECK=`∅`
- `service_providers_self_update` [UPDATE · roles=authenticated] USING=`((auth_uid = ( SELECT auth.uid() AS uid)) OR ((provider_type = 'hive'::text) AND (hive_id IN ( SELECT hm.hive_id FROM hi` CHECK=`∅`

Guard triggers: `trg_daily_cap_service_providers`, `trg_guard_service_provider_writes`

**Verdict:** FLAGS: service_providers_read (SELECT) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
