---
name: table-rls-sensor_topic_map
type: table-rls
source: db:pg_policies+pg_trigger:sensor_topic_map
source_sha: e28c50dc51bea916
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `sensor_topic_map` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, topic_pattern*, asset_id*, parameter*, unit, scale*, active*, created_at*

Policies:
- `sensor_topic_map_write_supervisor` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = sensor_topic_map.hive_id) AND` CHECK=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = sensor_topic_map.hive_id) AND`
- `sensor_topic_map_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
