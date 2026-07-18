---
name: table-rls-pf_intervals
type: table-rls
source: db:pg_policies+pg_trigger:pf_intervals
source_sha: 83f85a78f68822c4
last_verified: 2026-07-13
supersedes: null
---

## table-rls · `pf_intervals` — RLS posture (tenant table)

RLS enabled: **True** · has hive_id: True · has auth_uid: False

Columns (*=NOT NULL): id*, hive_id*, asset_id*, fmea_mode_id, parameter*, p_threshold*, f_threshold*, pf_days*, recommended_interval_days*, basis*, generated_at*

Policies:
- `pf_intervals_write` [ALL · roles=public] USING=`false` CHECK=`false`
- `pf_intervals_read` [SELECT · roles=public] USING=`((auth.uid() IS NOT NULL) AND (hive_id IN ( SELECT hm.hive_id FROM hive_members hm WHERE ((hm.auth_uid = auth.uid()) AND` CHECK=`∅`

**Verdict:** SCOPED — no structural hole detected by rules (verify live before trusting for a fix).

Links: [[reference_per_page_bughunt_roadmap]] [[project_platform_knowledge_substrate]]
