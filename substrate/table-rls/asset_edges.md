---
name: table-rls-asset_edges
type: table-rls
source: db:pg_policies+pg_trigger:asset_edges
source_sha: fcb06cbf138abc21
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `asset_edges` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: True

Columns (*=NOT NULL): id*, hive_id*, auth_uid, from_node_id*, to_node_id*, edge_type*, properties*, created_at*

Policies:
- `asset_edges_write` [ALL · roles=public] USING=`((auth.uid() IS NOT NULL) AND (EXISTS ( SELECT 1 FROM hive_members hm WHERE ((hm.hive_id = asset_edges.hive_id) AND (hm.` CHECK=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND`
- `asset_edges_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
