---
name: table-rls-hive_route_quotas
type: table-rls
source: db:pg_policies+pg_trigger:hive_route_quotas
source_sha: 7ced1a428f0efc9b
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_route_quotas` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, route*, hourly_cap*, enforce*, notes, created_at*, updated_at*

Policies:
- `hive_route_quotas_write` [ALL · roles=public] USING=`false` CHECK=`false`
- `hive_route_quotas_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = hive_route_quotas.hive_id) AN` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
