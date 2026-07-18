---
name: table-rls-hive_route_calls
type: table-rls
source: db:pg_policies+pg_trigger:hive_route_calls
source_sha: bcca3c77db7018f0
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `hive_route_calls` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): hive_id*, route*, hour_bucket*, call_count*, updated_at*

Policies:
- `hive_route_calls_write` [ALL · roles=public] USING=`false` CHECK=`false`
- `hive_route_calls_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = hive_route_calls.hive_id) AND` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
