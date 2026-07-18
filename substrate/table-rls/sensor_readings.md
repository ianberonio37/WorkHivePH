---
name: table-rls-sensor_readings
type: table-rls
source: db:pg_policies+pg_trigger:sensor_readings
source_sha: e6d665de6ec7abf7
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `sensor_readings` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, asset_id*, parameter*, unit, quality_flag, value*, recorded_at*, source*, meta*, external_key*

Policies:
- `sensor_readings_no_delete` [DELETE · roles=public] USING=`false` CHECK=`∅`
- `sensor_readings_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `sensor_readings_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`
- `sensor_readings_no_update` [UPDATE · roles=public] USING=`false` CHECK=`false`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
