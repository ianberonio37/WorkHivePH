---
name: table-rls-drone_inspections
type: table-rls
source: db:pg_policies+pg_trigger:drone_inspections
source_sha: d971a4933681f6bc
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `drone_inspections` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, asset_node_id, pilot, status*, reviewed_at, notes, created_at*

Policies:
- `drone_insert_locked` [INSERT · roles=public] USING=`∅` CHECK=`false`
- `drone_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`
- `drone_update_supervisor` [UPDATE · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = drone_inspections.hive_id) AN` CHECK=`true`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
