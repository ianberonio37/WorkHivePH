---
name: table-rls-pf_intervals
type: table-rls
source: db:pg_policies+pg_trigger:pf_intervals
source_sha: 68f627f3efb2dc39
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `pf_intervals` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, asset_id*, fmea_mode_id, parameter*, p_threshold*, f_threshold*, pf_days*, recommended_interval_days*, basis*, generated_at*

Policies:
- `pf_intervals_parent_hive_guard` [ALL · roles=public] USING=`true` CHECK=`((auth.uid() IS NULL) OR (asset_id IS NULL) OR (EXISTS ( SELECT 1 FROM asset_nodes n WHERE ((n.id = pf_intervals.asset_i`
- `pf_intervals_write` [ALL · roles=public] USING=`false` CHECK=`false`
- `pf_intervals_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

**Verdict:** FLAGS: pf_intervals_parent_hive_guard (ALL) USING is open ('true') — potential cross-tenant read/stream.

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
